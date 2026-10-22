"""Tests for the message contract validator. No broker needed - validate()
takes bytes and either returns a reading or raises ValidationError."""

import json

import pytest

from validator import MAX_MESSAGE_BYTES, ValidationError, validate


def _valid(**overrides) -> dict:
    reading = {
        "schema": 1,
        "device_id": "sensor-01",
        "ts": "2026-09-23T12:00:00+00:00",
        "temperature_c": 21.5,
        "humidity_pct": 45.0,
    }
    reading.update(overrides)
    return reading


def _without(field: str) -> dict:
    reading = _valid()
    del reading[field]
    return reading


def _encode(data) -> bytes:
    return json.dumps(data).encode()


def test_valid_reading_is_returned_unchanged():
    reading = _valid()
    assert validate(_encode(reading)) == reading


@pytest.mark.parametrize(
    "value",
    [-40, 125, 0, 21],  # range edges are inclusive, ints are fine too
)
def test_temperature_boundaries_and_ints_accepted(value):
    assert validate(_encode(_valid(temperature_c=value)))["temperature_c"] == value


def test_non_utc_timezone_accepted():
    assert validate(_encode(_valid(ts="2026-09-23T14:00:00+02:00")))


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        # not JSON / not an object
        (b"not even json {", "not valid JSON"),
        (b"", "not valid JSON"),
        (_encode([1, 2, 3]), "expected a JSON object"),
        (_encode("hello"), "expected a JSON object"),
        # schema
        (_encode(_without("schema")), "unsupported schema"),
        (_encode(_valid(schema=2)), "unsupported schema"),
        (_encode(_valid(schema="1")), "unsupported schema"),
        # device_id
        (_encode(_without("device_id")), "device_id must be a non-empty string"),
        (_encode(_valid(device_id="")), "device_id must be a non-empty string"),
        (_encode(_valid(device_id=42)), "device_id must be a non-empty string"),
        # timestamp
        (_encode(_without("ts")), "ts must be a string"),
        (_encode(_valid(ts=1727092800)), "ts must be a string"),
        (_encode(_valid(ts="yesterday")), "not valid ISO 8601"),
        (_encode(_valid(ts="2026-09-23T12:00:00")), "missing a timezone"),
        # missing values
        (_encode(_without("temperature_c")), "temperature_c is missing"),
        (_encode(_without("humidity_pct")), "humidity_pct is missing"),
        # non-numeric values (bool is an int subclass in Python - rejected on purpose)
        (_encode(_valid(temperature_c="warm")), "temperature_c must be a number"),
        (_encode(_valid(temperature_c=None)), "temperature_c must be a number"),
        (_encode(_valid(temperature_c=True)), "temperature_c must be a number"),
        (_encode(_valid(humidity_pct=False)), "humidity_pct must be a number"),
        # out of range
        (_encode(_valid(temperature_c=-40.1)), "outside the range"),
        (_encode(_valid(temperature_c=999.0)), "outside the range"),
        (_encode(_valid(humidity_pct=-1)), "outside the range"),
        (_encode(_valid(humidity_pct=100.5)), "outside the range"),
    ],
)
def test_invalid_messages_rejected_with_reason(raw, reason):
    with pytest.raises(ValidationError, match=reason):
        validate(raw)


def test_oversized_message_rejected_before_parsing():
    # Valid JSON padded past the limit: proves the size check runs first and
    # doesn't depend on the payload being broken in some other way.
    reading = _valid(device_id="x" * MAX_MESSAGE_BYTES)
    raw = _encode(reading)
    assert len(raw) > MAX_MESSAGE_BYTES
    with pytest.raises(ValidationError, match="byte limit"):
        validate(raw)


def test_message_exactly_at_limit_accepted():
    base = _encode(_valid(device_id=""))
    padding = MAX_MESSAGE_BYTES - len(base)
    raw = _encode(_valid(device_id="x" * padding))
    assert len(raw) == MAX_MESSAGE_BYTES
    assert validate(raw)["device_id"] == "x" * padding


def test_deliberately_failing_for_ci_demo():
    assert 1 + 1 == 3
