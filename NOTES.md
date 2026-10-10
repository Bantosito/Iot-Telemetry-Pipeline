# Build notes

Answer each step's questions here, in your own words, before moving to the next step.

## Step X.Y — <name>
Date: 28.9.2026
What I built:
What surprised me / what broke:
Answers to the questions:
1.2 What do + and # mean in a topic subscription? What are QoS 0/1/2, and which fits sensor readings? Why is anonymous access dangerous if the broker were internet-reachable?: 

"#" means subscribe to anything + is a wildcards which can replace one  serche level. QoS quality of serviceagreement between publisher and a broker and subscriber where 0 is the loswest no expectation of acknowledge, 1 messege is sent until it receives puback message from receiver and 2 where it mathes exact four part handshake, publish, pubrec, pubrel pubcomp. Both 0 and 1 fits this kind of sensor as the data comes every 30 seconds and is not operations crititcal. Qos 1 should hovewer be chosen as silent data loss should be prevented therefore at least once choice will be prevented. Possible duplicates coming for the fact that the publisher will send the messae for as long as it will receive acknowledgemnt message which can sometimes lead tu duplicates for example during delays. It is hovewer cheaper the pos, These duplicates should be accountend for in the database desgin.

Anonymous access is dangerouse when rechable over the internet as any device could send unwanted messages that would indexed

1.3 Why 30 seconds specifically (work it out from the 8,000 msg/day free-tier limit)? Why read settings from env vars instead of hardcoding? What does the script do when asked to stop?:

    30 seconds message frequency is done to not go over the day limit of 8000msgs per day as there. It only accounts for 36%  of  dailylimit so there can be more devices aadded in the future. 

    The script nejaces differently in different places without code change. For example fake esp32 and real esp or local instance, docker instance and azure instance in the future. Env variables keep anythign secret out of source code.

    If you mean main.py it stoops the loop disconects and logs that 

1.4 Questions

Hints (kept for reference):
1. Why validate at home rather than only in the cloud? — Look at the README's message contract section (the 512-byte limit and the IoT Hub free-tier note right below the contract table). Also think about what you already built: the dead-letter topic exists entirely locally, before anything touches Azure. Ask yourself what a bad message would cost if it only got caught after being sent to the cloud.
2. Why should one bad message never crash the bridge? — Open bridge/main.py and look at _on_message. Notice there are two separate try/except blocks (one around validate(), one around forward()) instead of one big one. Ask: what happens to message #48 through #2880 that day if message #47 throws an unhandled exception and kills the process?
3. If the bridge restarts, does it miss messages? — This one you can actually test rather than reason about. In the playground: start the broker and bridge, then stop the bridge, publish a couple of messages by hand with mosquitto_pub while it's down, then restart the bridge and watch whether they ever show up. Then look at bridge/main.py's client.connect(...) call and compare it to the paho-mqtt docs' section on sessions / clean_start — that's the concept that explains what you'll observe.
4. Why subscribe inside on_connect rather than once at startup? — You already have this one from our earlier conversation about reconnects; just restate it in your own words in NOTES.md.

My answers:

1. Why validate at home (in the bridge) rather than only in the cloud?

Validating at home serves primarily the free tier Azure IOT limits that accepts 512 byte messages. Handling data at home assures that the messeges send follow the message contract. It also handles the invalid messages that instead of being discarded are send into deead letter topic with a reason for rejection, for any further diagnostics. 

Gate passed — Q2 and Q3 could use a bit more "why" depth (single-process failure mode, and no persistence/queuing while the bridge is down), 

2. Why should one bad message never crash the bridge?

A bad message will not crash the bridge as there are two try/execpt blocks. One when vlaidating the message (This will create and publish a dead letter with raw content and reason for rejection if it doesnt pass) and second on forwarding. If the message passes validation but still fails during forwarding it will trigger an exeption and log itself.

3. If the bridge restarts, does it miss messages?
-Yes it does, the bridge does not receive lost messages when shut down/reseted.

4. Why subscribe inside the on_connect callback rather than once at startup? (I already gave you the answer to this one above — re-state it in your own words.)
-Subsctibing in the on_connect assures that subcriptions are declared every time a reconnect happens both when starting happens and when it lost conncection to the mqtt broker.


What I'd do differently:

