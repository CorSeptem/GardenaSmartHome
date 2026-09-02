"""Tests for the WebSocket reconnect loop."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.gardena_smart_system.api.websocket import GardenaWebSocket


def _ws(on_disconnected=None) -> GardenaWebSocket:
    return GardenaWebSocket(
        auth=MagicMock(),
        client=MagicMock(),
        session=MagicMock(),
        location_id="loc-1",
        on_message=MagicMock(),
        on_connected=MagicMock(),
        on_disconnected=on_disconnected,
    )


@pytest.mark.asyncio
async def test_listen_loop_never_gives_up():
    """More than five consecutive failures must not stop the loop."""
    ws = _ws()
    ws._running = True
    attempts = 0

    async def failing_connect():
        nonlocal attempts
        attempts += 1
        if attempts >= 12:
            ws._running = False  # end the test
        raise aiohttp.ClientConnectionError("down")

    with patch.object(ws, "_connect_and_listen", failing_connect), patch(
        "custom_components.gardena_smart_system.api.websocket.asyncio.sleep",
        new=AsyncMock(),
    ) as sleep:
        await ws._listen_loop()

    assert attempts == 12
    # Backoff is capped at the last delay, never resets to a stop.
    delays = [call.args[0] for call in sleep.await_args_list]
    assert delays[:6] == [5, 10, 30, 60, 120, 300]
    assert all(d == 300 for d in delays[6:])


@pytest.mark.asyncio
async def test_on_disconnected_fires_once_per_real_disconnect():
    """Failed reconnect attempts do not re-fire the disconnect callback."""
    on_disconnected = MagicMock()
    ws = _ws(on_disconnected)
    ws._running = True
    attempts = 0

    async def connect():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            ws._connected = True  # a real connection that later drops
            raise aiohttp.ClientConnectionError("dropped")
        if attempts >= 4:
            ws._running = False
        raise aiohttp.ClientConnectionError("still down")

    with patch.object(ws, "_connect_and_listen", connect), patch(
        "custom_components.gardena_smart_system.api.websocket.asyncio.sleep",
        new=AsyncMock(),
    ):
        await ws._listen_loop()

    assert attempts == 4
    assert on_disconnected.call_count == 1
