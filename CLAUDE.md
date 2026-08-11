# Gardena Smart System - Home Assistant Integration

## Project Goal
A HACS-compatible Home Assistant custom component for Gardena Smart System API v2. No external Python dependencies — only `aiohttp` (built into HA).

## Key Design Decisions
- **DEVICE objects from the real API have NO attributes.** Device name, modelType, and serial come from the COMMON service. The coordinator's `_process_included_data()` handles this.
- WebSocket per location with auto-reconnect (exponential backoff)
- Token refresh 5 minutes before expiry
- SSL context created in executor thread (non-blocking)
- **Token reuse:** config flow stores token + expiry in config entry data. Coordinator restores it via `auth.restore_token()` to avoid Husqvarna's simultaneous login rejection.
- **UnitOfIlluminance** not available in all HA versions — use string `"lx"` directly.

## What's Done
- Full integration: config flow, API layer (auth/client/websocket), coordinator, all entity platforms
- API smoke test script (`tests/smoke_test_api.py`)
- Fix: device attributes populated from COMMON service (not DEVICE)
- Fix: simultaneous login error — token passed from config flow to coordinator
- Fix: `UnitOfIlluminance` replaced with `"lx"` string for HA compatibility
- Published to HACS (exists in store as `CorSeptem/GardenaSmartHome`)

## What Remains
- Verify all entity platforms work with real devices
- Monitor for further HA compatibility issues

## Husqvarna Developer Portal
- Create app at developer.husqvarnagroup.net
- Connect **Gardena Smart System API** under "Connected APIs"
- **Application Key** = Client ID, **Application Secret** = Client Secret
- Redirect URL: `http://localhost` (not used, integration uses Client Credentials flow)
