"""DataUpdateCoordinator for the X-Sense integration."""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timedelta
import json
from typing import Any

from xsense import AsyncXSense, House
from xsense.exceptions import APIFailure, AuthFailed, NotFoundError, SessionExpired

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.logging import catch_log_exception

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, POLL_INTERVAL_MIN
from .mqtt import DEFAULT_ENCODING, DEFAULT_QOS, XSenseMQTT


class XSenseDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """X-Sense data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.xsense: AsyncXSense | None = None
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            always_update=True,
        )
        self.mqtt_servers: dict[str, XSenseMQTT] = {}

    def mqtt_server(self, host: str) -> XSenseMQTT | None:
        """Get MQTT server instance for a specific host."""
        return self.mqtt_servers.get(host)

    async def _close_session(self) -> None:
        """Close the API client when supported by the installed python-xsense version."""
        if self.xsense is None:
            return
        close = getattr(self.xsense, "close", None)
        if callable(close):
            await close()
        self.xsense = None

    async def _connect(self) -> None:
        """Authenticate with the X-Sense cloud API."""
        email = self.entry.data[CONF_EMAIL]
        password = self.entry.data[CONF_PASSWORD]

        await self._close_session()

        self.xsense = AsyncXSense()
        await self.xsense.init()

        try:
            await self.xsense.login(email, password)
        except AuthFailed as ex:
            raise ConfigEntryAuthFailed(f"Login failed: {ex!s}") from ex

    async def async_shutdown(self) -> None:
        """Disconnect MQTT clients and close the API session."""
        for mqtt in self.mqtt_servers.values():
            await mqtt.async_disconnect(disconnect_paho_client=True)
        self.mqtt_servers.clear()
        await self._close_session()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from X-Sense."""
        if self.xsense is None:
            await self._connect()

        devices = await self.get_devices()

        if self.xsense and self.xsense.houses:
            for house in self.xsense.houses.values():
                mqtt = self.mqtt_server(house.mqtt_server)
                if mqtt is None:
                    mqtt = self.setup_mqtt(house)
                await mqtt.async_connect()
                await self.assure_subscriptions(house)

                if mqtt.connected:
                    await self.request_device_updates(mqtt, house)

        return devices

    async def get_devices(self, retry: bool = False) -> dict[str, Any]:
        """Retrieve all stations and devices from the X-Sense account."""
        assert self.xsense is not None

        stations: dict[str, Any] = {}
        devices: dict[str, Any] = {}

        try:
            await self.xsense.load_all()

            for house in self.xsense.houses.values():
                stations.update(house.stations.items())
                with suppress(NotFoundError):
                    await self.xsense.get_house_state(house)
                for station in house.stations.values():
                    await self.xsense.get_station_state(station)
                    await self.xsense.get_state(station)
                    devices.update(station.devices.items())

        except (SessionExpired, AuthFailed) as ex:
            if not retry:
                await self._connect()
                return await self.get_devices(retry=True)
            raise ConfigEntryAuthFailed(
                "Could not update, session no longer valid"
            ) from ex
        except APIFailure as ex:
            raise UpdateFailed(f"X-Sense API issue: {ex}") from ex

        return {"stations": stations, "devices": devices}

    def _get_station_by_sn(self, identifier: str):
        """Find a station by serial number."""
        if self.xsense is None:
            return None

        for house in self.xsense.houses.values():
            if station := house.get_station_by_sn(identifier):
                return station
        return None

    def setup_mqtt(self, house: House) -> XSenseMQTT:
        """Create and configure an MQTT client for a house."""
        if house.mqtt_server not in self.mqtt_servers:
            mqtt = XSenseMQTT(self.hass, self.entry, house.mqtt)
            mqtt.on_data = self.async_event_received
            mqtt.init_client()
            self.mqtt_servers[house.mqtt_server] = mqtt

        return self.mqtt_servers[house.mqtt_server]

    def async_event_received(self, topic: str, data_str: bytes) -> None:
        """Handle incoming MQTT shadow updates and alarm events."""
        if self.xsense is None:
            return

        try:
            data = json.loads(data_str.decode("utf8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            LOGGER.debug("Ignoring non-JSON MQTT payload on %s", topic)
            return

        updated = False
        if reported := data.get("state", {}).get("reported"):
            updated = self._apply_station_reported(reported)
        elif data.get("type") == 1 and "alarmStatus" in data:
            updated = self._apply_alarm_event(data)

        if updated:
            self.async_update_listeners()

    def _apply_station_reported(self, station_data: dict[str, Any]) -> bool:
        """Apply a device shadow payload to the matching station/devices."""
        station_sn = station_data.get("stationSN")
        if not station_sn:
            return False

        station = self._get_station_by_sn(station_sn)
        if station is None:
            return False

        children = dict(station_data.get("devs", {}))
        station_payload = {
            key: value for key, value in station_data.items() if key != "devs"
        }
        self.xsense.parse_get_state(station, station_payload)

        for sn, values in children.items():
            if dev := station.get_device_by_sn(sn):
                dev.set_data(values)

        return True

    def _apply_alarm_event(self, data: dict[str, Any]) -> bool:
        """Apply a real-time alarm event (type 1) from @xsense/events."""
        station_sn = data.get("stationSN") or data.get("deviceSN")
        if not station_sn:
            return False

        station = self._get_station_by_sn(station_sn)
        if station is None:
            return False

        payload = {"alarmStatus": str(data["alarmStatus"])}
        device_sn = data.get("deviceSN")
        if device_sn and (dev := station.get_device_by_sn(device_sn)):
            dev.set_data(payload)
        else:
            station.set_data(payload)

        return True

    async def assure_subscriptions(self, house: House) -> None:
        """Subscribe to MQTT topics for a house."""
        await self.assure_subscription(
            house.mqtt_server, f"@xsense/events/+/{house.house_id}"
        )
        await self.assure_subscription(
            house.mqtt_server,
            f"$aws/things/{house.house_id}/shadow/name/+/update",
        )

        for station in house.stations.values():
            await self.assure_subscription(
                house.mqtt_server,
                f"$aws/things/{station.shadow_name}/shadow/name/+/update",
            )
            await self.assure_subscription(
                house.mqtt_server,
                f"$aws/events/presence/+/{station.shadow_name}",
            )

    async def assure_subscription(self, server: str, topic: str) -> None:
        """Subscribe to a topic if not already subscribed."""
        mqtt = self.mqtt_server(server)
        if mqtt is None:
            LOGGER.error("Unknown MQTT server %s", server)
            return

        if not mqtt.is_subscribed(topic):
            await self.subscribe_topic(mqtt, topic, self.async_event_received)

    async def subscribe_topic(self, mqtt: XSenseMQTT, topic: str, msg_callback) -> None:
        """Subscribe to an MQTT topic."""
        await mqtt.async_subscribe(
            topic,
            catch_log_exception(
                msg_callback,
                lambda msg: (
                    f"Exception in {msg_callback.__name__} when handling msg on "
                    f"'{msg.topic}': '{msg.payload}'"
                ),
            ),
            DEFAULT_QOS,
            DEFAULT_ENCODING,
        )

    async def request_device_updates(self, mqtt: XSenseMQTT, house: House) -> None:
        """Request live updates for temperature/humidity sensors."""
        assert self.xsense is not None

        for station in house.stations.values():
            updatable_devices = [
                dev.sn for dev in station.devices.values() if dev.type in ("STH51", "STH0A", "STH0B")
            ]

            if not updatable_devices:
                continue

            msg = {
                "state": {
                    "desired": {
                        "shadow": "appTempData",
                        "deviceSN": updatable_devices,
                        "source": "1",
                        "report": "1",
                        "reportDst": "1",
                        "timeoutM": str(POLL_INTERVAL_MIN),
                        "userId": self.xsense.userid,
                        "time": datetime.now().strftime("%Y%m%d%H%M%S"),
                        "stationSN": station.sn,
                    }
                }
            }
            await mqtt.async_publish(
                f"$aws/things/{station.shadow_name}/shadow/name/2nd_apptempdata/update",
                json.dumps(msg),
                0,
                False,
            )
