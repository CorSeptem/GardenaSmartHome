"""Lawn mower entity for Gardena Smart System."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import (
    DOMAIN,
    MOWER_ACTIVITY_NONE,
    MOWER_ACTIVITY_OK_CHARGING,
    MOWER_ACTIVITY_OK_CUTTING,
    MOWER_ACTIVITY_OK_CUTTING_TIMER_OVERRIDDEN,
    MOWER_ACTIVITY_OK_LEAVING,
    MOWER_ACTIVITY_OK_SEARCHING,
    MOWER_ACTIVITY_PARKED_AUTOTIMER,
    MOWER_ACTIVITY_PARKED_PARK_SELECTED,
    MOWER_ACTIVITY_PARKED_TIMER,
    MOWER_ACTIVITY_PAUSED,
    MOWER_STATE_ERROR,
    SERVICE_COMMON,
    SERVICE_MOWER,
)
from ..coordinator import GardenaDataCoordinator
from .base import GardenaEntity

_LOGGER = logging.getLogger(__name__)

MOWING_ACTIVITIES = {
    MOWER_ACTIVITY_OK_CUTTING,
    MOWER_ACTIVITY_OK_CUTTING_TIMER_OVERRIDDEN,
    MOWER_ACTIVITY_OK_SEARCHING,
    MOWER_ACTIVITY_OK_LEAVING,
}

DOCKED_ACTIVITIES = {
    MOWER_ACTIVITY_OK_CHARGING,
    MOWER_ACTIVITY_PARKED_TIMER,
    MOWER_ACTIVITY_PARKED_PARK_SELECTED,
    MOWER_ACTIVITY_PARKED_AUTOTIMER,
    MOWER_ACTIVITY_NONE,
}

SERVICE_START_MOWING = "start_mowing"
SERVICE_DOCK_MOWER = "dock_mower"
SERVICE_PAUSE_MOWER = "pause_mower"

DURATION_SCHEMA = {
    vol.Optional("duration"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gardena lawn mower entities."""
    coordinator: GardenaDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[GardenaLawnMower] = []
    for device_id, device in coordinator.devices.items():
        for service in device.get("services", []):
            if service["type"] == SERVICE_MOWER:
                entities.append(
                    GardenaLawnMower(
                        coordinator=coordinator,
                        device_id=device_id,
                        service_id=service["id"],
                    )
                )

    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_START_MOWING, DURATION_SCHEMA, "async_start_mowing_for"
    )
    platform.async_register_entity_service(SERVICE_DOCK_MOWER, None, "async_dock")
    platform.async_register_entity_service(SERVICE_PAUSE_MOWER, None, "async_pause")


class GardenaLawnMower(GardenaEntity, LawnMowerEntity):
    """Representation of a Gardena Sileno lawn mower."""

    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.DOCK
        | LawnMowerEntityFeature.PAUSE
    )

    def __init__(
        self,
        coordinator: GardenaDataCoordinator,
        device_id: str,
        service_id: str,
    ) -> None:
        """Initialize the lawn mower entity."""
        super().__init__(coordinator, device_id, service_id, SERVICE_MOWER)
        self._attr_unique_id = f"{device_id}_{SERVICE_MOWER}"
        self._attr_translation_key = "mower"

    @property
    def activity(self) -> LawnMowerActivity | None:
        """Return the current activity.

        Errors are reported by the API in the ``state`` attribute
        (OK/WARNING/ERROR/UNAVAILABLE) together with ``lastErrorCode``;
        ``activity`` keeps its last value (often PARKED_*) while the mower is
        stuck, so ``state`` must be checked first.
        """
        gardena_state = self.get_service_attribute("state", {})
        if isinstance(gardena_state, dict):
            gardena_state = gardena_state.get("value", "")
        if gardena_state == MOWER_STATE_ERROR:
            return LawnMowerActivity.ERROR

        gardena_activity = self.get_service_attribute("activity", {})
        if isinstance(gardena_activity, dict):
            gardena_activity = gardena_activity.get("value", "")

        if gardena_activity in MOWING_ACTIVITIES:
            return LawnMowerActivity.MOWING
        if gardena_activity == MOWER_ACTIVITY_PAUSED:
            return LawnMowerActivity.PAUSED
        if gardena_activity in DOCKED_ACTIVITIES:
            return LawnMowerActivity.DOCKED
        if gardena_activity and "ERROR" in str(gardena_activity).upper():
            return LawnMowerActivity.ERROR

        return LawnMowerActivity.DOCKED

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "battery_level": self.get_common_attribute("batteryLevel"),
            "rf_link_level": self.get_common_attribute("rfLinkLevel"),
            "operating_hours": self.get_service_attribute("operatingHours"),
            "last_error_code": self.get_service_attribute("lastErrorCode"),
            "activity": self.get_service_attribute("activity"),
            "state": self.get_service_attribute("state"),
        }

    async def async_start_mowing(self) -> None:
        """Start mowing (HA standard action; 60 minute override)."""
        await self.coordinator.client.mower_start(self._service_id)

    async def async_start_mowing_for(self, duration: int | None = None) -> None:
        """Start mowing for ``duration`` minutes, or resume the schedule."""
        if duration:
            await self.coordinator.client.mower_start(self._service_id, duration)
        else:
            await self.coordinator.client.mower_resume_schedule(self._service_id)

    async def async_dock(self) -> None:
        """Dock the mower."""
        await self.coordinator.client.mower_park(self._service_id)

    async def async_pause(self) -> None:
        """Pause the mower."""
        await self.coordinator.client.mower_pause(self._service_id)
