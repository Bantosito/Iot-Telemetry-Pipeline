"""Fake sensor: publishes readings that follow the project's message contract
over MQTT, standing in for a real ESP32 until step 1.3b."""

import json
import logging
import os
import random
import signal
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sensor")

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
DEVICE_ID = os.environ.get("DEVICE_ID", "sensor-01")
PUBLISH_INTERVAL_SECONDS = float(os.environ.get("PUBLISH_INTERVAL_SECONDS", "30"))
BROKEN_MESSAGE_PROBABILITY = float(os.environ.get("BROKEN_MESSAGE_PROBABILITY", "0.0"))
TOPIC = f"telemetry/{DEVICE_ID}"

TEMP_MIN, TEMP_MAX = -40.0, 125.0
HUMIDITY_MIN, HUMIDITY_MAX = 0.0, 100.0

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    log.info("received signal %s, shutting down after this cycle", signum)
    _shutdown = True


def _drift(value: float, low: float, high: float, step: float) -> float:
    value += random.uniform(-step, step)
    return max(low, min(high, value))


def _valid_reading(temperature_c: float, humidity_pct: float) -> dict:
    return {
        "schema": 1,
        "device_id": DEVICE_ID,
        "ts": datetime.now(timezone.utc).isoformat(),
        "temperature_c": round(temperature_c, 2),
        "humidity_pct": round(humidity_pct, 2),
    }


def _broken_reading(temperature_c: float, humidity_pct: float) -> str:
    """Returns a raw payload that violates the contract in one of several
    ways, so the bridge's validator has real broken input to catch."""
    valid = _valid_reading(temperature_c, humidity_pct)
    kind = random.choice(
        ["not_json", "missing_field", "bad_timestamp", "out_of_range", "wrong_type"]
    )

    if kind == "not_json":
        return "not even json {"

    if kind == "missing_field":
        del valid["humidity_pct"]
        return json.dumps(valid)

    if kind == "bad_timestamp":
        valid["ts"] = "2026-09-28 12:00:00"  # no timezone
        return json.dumps(valid)

    if kind == "out_of_range":
        valid["temperature_c"] = 999.0
        return json.dumps(valid)

    if kind == "wrong_type":
        valid["temperature_c"] = "warm"
        return json.dumps(valid)

    return json.dumps(valid)  # unreachable, keeps type checkers happy


def _connect_with_retry(client: mqtt.Client) -> None:
    delay = 1
    while not _shutdown:
        try:
            client.connect(MQTT_HOST, MQTT_PORT)
            log.info("connected to %s:%s", MQTT_HOST, MQTT_PORT)
            return
        except OSError as exc:
            log.warning("connect failed (%s), retrying in %ss", exc, delay)
            time.sleep(delay)
            delay = min(delay * 2, 30)


def main() -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    _connect_with_retry(client)
    client.loop_start()

    temperature_c = 21.0
    humidity_pct = 45.0

    try:
        while not _shutdown:
            temperature_c = _drift(temperature_c, TEMP_MIN, TEMP_MAX, 0.3)
            humidity_pct = _drift(humidity_pct, HUMIDITY_MIN, HUMIDITY_MAX, 0.5)

            if random.random() < BROKEN_MESSAGE_PROBABILITY:
                payload = _broken_reading(temperature_c, humidity_pct)
            else:
                payload = json.dumps(_valid_reading(temperature_c, humidity_pct))

            client.publish(TOPIC, payload, qos=1)
            log.info("published to %s: %s", TOPIC, payload)

            time.sleep(PUBLISH_INTERVAL_SECONDS)
    finally:
        client.loop_stop()
        client.disconnect()
        log.info("disconnected, exiting")


if __name__ == "__main__":
    devceid = print("Select input")
    main()
