"""Support for X-Sense buttons."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from xsense.entity import Entity

from homeassistant import config_entries
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import XSenseDataUpdateCoordinator
from .device_support import async_run_device_action
from .entity import XSenseEntity


async def run_action(entity: Entity, xsense, action: str) -> None:
    """Run an X-Sense device action."""
    await async_run_device_action(xsense, entity, action)


@dataclass(kw_only=True, frozen=True)
class XSenseButtonEntityDescription(ButtonEntityDescription):
    """Describes an X-Sense button entity."""

    exists_fn: Callable[[Entity, Any], bool] = lambda entity, api: True
    press_fn: Callable[[Entity, Any], Awaitable[None]]


BUTTONS: tuple[XSenseButtonEntityDescription, ...] = (
    XSenseButtonEntityDescription(
        key="test",
        translation_key="test",
        entity_category=EntityCategory.CONFIG,
        exists_fn=lambda entity, xsense: xsense.has_action(entity, "test"),
        press_fn=partial(run_action, action="test"),
    ),
    XSenseButtonEntityDescription(
        key="mute",
        translation_key="mute",
        entity_category=EntityCategory.CONFIG,
        exists_fn=lambda entity, xsense: xsense.has_action(entity, "mute"),
        press_fn=partial(run_action, action="mute"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up X-Sense buttons."""
    entities: list[ButtonEntity] = []
    coordinator: XSenseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    xsense = coordinator.xsense

    if xsense is None:
        return

    for station in coordinator.data["stations"].values():
        entities.extend(
            XSenseButtonEntity(coordinator, station, description)
            for description in BUTTONS
            if description.exists_fn(station, xsense)
        )

    for dev in coordinator.data["devices"].values():
        entities.extend(
            XSenseButtonEntity(
                coordinator, dev, description, station_id=dev.station.entity_id
            )
            for description in BUTTONS
            if description.exists_fn(dev, xsense)
        )

    async_add_entities(entities)


class XSenseButtonEntity(XSenseEntity, ButtonEntity):
    """Button for an X-Sense device."""

    entity_description: XSenseButtonEntityDescription

    def __init__(
        self,
        coordinator: XSenseDataUpdateCoordinator,
        entity: Entity,
        entity_description: XSenseButtonEntityDescription,
        station_id: str | None = None,
    ) -> None:
        """Set up the instance."""
        self._station_id = station_id
        self.entity_description = entity_description
        self._attr_available = False

        super().__init__(coordinator, entity, station_id)

    async def async_press(self) -> None:
        """Press the button."""
        xsense = self.coordinator.xsense
        if xsense is None:
            return

        if self._station_id:
            device = self.coordinator.data["devices"][self._dev_id]
        else:
            device = self.coordinator.data["stations"][self._dev_id]

        await self.entity_description.press_fn(device, xsense)
