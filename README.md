# X-Sense Home Security

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Home Assistant custom integration for **X-Sense** smoke, CO, heat, water, motion, door, temperature/humidity sensors, and base stations.

Built on [python-xsense](https://github.com/theosnel/python-xsense) by Theo Snelleman, adapted from his [Home Assistant integration prototype](https://github.com/theosnel/homeassistant-core/tree/xsense/homeassistant/components/xsense).

## Features

- Cloud login with your X-Sense app credentials
- Automatic discovery of all houses, base stations, and paired devices
- **MQTT push updates** for alarms, battery, temperature, humidity, and connectivity
- **Polling fallback** every 5 minutes for devices that do not push over MQTT
- Per-device entities:
  - **Sensors** — battery, temperature, humidity, CO ppm, Wi-Fi RSSI, RF level, firmware
  - **Binary sensors** — smoke/CO alarm, mute status, door open, end-of-life, alarm active
  - **Buttons** — device self-test (where supported)
- Re-authentication flow when your session expires

## Supported devices

Any device type mapped in [python-xsense](https://github.com/theosnel/python-xsense/blob/develop/xsense/entity_map.py), including:

| Type | Examples |
|------|----------|
| Base stations | SBS10, SBS50 |
| Smoke (Wi-Fi standalone) | **XS0B-iR**, XS01-WX |
| Smoke (RF / hub) | XS01-M, XS0B-MR, XP02S-MR |
| CO | XC01-M, XC04-WX, XC0C-iR |
| Smoke + CO combo (Wi-Fi) | **SC07-WX**, SC06-WX, XP0A-MR |

### Tested model notes

**SC07-WX** — Wi-Fi smoke and CO combo with display. No base station required. Exposes separate `Smoke alarm` and `CO alarm` binary sensors (alarm status `1` = smoke, `2` = CO, `3` = both), plus CO ppm, battery, mute, and mute button.

**XS0B-iR** (retail label may show as HS0B-IR) — Wi-Fi standalone smoke alarm using the X-Sense Home Security app. Exposes smoke alarm, battery, mute status, and self-test button. Does not use an SBS50 base station.
| Temperature/humidity | STH0A, STH0B, STH51 |
| Water | SWS51 |
| Motion | SMS0A |
| Door | SDS0A |
| Heat | XH02-M |
| Keypad | SKP0A |
| Mailbox | SMA51 |

## Install (HACS)

1. **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/james194zt/xsense-integration` as type **Integration**
3. Search **X-Sense Home Security** → Install
4. Restart Home Assistant

### Manual install

Copy `custom_components/xsense` into your Home Assistant `config/custom_components/` directory and restart.

## Setup

1. **Settings → Devices & services → Add integration → X-Sense Home Security**
2. Enter the email and password from your X-Sense / X-Sense Home Security app
3. All devices in your account appear automatically, grouped under their base station

### Tip: secondary account

Some users create a dedicated X-Sense account and share devices to it from the main account. This keeps HA credentials separate from your primary login.

## Automations

Smoke alarm triggered:

```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.kitchen_smoke_alarm_status
    to: "on"
action:
  - service: notify.mobile_app_your_phone
    data:
      message: "Smoke detected in the kitchen!"
```

Low battery:

```yaml
trigger:
  - platform: numeric_state
    entity_id: sensor.hallway_smoke_battery
    below: 20
action:
  - service: notify.persistent_notification
    data:
      message: "X-Sense hallway smoke detector battery is low"
```

## Architecture

```
X-Sense Cloud API  ──polling──►  Coordinator  ──►  HA entities
        │
        └── MQTT (WebSocket) ──push──►  Coordinator
```

The integration maintains one MQTT WebSocket connection per X-Sense cloud region (e.g. EU, US). Alarm and sensor state changes arrive in near real-time; the coordinator also polls every 5 minutes as a safety net.

## Local development

This repo is part of the HADashboard workspace. To test locally, the integration is also mirrored at:

```
homeassistant/custom_components/xsense/
```

## Credits

- [python-xsense](https://github.com/theosnel/python-xsense) — Theo Snelleman
- Original HA integration design — Theo Snelleman

## License

MIT
