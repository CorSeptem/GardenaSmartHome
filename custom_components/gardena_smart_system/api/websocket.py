"""WebSocket handler for Gardena Smart System real-time updates."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from functools import partial
from typing import Any, Callable

import aiohttp

from ..const import WS_RECONNECT_DELAYS
from .auth import GardenaAuth
from .client import GardenaClient

_LOGGER = logging.getLogger(__name__)


class GardenaWebSocket:
    """Manage WebSocket connection for real-time device updates."""

    def __init__(
        self,
        auth: GardenaAuth,
        client: GardenaClient,
        session: aiohttp.ClientSession,
        location_id: str,
        on_message: Callable[[dict[str, Any]], None],
        on_connected: Callable[[], None] | None = None,
        on_disconnected: Callable[[], None] | None = None,
    ) -> None:
        """Initialize WebSocket handler."""
        self._auth = auth
        self._client = client
        self._session = session
        self._location_id = location_id
        self._on_message = on_message
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._listen_task: asyncio.Task[None] | None = None
        self._running = False
        self._retry_count = 0
        self._connected = False
        self._ssl_context: ssl.SSLContext | None = None

    @property
    def connected(self) -> bool:
        """Return whether the WebSocket is connected."""
        return self._connected

    async def _get_ssl_context(self) -> ssl.SSLContext:
        """Get SSL context, creating it in executor to avoid blocking.

        This addresses issue #315 - blocking SSL calls in event loop.
        """
        if self._ssl_context is None:
            loop = asyncio.get_event_loop()
            self._ssl_context = await loop.run_in_executor(
                None, partial(ssl.create_default_context)
            )
        return self._ssl_context

    async def connect(self) -> None:
        """Start the WebSocket connection and listener."""
        self._running = True
        self._retry_count = 0
        self._listen_task = asyncio.ensure_future(self._listen_loop())

    async def disconnect(self) -> None:
        """Disconnect the WebSocket."""
        self._running = False
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._listen_task is not None:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None
        self._connected = False
        if self._on_disconnected:
            self._on_disconnected()

    async def _listen_loop(self) -> None:
        """Main WebSocket listen loop with automatic reconnection.

        Backoff 5s → 10s → 30s → 60s → 120s → 300s, then every 300s for as
        long as the integration is loaded. The API closes the socket on
        purpose every few hours; a longer outage (router restart, ISP hiccup)
        must not leave the integration permanently without push updates.
        """
        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
                _LOGGER.warning("WebSocket connection failed: %s", err)
            except Exception:
                _LOGGER.exception("WebSocket error")

            if not self._running:
                break

            # Notify once per real disconnect, not once per failed retry.
            was_connected = self._connected
            self._connected = False
            if was_connected and self._on_disconnected:
                self._on_disconnected()

            delay = WS_RECONNECT_DELAYS[
                min(self._retry_count, len(WS_RECONNECT_DELAYS) - 1)
            ]
            self._retry_count += 1
            _LOGGER.info(
                "WebSocket reconnecting in %ds (attempt %d)",
                delay,
                self._retry_count,
            )
            await asyncio.sleep(delay)

    async def _connect_and_listen(self) -> None:
        """Establish WebSocket connection and process messages."""
        # Ensure token is fresh before connecting
        await self._auth.ensure_valid_token()

        # Get a new WebSocket URL
        ws_url = await self._client.get_websocket_url(self._location_id)

        ssl_context = await self._get_ssl_context()

        _LOGGER.debug("Connecting to WebSocket for location %s", self._location_id)

        async with self._session.ws_connect(
            ws_url,
            ssl=ssl_context,
            heartbeat=30,
            timeout=60,
        ) as ws:
            self._ws = ws
            self._connected = True
            self._retry_count = 0  # Reset on successful connection

            if self._on_connected:
                self._on_connected()

            _LOGGER.info("WebSocket connected for location %s", self._location_id)

            # Start token refresh task
            token_refresh_task = asyncio.ensure_future(
                self._token_refresh_loop()
            )

            try:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            data = json.loads(msg.data)
                            self._on_message(data)
                        except json.JSONDecodeError:
                            _LOGGER.warning(
                                "Invalid JSON from WebSocket: %s", msg.data
                            )
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        _LOGGER.error(
                            "WebSocket error: %s", ws.exception()
                        )
                        break
                    elif msg.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSING,
                        aiohttp.WSMsgType.CLOSED,
                    ):
                        _LOGGER.info("WebSocket closed")
                        break
            finally:
                token_refresh_task.cancel()
                try:
                    await token_refresh_task
                except asyncio.CancelledError:
                    pass

    async def _token_refresh_loop(self) -> None:
        """Periodically check and refresh token before expiry.

        This addresses the requirement to refresh 5 minutes before expiry
        without interrupting the WebSocket connection.
        """
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                if self._auth.needs_refresh:
                    _LOGGER.debug("Proactively refreshing token")
                    await self._auth.ensure_valid_token()
            except asyncio.CancelledError:
                break
            except Exception:
                _LOGGER.exception("Error refreshing token")
