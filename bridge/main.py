"""Bridge: subscribes to sensor topics, validates every message against the
contract, forwards good readings, dead-letters bad ones with a reason."""

import json
import logging
import os
import signal
import time

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from validator import ValidationError, validate

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bridge")

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
SENSOR_TOPIC_FILTER = "telemetry/#"
DEAD_LETTER_TOPIC = "dead-letter"

_shutdown = False
_counts = {"valid": 0, "invalid": 0, "forward_failed": 0}


def _handle_signal(signum, frame):
    global _shutdown
    log.info("received signal %s, shutting down", signum)
    _shutdown = True


def forward(reading: dict) -> None:
    """Where a valid reading goes. Logging only for now - step 2.2 swaps
    this for an Azure IoT Hub publish without touching anything else here."""
    log.info("forwarded: %s", reading)


def _on_connect(client, userdata, flags, reason_code, properties):
    log.info("connected to %s:%s (reason=%s)", MQTT_HOST, MQTT_PORT, reason_code)
    # Subscribing here, not once at startup, means every reconnect
    # re-subscribes automatically - a fresh connection has no memory of
    # subscriptions made on a previous one.
    client.subscribe(SENSOR_TOPIC_FILTER, qos=1)


def _on_message(client, userdata, msg):
    try:
        reading = validate(msg.payload)
    except ValidationError as exc:
        _counts["invalid"] += 1
        dead_letter = {
            "topic": msg.topic,
            "reason": str(exc),
            "raw": msg.payload.decode(errors="replace"),
        }
        client.publish(DEAD_LETTER_TOPIC, json.dumps(dead_letter), qos=1)
        log.warning("rejected message on %s: %s", msg.topic, exc)
        return

    _counts["valid"] += 1
    try:
        forward(reading)
    except Exception as exc:  # noqa: BLE001 - forwarding must never crash the bridge
        _counts["forward_failed"] += 1
        log.error("forward failed for %s: %s", reading, exc)


def _connect_with_retry(client: mqtt.Client) -> None:
    delay = 1
    while not _shutdown:
        try:
            client.connect(MQTT_HOST, MQTT_PORT)
            return
        except OSError as exc:
            log.warning("connect failed (%s), retrying in %ss", exc, delay)
            time.sleep(delay)
            delay = min(delay * 2, 30)


def main() -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = _on_connect
    client.on_message = _on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    _connect_with_retry(client)
    client.loop_start()

    last_report = time.monotonic()
    try:
        while not _shutdown:
            time.sleep(1)
            if time.monotonic() - last_report >= 60:
                log.info(
                    "seen so far: valid=%d invalid=%d forward_failed=%d",
                    _counts["valid"], _counts["invalid"], _counts["forward_failed"],
                )
                last_report = time.monotonic()
    finally:
        client.loop_stop()
        client.disconnect()
        log.info("disconnected, exiting")


if __name__ == "__main__":
    main()