(shutdown-behavior answer still open — the sensor's _handle_signal / while-loop / finally-block walkthrough from chat)

## Playground observations — 29.9.2026

**Setup:** broker + bridge running, a fourth terminal subscribed to everything (`mosquitto_sub -t '#'`), then a *second* fake sensor process started without overriding `DEVICE_ID` — so it also defaulted to `sensor-01`.

**What happened:** both sensor processes published to the exact same topic (`telemetry/sensor-01`) under the same `device_id`. Neither the broker nor the bridge distinguished them. The broker has no concept of topic ownership — a topic is just a string, anyone connected can publish to it. The bridge's `validate()` only checks that `device_id` is a non-empty string; it never checks that it matches who's actually connected. Downstream, the two processes' readings were completely indistinguishable — interleaved, unattributable, no way to tell which one was "real."

**Why this matters:** same root cause as the anonymous-access risk from 1.2 — nothing on the wire proves who's sending a message. `device_id` is 100% self-declared in the payload right now, enforced by nothing. Anyone who can reach the broker can claim to be any device, including one that already exists (device spoofing).

**Where this gets fixed:** Azure IoT Hub (step 2.2, not built yet) gives each device its own identity and credentials — the *connection itself* is authenticated, not just a field in the JSON payload. That closes the broker-level gap. Worth digging into properly when we get there: even with per-device auth, it's still worth checking that the authenticated identity matches the `device_id` claimed *inside* the message — otherwise a legitimately-connected device could still spoof a different device's `device_id` in its payload. **Flagged to dig deeper at step 2.2.**

**MQTT keep-alive (the "ping back and forth" noticed on the bridge's connection):** on connect, a client negotiates a keep-alive interval with the broker (paho-mqtt defaults to 60s). If no other traffic passes in that window, the client sends a PINGREQ and the broker replies PINGRESP — a heartbeat with no payload, just proving the connection is still alive. If the broker hears nothing at all (not even a ping) for 1.5x the keep-alive interval, it assumes the client is dead and closes the connection — and would fire a Last Will message if one were configured (this project doesn't use one yet). That's how the broker tells "genuinely dead" apart from "quiet because there's nothing new to publish."

## Step 1.5 — Tests
Date: 6.10.2026

What I built:
- `tests/test_validator.py`: 32 tests for `bridge/validator.py`.
- `pyproject.toml`: tells pytest where the tests are (`tests/`) and where to import `validator` from (`bridge/`).

### Testing from zero: what a test even is

A test is a small function that **runs your code with a known input and checks the output is what you expect**. If the check fails, pytest reports it in red. That's all it is.

```python
def test_valid_reading_is_returned_unchanged():
    reading = _valid()
    assert validate(_encode(reading)) == reading
```

- The function name starts with `test_`. That's how pytest finds it: it scans `tests/` for files named `test_*.py` and runs every function in them whose name starts with `test_`.
- `assert <something true>` is the check. If the expression is false, the test fails and pytest shows you both sides of the comparison.
- No `if __name__ == "__main__"` and no `main()`. pytest calls the functions itself.

**Why bother?** Without tests, the only way to know the validator still works after a change is to start the broker, bridge and sensor and watch logs by eye. With tests, one command checks all 32 cases in 0.02 seconds. That lets you change code "without fear" (the README's phrase). If you break a rule, you find out immediately, not three weeks later in Azure.

### Running them

In a terminal with the venv active, from the project root:

```
pytest        # dots = passed, F = failed, summary at the end
pytest -v     # one line per test, with its name; nicer for learning
pytest -q     # quiet: just dots and the count
```

What I ran (from my own shell, which needs setup every time):
```
cd /Users/antoniratajczyk/Desktop/Project && source .venv/bin/activate && python -m pytest -q 2>&1 | tail -8
```
- `cd ...`: go to the project folder, so pytest finds `pyproject.toml`.
- `&&`: run the next command only if the previous one succeeded.
- `source .venv/bin/activate`: switch to the project's Python, the one with pytest installed.
- `python -m pytest`: run pytest *through that Python*. It's safer than plain `pytest`, which could pick up a different install.
- `-q`: quiet output.
- `2>&1`: merge error output into normal output.
- `| tail -8`: show only the last 8 lines. That was just for my screen space.

Result: `32 passed in 0.02s`.

### How the test file is built

**1. Helpers that build test data.**
```python
_valid()                      # one known-good reading
_valid(temperature_c=999)     # the same reading with ONE field changed
_without("ts")                # the same reading with ONE field removed
_encode(data)                 # dict -> JSON bytes, like MQTT delivers
```
Every bad message is "a good message with exactly one thing wrong." So when a test fails, you know exactly which rule is responsible: nothing else about the message was off.

**2. Tests that good messages are ACCEPTED.**
- A normal reading comes back unchanged.
- The edges of the ranges are allowed: temperature exactly -40 and exactly 125, plus whole numbers like `21` (not only `21.0`).
- A non-UTC timezone (`+02:00`) is fine. The contract says "with a timezone", not "in UTC".
- A message of exactly 512 bytes is accepted (only *over* 512 is rejected).

Why test acceptance at all? A validator that rejected *everything* would pass every "reject" test. The acceptance tests prove it isn't too strict. The edges are where bugs hide: writing `<` where you meant `<=` silently rejects exactly 125°C.

**3. One parametrised test for all the ways a message can be WRONG (24 cases).**
```python
@pytest.mark.parametrize(("raw", "reason"), [
    (b"not even json {",                "not valid JSON"),
    (_encode(_valid(schema=2)),         "unsupported schema"),
    (_encode(_valid(temperature_c=True)), "temperature_c must be a number"),
    ...
])
def test_invalid_messages_rejected_with_reason(raw, reason):
    with pytest.raises(ValidationError, match=reason):
        validate(raw)
```
- `@pytest.mark.parametrize` = "run this one test function once per row in this list." There are 24 rows, so pytest counts 24 separate tests. That's why 6 functions add up to 32 tests.
- `pytest.raises(ValidationError, match=reason)` = "this code MUST raise a `ValidationError`, and its message must contain `reason`." If no error is raised, or a different one is, or the message is wrong, the test fails.
- Why check the message and not just "it raised"? The reason text ends up on the dead-letter topic, and it's what you'll read when diagnosing a broken sensor. A wrong reason would send you looking in the wrong place.

The cases cover everything the README lists:
| Group | Cases |
|---|---|
| not JSON / not an object | garbage text, empty bytes, a JSON list, a JSON string |
| schema | missing, `2`, `"1"` (a string, not a number) |
| device_id | missing, empty `""`, a number `42` |
| timestamp | missing, a number, `"yesterday"`, no timezone |
| missing values | no `temperature_c`, no `humidity_pct` |
| not numbers | `"warm"`, `null`, `true`, `false` |
| out of range | -40.1, 999, humidity -1, humidity 100.5 |

**The `true` case.** In Python, `True` is secretly the integer `1` (`bool` is a subclass of `int`). So without a special check, `{"temperature_c": true}` would pass as "a number, 1 degree". The validator rejects booleans on purpose, and two tests guard that decision.

**4. The size test.**
It pads an otherwise *valid* message past 512 bytes. If the oversized message were also broken in some other way, the test might pass for the wrong reason. Keeping everything else valid proves the size rule *alone* rejects it.

### Proving the tests actually work

The README's "done when" asks for this: a test that can never fail proves nothing. So I broke the validator on purpose by deleting the `bool` check:

```
if isinstance(value, bool) or not isinstance(value, (int, float)):   # real
if not isinstance(value, (int, float)):                               # broken
```

Result: `2 failed, 30 passed`. Exactly the `true` and `false` tests went red, and pytest named the exact input that failed. Then `git checkout bridge/validator.py` restored the real file (it throws away uncommitted changes to that file), and all 32 passed again.

This "break the code, check a test catches it" idea is a lightweight version of **mutation testing**.

### Why only the validator, not the MQTT part

`validate()` is a **pure function**: bytes go in, a reading or an error comes out. No network, no broker, no clock, no randomness. So its tests are:
- **fast**: 0.02s;
- **deterministic**: same result every run, on any machine, including GitHub's CI in step 1.7;
- **about my code**: they test my rules, not Mosquitto's or paho's.

Testing the MQTT connection would need a running broker. It would be slow, could fail at random (port busy, timing), and would mostly test other people's libraries. This is the payoff from step 1.4's decision to keep `validate()` in its own file, away from `main.py`.

### What happens next with these tests

Step 1.7 (CI) will run `pytest` automatically on every push to GitHub. If a future change loosens or breaks a rule, the push turns red before the code goes anywhere near Azure.

What surprised me / what broke:

Answers to the questions (in my own words):

1. Why test the validation function but not the MQTT connection?
We are just testing functions, testing of a mqtt would require broker/networking and would test someone elses code. Here we are testing my code, my functions and how they work under wariety of input not already existing and maintained code

2. What's a parametrised test, and why is it useful here?
Parametrised test allows to run same test with differemt parameters testing all edge and specific input-output cases for a certain test. It is useful for the validator test as we can test diffrrent sent temperatures or various messasgee types and whether rejection they return is correct.

What I'd do differently: