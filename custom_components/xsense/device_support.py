"""Device model helpers and python-xsense compatibility patches."""

from __future__ import annotations

from typing import Any

from xsense import entity_map

# Retail / marketing names → API device type codes.
MODEL_LABELS: dict[str, str] = {
    "SC07-WX": "SC07-WX Smoke & CO Alarm",
    "XS0B-iR": "XS0B-iR Smart Smoke Alarm",
    "XS0B-MR": "XS0B-MR Smoke Alarm",
    "XS01-WX": "XS01-WX Smoke Alarm",
    "XS01-M": "XS01-M Smoke Alarm",
}

# Combo detectors report alarmStatus as 1=smoke, 2=CO, 3=both (MQTT events and shadows).
COMBO_MODELS = frozenset({"SC06-WX", "SC07-WX", "SC07-MR", "XP0A-MR"})

# Standalone Wi-Fi alarms that register as their own station in the X-Sense cloud.
STANDALONE_WIFI_MODELS = frozenset(
    {"SC07-WX", "XC04-WX", "XS01-WX", "XS0B-iR", "XS03-WX"}
)

SMOKE_MODELS = frozenset(
    {
        "XS01-M",
        "XS01-WX",
        "XS03-WX",
        "XS03-iWX",
        "XS0B-MR",
        "XS0B-iR",
        "XP02S-MR",
        "XS0D-MR",
    }
)


def model_label(device_type: str | None) -> str:
    """Return a friendly model name for the device registry."""
    if not device_type:
        return "X-Sense Device"
    return MODEL_LABELS.get(device_type, device_type)


def _alarm_status_value(data: dict[str, Any]) -> int | bool | None:
    """Return alarm status in a normalized form."""
    if "alarmStatus" not in data:
        return None
    value = data["alarmStatus"]
    if isinstance(value, bool):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def smoke_alarm_active(data: dict[str, Any]) -> bool:
    """Whether a smoke alarm is active."""
    status = _alarm_status_value(data)
    if status is None:
        return False
    if isinstance(status, bool):
        return status
    return status in (1, 3)


def co_alarm_active(data: dict[str, Any]) -> bool:
    """Whether a CO alarm is active."""
    status = _alarm_status_value(data)
    if status is None:
        return False
    if isinstance(status, bool):
        return False
    return status in (2, 3)


def has_smoke_alarm_entity(entity) -> bool:
    """Whether to expose a smoke alarm binary sensor."""
    return "alarmStatus" in entity.data or entity.type in COMBO_MODELS | SMOKE_MODELS


def has_co_alarm_entity(entity) -> bool:
    """Whether to expose a CO alarm binary sensor."""
    if entity.type in COMBO_MODELS:
        return "alarmStatus" in entity.data or "coPpm" in entity.data
    return "coPpm" in entity.data or entity.type.startswith("XC")


def patch_xsense_library() -> None:
    """Extend python-xsense with models missing from upstream entity_map."""
    import xsense.mapping as mapping

    if "XS0B-iR" not in entity_map.entities:
        entity_map.entities["XS0B-iR"] = {
            "type": entity_map.EntityType.SMOKE,
            "actions": [
                entity_map.TestAction(),
            ],
        }

    # Preserve numeric alarmStatus for combo detectors (upstream maps it to bool).
    original_map_values = mapping.map_values

    def map_values(device_type: str, data: dict[str, Any]) -> dict[str, Any]:
        raw_alarm = data.get("alarmStatus")
        mapped = original_map_values(device_type, data)
        if device_type in COMBO_MODELS and raw_alarm is not None:
            try:
                mapped["alarmStatus"] = int(raw_alarm)
            except (TypeError, ValueError):
                mapped["alarmStatus"] = raw_alarm
        return mapped

    mapping.map_values = map_values
