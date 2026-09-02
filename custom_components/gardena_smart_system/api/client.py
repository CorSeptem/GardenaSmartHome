"""REST API client for Gardena Smart System."""

from __future__ import annotations

import json as _json
import logging
import uuid
from typing import Any

import aiohttp

from ..const import COMMAND_URL, LOCATIONS_URL, WEBSOCKET_URL
from .auth import GardenaAuth, GardenaAuthError

_LOGGER = logging.getLogger(__name__)


class GardenaClient:
    """Client for Gardena Smart System REST API."""

    def __init__(self, auth: GardenaAuth, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self._auth = auth
        self._session = session

    async def get_locations(self) -> list[dict[str, Any]]:
        """Get all locations associated with the account."""
        data = await self._api_request("GET", LOCATIONS_URL)
        return data.get("data", [])

    async def get_location(self, location_id: str) -> dict[str, Any]:
        """Get a specific location with all devices."""
        url = f"{LOCATIONS_URL}/{location_id}"
        return await self._api_request("GET", url)

    async def get_websocket_url(self, location_id: str) -> str:
        """Request a WebSocket URL for real-time updates."""
        payload = {
            "data": {
                "type": "WEBSOCKET",
                "attributes": {"locationId": location_id},
                "id": f"request-{uuid.uuid4()}",
            }
        }

        data = await self._api_request("POST", WEBSOCKET_URL, json=payload)
        ws_url = data.get("data", {}).get("attributes", {}).get("url")

        if not ws_url:
            raise GardenaApiError("No WebSocket URL in response")

        return ws_url

    async def send_command(
        self, service_id: str, command: dict[str, Any]
    ) -> dict[str, Any]:
        """Send a command to a device service."""
        url = f"{COMMAND_URL}/{service_id}"
        # JSON:API requires data.id to match the resource id in the URL path
        command["data"]["id"] = service_id
        return await self._api_request("PUT", url, json=command)

    async def _api_request(
        self,
        method: str,
        url: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated API request."""
        await self._auth.ensure_valid_token()
        headers = self._auth.get_headers()
        # Serialize manually so aiohttp does not override our Content-Type header
        # (aiohttp's json= kwarg sets Content-Type: application/json internally,
        # overwriting application/vnd.api+json which Gardena requires)
        data = _json.dumps(json).encode("utf-8") if json is not None else None

        try:
            async with self._session.request(
                method, url, headers=headers, data=data
            ) as resp:
                if resp.status == 401:
                    _LOGGER.debug("Token expired, re-authenticating")
                    await self._auth.authenticate()
                    headers = self._auth.get_headers()
                    async with self._session.request(
                        method, url, headers=headers, data=data
                    ) as retry_resp:
                        retry_resp.raise_for_status()
                        if retry_resp.content_length == 0:
                            return {}
                        return await retry_resp.json()

                if resp.status >= 400:
                    text = await resp.text()
                    raise GardenaApiError(
                        f"API request failed ({resp.status}): {text}"
                    )

                if resp.content_length == 0 or resp.status == 204:
                    return {}
                return await resp.json()

        except aiohttp.ClientError as err:
            raise GardenaApiError(f"Connection error: {err}") from err

    async def close(self) -> None:
        """Clean up resources."""

    # Command helpers

    async def mower_start(
        self, service_id: str, duration: int | None = None
    ) -> dict[str, Any]:
        """Start the mower.

        Args:
            service_id: The mower service ID.
            duration: Duration in minutes. Defaults to 60 min.
        """
        seconds = (duration * 60) if duration else 3600
        command = {
            "data": {
                "type": SERVICE_MOWER_COMMAND,
                "attributes": {
                    "command": "START_SECONDS_TO_OVERRIDE",
                    "seconds": seconds,
                },
                "id": f"request-{uuid.uuid4()}",
            }
        }
        return await self.send_command(service_id, command)

    async def mower_resume_schedule(self, service_id: str) -> dict[str, Any]:
        """Start mowing according to the mower's own schedule."""
        command = {
            "data": {
                "type": SERVICE_MOWER_COMMAND,
                "attributes": {"command": "START_DONT_OVERRIDE"},
                "id": f"request-{uuid.uuid4()}",
            }
        }
        return await self.send_command(service_id, command)

    async def mower_park(self, service_id: str) -> dict[str, Any]:
        """Park the mower until next schedule."""
        command = {
            "data": {
                "type": SERVICE_MOWER_COMMAND,
                "attributes": {"command": "PARK_UNTIL_NEXT_TASK"},
                "id": f"request-{uuid.uuid4()}",
            }
        }
        return await self.send_command(service_id, command)

    async def mower_pause(self, service_id: str) -> dict[str, Any]:
        """Pause the mower."""
        command = {
            "data": {
                "type": SERVICE_MOWER_COMMAND,
                "attributes": {"command": "PARK_UNTIL_FURTHER_NOTICE"},
                "id": f"request-{uuid.uuid4()}",
            }
        }
        return await self.send_command(service_id, command)

    async def valve_open(
        self, service_id: str, duration: int = 30
    ) -> dict[str, Any]:
        """Open a valve for a given duration in minutes."""
        command = {
            "data": {
                "type": SERVICE_VALVE_COMMAND,
                "attributes": {
                    "command": "START_SECONDS_TO_OVERRIDE",
                    "seconds": duration * 60,
                },
                "id": f"request-{uuid.uuid4()}",
            }
        }
        return await self.send_command(service_id, command)

    async def valve_close(self, service_id: str) -> dict[str, Any]:
        """Close a valve."""
        command = {
            "data": {
                "type": SERVICE_VALVE_COMMAND,
                "attributes": {"command": "STOP_UNTIL_NEXT_TASK"},
                "id": f"request-{uuid.uuid4()}",
            }
        }
        return await self.send_command(service_id, command)

    async def valve_pause(self, service_id: str) -> dict[str, Any]:
        """Pause a valve."""
        command = {
            "data": {
                "type": SERVICE_VALVE_COMMAND,
                "attributes": {"command": "PAUSE"},
                "id": f"request-{uuid.uuid4()}",
            }
        }
        return await self.send_command(service_id, command)

    async def valve_unpause(self, service_id: str) -> dict[str, Any]:
        """Unpause a valve."""
        command = {
            "data": {
                "type": SERVICE_VALVE_COMMAND,
                "attributes": {"command": "UNPAUSE"},
                "id": f"request-{uuid.uuid4()}",
            }
        }
        return await self.send_command(service_id, command)

    async def power_socket_on(
        self, service_id: str, duration: int | None = None
    ) -> dict[str, Any]:
        """Turn on the power socket.

        Args:
            service_id: The power socket service ID.
            duration: Duration in minutes. If None, turns on indefinitely.
        """
        if duration:
            attrs: dict[str, Any] = {
                "command": "START_SECONDS_TO_OVERRIDE",
                "seconds": duration * 60,
            }
        else:
            attrs = {"command": "START_OVERRIDE"}
        command = {
            "data": {
                "type": SERVICE_POWER_SOCKET_COMMAND,
                "attributes": attrs,
                "id": f"request-{uuid.uuid4()}",
            }
        }
        return await self.send_command(service_id, command)

    async def power_socket_off(self, service_id: str) -> dict[str, Any]:
        """Turn off the power socket."""
        command = {
            "data": {
                "type": SERVICE_POWER_SOCKET_COMMAND,
                "attributes": {"command": "STOP_UNTIL_NEXT_TASK"},
                "id": f"request-{uuid.uuid4()}",
            }
        }
        return await self.send_command(service_id, command)


SERVICE_MOWER_COMMAND = "MOWER_CONTROL"
SERVICE_VALVE_COMMAND = "VALVE_CONTROL"
SERVICE_POWER_SOCKET_COMMAND = "POWER_SOCKET_CONTROL"


class GardenaApiError(Exception):
    """Exception for API errors."""
