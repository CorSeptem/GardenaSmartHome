# Gardena Smart System - Home Assistant Integration

A modern Home Assistant custom component for the Gardena Smart System API v2.

## Features

- **Lawn mower** (Sileno): mowing/docked/paused/error states + start, dock, pause controls
- **Irrigation valves** (Irrigation Control, Water Control): open/close with duration
- **Soil sensors**: temperature (°C), humidity (%), light intensity (lux)
- **Binary sensors**: gateway connectivity, WebSocket connection status
- **Real-time updates** via WebSocket with automatic reconnection
- **Multi-location support**

## Prerequisites

1. Create an account at [Husqvarna Developer Portal](https://developer.husqvarnagroup.cloud/)
2. Create an application and connect the **Gardena Smart System API**
3. Note your **Application Key** (Client ID) and **Application Secret** (Client Secret)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → **⋮** (top right) → **Custom repositories**
3. Add this repository URL with category **Integration**
4. Search for "Gardena Smart System" and install
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/gardena_smart_system` folder to your `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **Gardena Smart System**
3. Enter your Application Key and Application Secret
4. The integration will discover all locations and devices automatically

## Supported Devices

| Device | HA Platform | States | Controls |
|--------|------------|--------|----------|
| Sileno Mower | `lawn_mower` | mowing, docked, paused, error | start, dock, pause |
| Irrigation Control | `valve` | open, closed | open (with duration), close |
| Water Control | `valve` | open, closed | open (with duration), close |
| Soil Sensor | `sensor` | temperature, humidity, light | — |
| Gateway | `binary_sensor` | online/offline | — |

## Actions

Besides the standard `lawn_mower.*` and `valve.*` actions, the integration registers
its own actions with a `duration` parameter (minutes):

| Action | Target | Notes |
|--------|--------|-------|
| `gardena_smart_system.start_mowing` | `lawn_mower` | `duration` optional; without it the mower follows its own schedule |
| `gardena_smart_system.dock_mower` | `lawn_mower` | Park until next scheduled task |
| `gardena_smart_system.pause_mower` | `lawn_mower` | Park until further notice (the API has no pause) |
| `gardena_smart_system.open_valve` | `valve` | `duration` optional, default 30 |
| `gardena_smart_system.close_valve` | `valve` | Stop until next scheduled task |
| `gardena_smart_system.pause_valve` / `unpause_valve` | `valve` | Pause / resume an active watering |

```yaml
action: gardena_smart_system.open_valve
target:
  entity_id: valve.stora_grasmattan
data:
  duration: 90
```

## Architecture

- **No external dependencies** — uses only `aiohttp` (built into HA)
- **WebSocket** for real-time push updates with exponential backoff reconnection
- **Proactive token refresh** — refreshes OAuth2 token 5 minutes before expiry
- **Non-blocking SSL** — SSL context created in executor thread
- **Proper cleanup** — all connections properly closed on unload

## Troubleshooting

### WebSocket disconnects
The integration automatically reconnects with exponential backoff (5s → 10s → 30s → 60s). Check the `binary_sensor` entities for connection status.

### Authentication errors
Verify your credentials at the [Husqvarna Developer Portal](https://developer.husqvarnagroup.cloud/). Ensure the Gardena Smart System API is connected to your application.

## License

MIT
