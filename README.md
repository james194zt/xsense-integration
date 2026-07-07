# X-Sense Home Security

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Home Assistant custom integration for **X-Sense** smoke alarms, CO detectors, combo units, base stations, and other devices linked to your X-Sense Home Security account.

Built on [python-xsense](https://github.com/theosnel/python-xsense) by Theo Snelleman, adapted from his [Home Assistant integration prototype](https://github.com/theosnel/homeassistant-core/tree/xsense/homeassistant/components/xsense).

# Screenshots

The main integration page, per account and a list of your devices.

<img width="1071" height="395" alt="image" src="https://github.com/user-attachments/assets/47eadcc0-03d1-4b44-8849-96855d66866f" />

Example of a devices page
<img width="1064" height="851" alt="image" src="https://github.com/user-attachments/assets/f15b7385-6439-452a-8465-32fece752f4a" />


## How it works

X-Sense devices are managed through the **X-Sense cloud**. There is no local LAN API — this integration talks to the same backend as the mobile app.

```
┌─────────────────┐     login / discovery      ┌──────────────────┐
│  Home Assistant │ ◄────────────────────────► │  X-Sense Cloud   │
│   (this addon)  │     REST API (polling)     │  api.x-sense-iot │
└────────┬────────┘                            └────────┬─────────┘
         │                                              │
         │         MQTT over WebSocket (push)           │
         └──────────────────────────────────────────────┘
                    AWS IoT (per region: EU, US, …)
```

On setup, the integration:

1. **Authenticates** with your X-Sense account (AWS Cognito, same as the app).
2. **Discovers** all houses, base stations, and paired devices in the account.
3. **Polls** device state from the cloud API every 5 minutes as a fallback.
4. **Connects** to the X-Sense MQTT servers for your region(s) and subscribes to device shadow and alarm event topics for near real-time updates.

Each physical device becomes a Home Assistant **device** with entities created only for data fields the device actually reports. Child sensors (e.g. smoke detectors paired to an SBS50) appear under their base station via the device hierarchy.

### Cloud dependency

This is a **cloud_push** integration. Home Assistant needs internet access to the X-Sense API and MQTT endpoints. Devices continue to work standalone and through the app if Home Assistant is offline; HA simply won't receive updates until connectivity returns.

## Features

- One-time setup via config flow (email + password)
- Automatic discovery of all devices in the linked account
- Real-time alarm and status updates over MQTT
- 5-minute polling fallback when a push update is missed
- Separate **smoke** and **CO** alarm binary sensors on combo detectors (e.g. SC07-WX)
- Battery, temperature, humidity, CO ppm, Wi-Fi/RF diagnostics where reported
- Self-test and mute buttons on supported models
- Re-authentication flow when the cloud session expires
- Diagnostics download for troubleshooting (credentials redacted)

## Requirements

- Home Assistant **2024.6** or newer
- [HACS](https://hacs.xyz/) (recommended) or manual install
- An X-Sense Home Security account with devices already set up in the app
- Outbound HTTPS and WSS access to X-Sense cloud endpoints

## Installation

### HACS (recommended)

1. Open **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/james194zt/xsense-integration` as type **Integration**
3. Search **X-Sense Home Security** → **Download**
4. Restart Home Assistant

### Manual

Copy the `custom_components/xsense` folder into your Home Assistant `config/custom_components/` directory and restart.

## Setup

### Recommended: use a secondary account

The X-Sense cloud allows only one active session per account. If Home Assistant and the mobile app share the same login, you may get logged out of one or the other.

The recommended approach:

1. Create a **second X-Sense account** (separate email).
2. In the X-Sense app on your main account, **share** your devices/house with the secondary account.
3. In Home Assistant, add the integration using the **secondary account** credentials.

Device management (pairing, removal, firmware, sharing) stays in the app on your main account.

### Add the integration

1. **Settings → Devices & services → Add integration**
2. Search for **X-Sense Home Security**
3. Enter the email and password for your (secondary) X-Sense account
4. Devices appear automatically after the first sync

If setup fails, remove the entry, update to the latest version, restart Home Assistant, and try again. Check **Settings → System → Logs** and filter for `xsense` if problems persist.

## Supported devices

Entities are created for whatever fields each device reports. The integration supports any device type mapped in [python-xsense](https://github.com/theosnel/python-xsense/blob/develop/xsense/entity_map.py).

| Category | Models |
|----------|--------|
| Base stations | SBS10, SBS50 |
| Smoke (Wi-Fi standalone) | XS01-WX, **XS0B-iR** |
| Smoke (RF / via hub) | XS01-M, XS0B-MR, XP02S-MR |
| CO | XC01-M, XC04-WX, XC0C-iR |
| Smoke + CO combo | **SC07-WX**, SC06-WX, XP0A-MR |
| Temperature / humidity | STH0A, STH0B, STH51 |
| Water leak | SWS51 |
| Motion | SMS0A |
| Door | SDS0A |
| Heat | XH02-M |
| Keypad | SKP0A |
| Mailbox | SMA51 |

### Confirmed working

| Model | Notes |
|-------|-------|
| **SC07-WX** | Wi-Fi smoke + CO combo with display. No base station. Separate smoke/CO alarm sensors, CO ppm, battery, mute button. |
| **XS0B-iR** | Wi-Fi standalone smoke alarm (retail label may show **HS0B-IR**). Smoke alarm, battery, mute status, self-test. No SBS50. |

Combo detectors use numeric alarm status: `1` = smoke, `2` = CO, `3` = both. The integration exposes these as separate `binary_sensor.*_smoke_alarm` and `binary_sensor.*_co_alarm` entities.

## Entities

Entities are only created when the device reports the underlying field.

### Binary sensors

| Entity | Description |
|--------|-------------|
| Smoke | Smoke detection active |
| CO alarm | Carbon monoxide detection active (combo / CO devices) |
| Muted | Alarm is currently silenced |
| Status | Device status (e.g. end-of-life warning) |
| Alarm active | Station-level alarm activation |
| Door | Door open (door sensors) |
| Connected | MQTT cloud link (diagnostic, per station) |

### Sensors

| Entity | Description |
|--------|-------------|
| Battery | Battery level (%) |
| Temperature | Temperature (°C) |
| Humidity | Relative humidity (%) |
| CO | CO concentration (ppm) |
| Wi-Fi signal | RSSI (dBm) |
| Wi-Fi SSID | Connected network name |
| RF level | Radio signal quality (no signal / weak / moderate / good) |
| Software version | Firmware version |
| IP address | Device IP (where reported) |
| Alarm / voice volume | Volume levels (where reported) |

### Buttons

| Entity | Description |
|--------|-------------|
| Test | Trigger device self-test (where supported) |
| Mute | Silence alarm (where supported) |

## Automations

### Smoke alarm

```yaml
alias: X-Sense smoke alarm notification
trigger:
  - platform: state
    entity_id: binary_sensor.kitchen_smoke_alarm
    to: "on"
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "Smoke alarm"
      message: "Smoke detected in the kitchen!"
```

### CO alarm (combo detectors)

```yaml
alias: X-Sense CO alarm notification
trigger:
  - platform: state
    entity_id: binary_sensor.hallway_co_alarm
    to: "on"
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "CO alarm"
      message: "Carbon monoxide detected in the hallway!"
```

### Low battery

```yaml
alias: X-Sense low battery
trigger:
  - platform: numeric_state
    entity_id: sensor.bedroom_smoke_battery
    below: 20
action:
  - service: notify.persistent_notification
    data:
      message: "X-Sense bedroom smoke detector battery is low"
```

Replace entity IDs with the ones shown under **Settings → Devices & services → X-Sense Home Security**.

## Troubleshooting

| Symptom | Things to try |
|---------|----------------|
| Setup fails with *invalid auth* | Check email/password. Use a secondary account if the main account is logged in elsewhere. |
| Setup fails with *cannot connect* | Check HA has internet access. X-Sense API may be temporarily unavailable. |
| Integration shows *Failed setup, will retry* | Update to the latest version, restart HA, remove and re-add the integration. Check logs for `xsense`. |
| Devices missing | Confirm they appear in the X-Sense app on the same account. Shared devices must be shared with the HA account. |
| Stale values | MQTT may have disconnected; check the **Connected** diagnostic sensor. Polling refreshes every 5 minutes regardless. |
| Logged out of the app | Use a dedicated secondary account for Home Assistant (see Setup above). |

Download diagnostics from **Settings → Devices & services → X-Sense → ⋮ → Download diagnostics** when reporting issues on GitHub.

## Limitations

- **Cloud only** — no local control without internet
- **Read-focused** — alarm mute and self-test are supported where the cloud API allows; arm/disarm and full security-system control are not implemented
- **Unofficial** — uses a reverse-engineered API; X-Sense may change their cloud at any time
- **Entity coverage** — only fields reported by the cloud/MQTT are exposed; if the app shows a value HA doesn't, open an issue with diagnostics

## Contributing

Issues and pull requests welcome at [github.com/james194zt/xsense-integration](https://github.com/james194zt/xsense-integration).

When reporting a problem, include your Home Assistant version, integration version, device model(s), and diagnostics output.

## Credits

- [python-xsense](https://github.com/theosnel/python-xsense) — Theo Snelleman
- Original Home Assistant integration design — Theo Snelleman
- [Jarnsen/ha-xsense-component_test](https://github.com/Jarnsen/ha-xsense-component_test) — community reference implementation

## License

MIT
