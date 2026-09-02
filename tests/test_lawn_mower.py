"""Tests for the lawn mower entity's activity mapping."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.lawn_mower import LawnMowerActivity

from custom_components.gardena_smart_system.entities.lawn_mower import (
    GardenaLawnMower,
)


def _mower(service_attrs: dict) -> GardenaLawnMower:
    """Build a mower entity over a stub coordinator with given MOWER attributes."""
    coordinator = MagicMock()
    coordinator.get_device.return_value = {
        "attributes": {"name": {"value": "Sileno"}}
    }

    def by_id(device_id, service_id, attribute, default=None):
        return service_attrs.get(attribute, default)

    coordinator.get_service_attribute_by_id.side_effect = by_id
    return GardenaLawnMower(coordinator, "device-1", "mower-1")


def test_error_state_wins_over_parked_activity():
    """A stuck mower reports state=ERROR while activity stays PARKED_*."""
    mower = _mower(
        {
            "state": {"value": "ERROR"},
            "activity": {"value": "PARKED_TIMER"},
            "lastErrorCode": {"value": "OUTSIDE_WORKING_AREA"},
        }
    )
    assert mower.activity == LawnMowerActivity.ERROR


def test_ok_state_maps_activity():
    """With state=OK the activity decides."""
    assert (
        _mower({"state": {"value": "OK"}, "activity": {"value": "OK_CUTTING"}}).activity
        == LawnMowerActivity.MOWING
    )
    assert (
        _mower({"state": {"value": "OK"}, "activity": {"value": "OK_SEARCHING"}}).activity
        == LawnMowerActivity.MOWING
    )
    assert (
        _mower({"state": {"value": "OK"}, "activity": {"value": "PARKED_PARK_SELECTED"}}).activity
        == LawnMowerActivity.DOCKED
    )
    assert (
        _mower({"state": {"value": "OK"}, "activity": {"value": "PAUSED"}}).activity
        == LawnMowerActivity.PAUSED
    )


def test_warning_state_is_not_error():
    """WARNING is informational; the mower keeps working."""
    assert (
        _mower({"state": {"value": "WARNING"}, "activity": {"value": "OK_CUTTING"}}).activity
        == LawnMowerActivity.MOWING
    )
