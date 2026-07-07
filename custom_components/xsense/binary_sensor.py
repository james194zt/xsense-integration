"""Support for X-Sense binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from xsense.device import Device
from xsense.entity import Entity
from xsense.station import Station

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import XSenseDataUpdateCoordinator
from .device_support import co_alarm_active, has_co_alarm_entity, has_smoke_alarm_entity, smoke_alarm_active
from .entity import XSenseEntity


@dataclass(kw_only=True, frozen=True)
class XSenseBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an X-Sense binary sensor entity."""

    exists_fn: Callable[[Entity], bool] = lambda _: True
    value_fn: Callable[[Entity], bool]


SENSORS: tuple[XSenseBinarySensorEntityDescription, ...] = (
    XSenseBinarySensorEntityDescription(
        key="is_life_end",
        translation_key="is_life_end",
        name="Status",
        icon="mdi:information-outline",
        exists_fn=lambda entity: "isLifeEnd" in entity.data,
        value_fn=lambda entity: entity.data["isLifeEnd"] == 1,
    ),
    XSenseBinarySensorEntityDescription(
        key="smoke_alarm",
        device_class=BinarySensorDeviceClass.SMOKE,
        exists_fn=has_smoke_alarm_entity,
        value_fn=lambda entity: smoke_alarm_active(entity.data),
    ),
    XSenseBinarySensorEntityDescription(
        key="co_alarm",
        translation_key="co_alarm",
        device_class=BinarySensorDeviceClass.CO,
        exists_fn=has_co_alarm_entity,
        value_fn=lambda entity: co_alarm_active(entity.data),
    ),
    XSenseBinarySensorEntityDescription(
        key="mute_status",
        translation_key="mute_status",
        name="Muted",
        icon="mdi:alarm-light-off",
        exists_fn=lambda entity: "muteStatus" in entity.data,
        value_fn=lambda entity: entity.data["muteStatus"],
    ),
    XSenseBinarySensorEntityDescription(
        key="activate",
        translation_key="activate",
        icon="mdi:bell-ring",
        exists_fn=lambda entity: "activate" in entity.data,
        value_fn=lambda entity: entity.data["activate"],
    ),
    XSenseBinarySensorEntityDescription(
        key="door",
        translation_key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        exists_fn=lambda device: "isOpen" in device.data,
        value_fn=lambda device: device.data["isOpen"] == "1",
    ),
)

MQTTSensor = XSenseBinarySensorEntityDescription(
    key="connected",
    translation_key="connected",
    entity_category=EntityCategory.DIAGNOSTIC,
    icon="mdi:connection",
    exists_fn=lambda entity: isinstance(entity, Station),
    value_fn=lambda entity: False,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up X-Sense binary sensors."""
    entities: list[BinarySensorEntity] = []
    coordinator: XSenseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    for station in coordinator.data["stations"].values():
        entities.extend(
            XSenseBinarySensorEntity(coordinator, station, description)
            for description in SENSORS
            if description.exists_fn(station)
        )
        entities.append(XSenseMQTTConnectedEntity(coordinator, station, MQTTSensor))

    for dev in coordinator.data["devices"].values():
        entities.extend(
            XSenseBinarySensorEntity(
                coordinator, dev, description, station_id=dev.station.entity_id
            )
            for description in SENSORS
            if description.exists_fn(dev)
        )

    async_add_entities(entities)


class XSenseBinarySensorEntity(XSenseEntity, BinarySensorEntity):
    """Binary sensor for an X-Sense device."""

    entity_description: XSenseBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: XSenseDataUpdateCoordinator,
        entity: Entity,
        entity_description: XSenseBinarySensorEntityDescription,
        station_id: str | None = None,
    ) -> None:
        """Set up the instance."""
        self._station_id = station_id
        self.entity_description = entity_description
        self._attr_available = False

        super().__init__(coordinator, entity, station_id)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        if self._station_id:
            device = self.coordinator.data["devices"][self._dev_id]
        else:
            device = self.coordinator.data["stations"][self._dev_id]

        return self.entity_description.value_fn(device)


class XSenseMQTTConnectedEntity(XSenseBinarySensorEntity):
    """Binary sensor for MQTT connectivity."""

    @property
    def is_on(self) -> bool | None:
        """Return whether the MQTT connection is active."""
        device = self.coordinator.data["stations"][self._dev_id]
        mqtt_server = self.coordinator.mqtt_server(device.house.mqtt_server)
        return mqtt_server.connected if mqtt_server else False
