"""Validates raw MQTT payloads against the project's message contract.
Kept separate from any MQTT code so it can be tested without a broker."""

import json
from datetime import datetime

MAX_MESSAGE_BYTES = 512
TEMPERATURE_RANGE = (-40, 125)
HUMIDITY_RANGE = (0, 100)


class ValidationError(ValueError):
    """Raised with a message explaining exactly what's wrong with a reading."""


def validate(raw: bytes) -> dict:
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ValidationError(f"message is {len(raw)} bytes, over the {MAX_MESSAGE_BYTES} byte limit")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValidationError(f"expected a JSON object, got {type(data).__name__}")

    if data.get("schema") != 1:
        raise ValidationError(f"unsupported schema {data.get('schema')!r}, expected 1")

    device_id = data.get("device_id")
    if not isinstance(device_id, str) or not device_id:
        raise ValidationError(f"device_id must be a non-empty string, got {device_id!r}")

    ts = data.get("ts")
    if not isinstance(ts, str):
        raise ValidationError(f"ts must be a string, got {ts!r}")
    try:
        parsed_ts = datetime.fromisoformat(ts)
    except ValueError as exc:
        raise ValidationError(f"ts is not valid ISO 8601: {ts!r}") from exc
    if parsed_ts.tzinfo is None:
        raise ValidationError(f"ts is missing a timezone: {ts!r}")

    temperature_c = _validate_number(data, "temperature_c", *TEMPERATURE_RANGE)
    humidity_pct = _validate_number(data, "humidity_pct", *HUMIDITY_RANGE)

    return {
        "schema": 1,
        "device_id": device_id,
        "ts": ts,
        "temperature_c": temperature_c,
        "humidity_pct": humidity_pct,
    }


def _validate_number(data: dict, field: str, low: float, high: float) -> float:
    if field not in data:
        raise ValidationError(f"{field} is missing")
    value = data[field]
    # bool is a subclass of int in Python, so isinstance(True, (int, float))
    # is True - without this check, {"temperature_c": true} would validate.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be a number, got {value!r}")
    if not (low <= value <= high):
        raise ValidationError(f"{field} is {value}, outside the range {low}-{high}")
    return value
