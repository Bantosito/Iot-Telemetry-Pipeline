# Playground — running and poking at the pipeline

What exists so far: a broker, a fake sensor, and a bridge. This doc is for
running them yourself and breaking things on purpose so the design decisions
in the README stop being abstract. It's separate from `NOTES.md` — that file
is for answering the README's questions; this one is for hands-on exploring.

```
 sensor  ──MQTT──►  broker (Mosquitto)  ──MQTT──►  bridge  ──► forward() (just logs, for now)
                                                       │
                                                       └──► dead-letter topic (bad messages + why)
```

## One-time setup

```
cd /Users/antoniratajczyk/Desktop/Project
source .venv/bin/activate
```

Every command below assumes you're in this directory with the venv active.
If you open a new terminal tab, repeat `source .venv/bin/activate` there too
— it's a per-terminal setting, not a per-project one.

## Running it — one process per terminal

Open **three terminal tabs/windows**, all `cd`'d into the project root with
the venv activated.

**Terminal 1 — the broker:**
```
mosquitto -c mosquitto/config/mosquitto.conf -v
```
`-v` makes Mosquitto log every connect/subscribe/publish it sees — useful
while you're learning, noisy once you're not. Drop it later if you want.

**Terminal 2 — the bridge:**
```
python bridge/main.py
```
It'll retry-connect every few seconds if the broker isn't up yet (try
starting this one first, before the broker, and watch it retry with
increasing backoff — 1s, 2s, 4s... — instead of crashing).

**Terminal 3 — the fake sensor:**
```
python sensor/main.py
```
Defaults to one reading every 30 seconds, no broken messages. For faster
feedback while playing around, override the env vars inline instead of
editing `.env`:
```
PUBLISH_INTERVAL_SECONDS=2 BROKEN_MESSAGE_PROBABILITY=0.3 python sensor/main.py
```

Watch Terminal 2 — you'll see `forwarded: {...}` for good readings and
`rejected message on telemetry/sensor-01: <reason>` for bad ones.

## Terminal 4 — watch the wire directly

This bypasses the bridge entirely and shows you the raw MQTT traffic:
```
mosquitto_sub -t '#' -v
```
`#` subscribes to every topic. You'll see both `telemetry/sensor-01` (raw,
unvalidated — whatever the sensor sent, good or broken) and `dead-letter`
(only what the bridge rejected, with the reason attached). Narrow it to just
one:
```
mosquitto_sub -t 'dead-letter' -v
```

## Publish your own messages by hand

No need to go through the fake sensor at all — you're just publishing to a
topic, so anything can do it.

A valid reading:
```
mosquitto_pub -t telemetry/sensor-99 -m '{"schema":1,"device_id":"sensor-99","ts":"2026-09-29T12:00:00+00:00","temperature_c":22.5,"humidity_pct":50}'
```

An invalid one (missing `humidity_pct`) — watch it show up on `dead-letter`:
```
mosquitto_pub -t telemetry/sensor-99 -m '{"schema":1,"device_id":"sensor-99","ts":"2026-09-29T12:00:00+00:00","temperature_c":22.5}'
```

## Things worth trying

- **Two devices at once**: run a second sensor in another terminal with
  `DEVICE_ID=sensor-02 python sensor/main.py`. The bridge subscribes to
  `telemetry/#`, so both flow through the same bridge — check `bridge/main.py`'s
  `_on_message` to see it never looks at which device sent something before
  validating it.
- **Kill the broker while the sensor and bridge are still running.** Both
  should log connection failures and keep retrying rather than crashing.
  Restart the broker and watch them reconnect on their own — this is
  `reconnect_delay_set()` and (for the bridge) subscribing inside
  `_on_connect` doing their job.
- **Ctrl+C the sensor or bridge** and watch the log order: the "received
  signal" line, then (eventually) "disconnected, exiting" from the `finally`
  block. Time how long it actually takes — this ties back to the PEP 475
  discussion about `time.sleep()` not always returning early.
- **Push `BROKEN_MESSAGE_PROBABILITY` to `1.0`** on the sensor and watch
  every single message get dead-lettered — a quick way to see all five break
  modes (`not_json`, `missing_field`, `bad_timestamp`, `out_of_range`,
  `wrong_type`) cycle through.
- **Send a message over 512 bytes by hand** with `mosquitto_pub` and confirm
  the bridge rejects it for size before it even tries to parse the JSON.

## Stopping everything

`Ctrl+C` in each terminal, in any order. If something gets stuck in the
background, from the project root:
```
pkill -f "sensor/main.py"; pkill -f "bridge/main.py"; pkill -f "mosquitto -c mosquitto/config/mosquitto.conf"
```

## Where the logic actually lives

- `sensor/main.py` — generates readings, drifts them, occasionally breaks
  them on purpose.
- `bridge/validator.py` — the pure function that decides valid vs. invalid.
  No MQTT code here at all; this is what 1.5's tests will exercise directly.
- `bridge/main.py` — the MQTT plumbing: subscribe, call the validator,
  forward or dead-letter.
