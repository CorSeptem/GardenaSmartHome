"""Valve entity for Gardena Smart System."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import (
    DOMAIN,
    SERVICE_VALVE,
    VALVE_ACTIVITY_CLOSED,
    VALVE_ACTIVITY_MANUAL_WATERING,
    VALVE_ACTIVITY_SCHEDULED_WATERING,
)
from ..coordinator import GardenaDataCoordinator
from .base import GardenaEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_VALVE_DURATION = 30  # minutes

SERVICE_OPEN_VALVE = "open_valve"
SERVICE_CLOSE_VALVE = "close_valve"
SERVICE_PAUSE_VALVE = "pause_valve"
SERVICE_UNPAUSE_VALVE = "unpause_valve"

DURATION_SCHEMA = {
    vol.Optional("duration", default=DEFAULT_VALVE_DURATION): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=1440)
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gardena valve entities."""
    coordinator: GardenaDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[GardenaValve] = []
    for device_id, device in coordinator.devices.items():
        for service in device.get("services", []):
            if service["type"] == SERVICE_VALVE:
                entities.append(
                    GardenaValve(
                        coordinator=coordinator,
                        device_id=device_id,
                        service_id=service["id"],
                    )
                )

    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_OPEN_VALVE, DURATION_SCHEMA, "async_open_valve_for"
    )
    platform.async_register_entity_service(
        SERVICE_CLOSE_VALVE, None, "async_close_valve"
    )
    platform.async_register_entity_service(
        SERVICE_PAUSE_VALVE, None, "async_pause_valve"
    )
    platform.async_register_entity_service(
        SERVICE_UNPAUSE_VALVE, None, "async_unpause_valve"
    )


class GardenaValve(GardenaEntity, ValveEntity):
    """Representation of a Gardena irrigation valve."""

    _attr_device_class = ValveDeviceClass.WATER
    _attr_reports_position = False
    _attr_supported_features = (
        ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    )

    def __init__(
        self,
        coordinator: GardenaDataCoordinator,
        device_id: str,
        service_id: str,
    ) -> None:
        """Initialize the valve entity."""
        super().__init__(coordinator, device_id, service_id, SERVICE_VALVE)
        self._attr_unique_id = f"{device_id}_{service_id}"

    @property
    def name(self) -> str | None:
        """Return the valve's individual name from the service."""
        return self.get_service_attribute("name") or "Valve"

    @property
    def is_closed(self) -> bool:
        """Return if the valve is closed."""
        activity = self.get_service_attribute("activity", {})
        if isinstance(activity, dict):
            activity = activity.get("value", VALVE_ACTIVITY_CLOSED)
        return activity == VALVE_ACTIVITY_CLOSED

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "activity": self.get_service_attribute("activity"),
            "duration": self.get_service_attribute("duration"),
            "battery_level": self.get_common_attribute("batteryLevel"),
            "rf_link_level": self.get_common_attribute("rfLinkLevel"),
        }

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve (HA standard action; default duration)."""
        await self.async_open_valve_for(DEFAULT_VALVE_DURATION)

    async def async_open_valve_for(self, duration: int = DEFAULT_VALVE_DURATION) -> None:
        """Open the valve for ``duration`` minutes."""
        await self.coordinator.client.valve_open(self._service_id, duration)

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close the valve."""
        await self.coordinator.client.valve_close(self._service_id)

    async def async_pause_valve(self) -> None:
        """Pause an active watering."""
        await self.coordinator.client.valve_pause(self._service_id)

    async def async_unpause_valve(self) -> None:
        """Resume a paused watering."""
        await self.coordinator.client.valve_unpause(self._service_id)
