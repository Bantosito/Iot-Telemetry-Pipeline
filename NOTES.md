# Build notes

*My learning log: raw notes, experiments and answers written step by step while building this project. The longer walkthroughs (e.g. "Testing from zero", "Docker from zero", the command explanations) were written by Claude when I asked for them; the answers under each step's questions are my own.*

*Easier to browse: the same content split into one file per topic is in [`notes/`](notes/README.md).*

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

### Exercises (hands-on, do them myself)

Run the stack with `docker compose up -d`, and in a second terminal watch the dead-letter topic: `mosquitto_sub -t dead-letter -v`. For each exercise: **predict first**, then run, then write one line about what happened.

**1. Be the sensor.** *(5 min)*
Publish by hand from the laptop:
```
mosquitto_pub -t telemetry/test -m '{"schema":1,"device_id":"me","ts":"2026-10-22T12:00:00+00:00","temperature_c":22,"humidity_pct":50}'
mosquitto_pub -t telemetry/test -m 'hello'
mosquitto_pub -t telemetry/test -m '{"schema":1,"device_id":"me","ts":"2026-10-22T12:00:00","temperature_c":22,"humidity_pct":50}'
```
Watch `docker compose logs -f bridge` and the dead-letter terminal.
- Which messages were forwarded and which dead-lettered? Is each reason clear enough that I'd know how to fix the sensor?

**2. Which topics does the bridge hear?** *(5 min)*
Publish the valid message from exercise 1 to each of these topics: `telemetry/a/b/c`, `telemetry`, `sensors/x`, `Telemetry/x`.
- Which ones reach the bridge? Explain each using the subscription `telemetry/#` (and remember topics are case-sensitive).

**3. The oversized message.** *(5 min)*
```
mosquitto_pub -t telemetry/test -m "$(python3 -c 'print("x" * 600)')"
```
(`python3 -c '...'` prints 600 x's; `$(...)` pastes that output into the command.)
- What reason appears on dead-letter? The payload isn't even JSON, so why does the reason talk about size and not JSON?

**4. Count check: valid + invalid = sent.** *(10 min)*
In `.env` set `PUBLISH_INTERVAL_SECONDS=2` and `BROKEN_MESSAGE_PROBABILITY=0.3`, then `docker compose up -d`. Wait ~2 minutes until the bridge logs a `seen so far:` line.
- Count the sensor's `published` lines (`docker compose logs sensor | grep -c published`). Does valid + invalid match? If not exactly, why might it be off by a few? (Hint: when did each counter start?)

**5. Make forwarding fail.** *(15 min)*
In `bridge/main.py`, make `forward()` fail sometimes, pretending Azure is down:
```python
def forward(reading: dict) -> None:
    if reading["temperature_c"] > 20:
        raise RuntimeError("pretend Azure is down")
    log.info("forwarded: %s", reading)
```
Rebuild and run: `docker compose up -d --build bridge`.
- Does the bridge crash? What does it log, and how does `forward_failed` change in the `seen so far` line?
- Which `try/except` saves it? (This is 1.4 Q2, seen live.)
- Undo: `git restore bridge/main.py`, then `docker compose up -d --build bridge`.

**6. Remove the safety net.** *(10 min)*
In `_on_message`, temporarily delete the `try/except ValidationError` around `validate()` (keep just `reading = validate(msg.payload)`). Rebuild, then send `hello` as in exercise 1.
- What happens to the bridge? Look at `docker compose logs bridge` and `docker compose ps`. Do valid readings sent right after still get through?
- Undo with `git restore bridge/main.py` and rebuild.

**7. Thinking exercise: the dead-letter loop.** *(5 min, no code)*
Imagine I renamed `DEAD_LETTER_TOPIC` to `telemetry/dead-letter`. The bridge subscribes to `telemetry/#`. What would happen the first time a bad message arrives? Why is the dead-letter topic deliberately *outside* `telemetry/`?


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

### Exercises (hands-on, do them myself)

All of these run on my laptop, with the venv active (`source .venv/bin/activate`), no Docker needed. **Predict first**, then run, then write one line about what happened. Always finish with `git restore bridge/validator.py tests/test_validator.py` and `pytest` all green.

**1. Get to know pytest's options.** *(10 min)*
```
pytest -v                   # every test by name
pytest -k timezone          # only tests whose name/ID contains "timezone"
pytest -k "bool or True"    # -k accepts simple logic
pytest -x                   # stop at the first failure
pytest --lf                 # re-run only the tests that failed last time
```
- How many tests does `-k timezone` select, and why those?

**2. Break the validator three ways.** *(15 min)*
Make ONE change at a time in `bridge/validator.py`, predict which tests will fail, run `pytest`, and compare. Undo after each with `git restore bridge/validator.py`.
- a) In `_validate_number`, change `low <= value <= high` to `low < value < high`.
- b) Delete the `if parsed_ts.tzinfo is None:` check (both lines).
- c) Change `MAX_MESSAGE_BYTES = 512` to `1024`.
- Did any change break *no* test? If so, that's a gap in my tests. Which test would catch it?

**3. Add my own test cases.** *(15 min)*
In `test_invalid_messages_rejected_with_reason`, add new rows to the list, e.g.:
```python
(_encode(_valid(humidity_pct="50")), "humidity_pct must be a number"),
(_encode(_valid(device_id="   ")), "device_id must be a non-empty string"),
```
- Run `pytest`. Does the second one pass? Is a device_id of three spaces OK? Should it be? (A real design question; there's no single right answer.)

**4. Discover a surprise: NaN.** *(10 min)*
Python's JSON parser accepts `NaN` ("not a number"), even though it isn't valid JSON. Try:
```
python -c "import sys; sys.path.insert(0, 'bridge'); from validator import validate; validate(b'{\"schema\":1,\"device_id\":\"a\",\"ts\":\"2026-10-22T12:00:00+00:00\",\"temperature_c\":NaN,\"humidity_pct\":50}')"
```
- Is it accepted or rejected? Read the error message: is the reason *accurate*? Why does a range check reject NaN? (Hint: in Python, every comparison with NaN is False.)
- Write a test for it. What reason *should* it give?

**5. Read a failure like a pro.** *(5 min)*
Change `test_valid_reading_is_returned_unchanged` to compare against `_valid(temperature_c=99)` instead of `reading`. Run `pytest`.
- Find, in pytest's output: the test name, the file and line, and the exact field that differs. How does pytest show the difference between two dicts?

**6. Test first, then code (TDD taste).** *(15 min, optional)*
Pretend there's a new rule: "`device_id` must be at most 64 characters."
1. Write the test first (a new row: `_valid(device_id="x" * 65)` with reason `"too long"`). Run `pytest` and see it fail. That's expected: the rule doesn't exist yet.
2. Add the rule to the validator. Run `pytest` and see green.
- Why is seeing the test fail *first* useful? (Same idea as the red CI run in 1.7.)
- This changes the contract, so undo both files with `git restore` afterwards, unless I decide the rule is worth keeping.

What I'd do differently:

## Step 1.6 — Docker Compose
Date: 10.10.2026

What I built:
- `sensor/Dockerfile` and `bridge/Dockeerfile`: recipes that package each program into an image.
- `docker-compose.yml`: starts broker, sensor and bridge together with one command.
- A fix in `sensor/main.py` so the sensor stops cleanly when Docker asks it to (found while testing, details below).
- `pyproject.toml`: a small ruff setting so the linter knows `validator` is my own code.

### Docker from zero: the four words you need

- **Image**: a frozen package containing an operating system base, Python, my libraries and my code. Built once, never changes. Like a class in Python, or an installer.
- **Container**: a running copy of an image. It has its own filesystem, processes and network address, isolated from my laptop. Like an object created from a class: you can run many containers from one image, and stop or delete them without touching the image.
- **Dockerfile**: the recipe for building an image, read top to bottom.
- **Docker Compose**: a file (`docker-compose.yml`) describing *several* containers that belong together, plus one command that starts them all on a shared private network.

Why bother? "It works on my machine" goes away. The image contains the exact Python version and libraries, so it runs the same on my laptop, on GitHub's CI (step 1.7), or on a Raspberry Pi later. And instead of three terminal tabs (the playground setup), it's one command.

Docker Desktop is the app that runs the Docker *engine* (the "daemon") in the background. The `docker` commands are just a remote control for that engine. If Docker Desktop isn't running, every command fails with "daemon not running". That was the first thing I hit.

### The Dockerfile, line by line (the sensor and bridge files are almost identical)

```dockerfile
FROM python:3.12-slim
```
Start from the official Python 3.12 image, "slim" variant: a minimal Debian Linux with Python, about 150 MB instead of about 1 GB for the full one. Smaller means faster to build and download, and less software in it that could have security holes.

```dockerfile
ENV PYTHONUNBUFFERED=1
```
Normally Python collects printed or logged output in a buffer and writes it out in chunks. In a container that means logs appear late, or are lost if the container is killed. This setting makes every log line appear immediately in `docker compose logs`.

```dockerfile
WORKDIR /app
```
"cd into /app inside the image, creating it if needed." Everything after this happens there.

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py validator.py ./
```
Copy the requirements in, install them, *then* copy the code. The order matters because **Docker caches each step (layer)**. If a step's input hasn't changed, Docker reuses the saved result. Code changes often, requirements rarely, so with this order editing `main.py` only re-runs the last COPY, and the slow `pip install` is reused from cache. If the code were copied first, every code edit would reinstall all libraries.
`--no-cache-dir` stops pip keeping a download cache inside the image. It would never be used again, so it just wastes space.
The sensor copies only `main.py`. The bridge also needs `validator.py`.

```dockerfile
RUN useradd --create-home --uid 10001 app
USER app
```
Create an ordinary user called `app` and switch to it. By default, containers run as **root** (all-powerful). If someone ever exploited a bug in my code, they'd be root inside the container, which makes escaping the container or doing damage easier. As `app` they can't install software or modify the system. My code doesn't need any of those powers, so it shouldn't have them (the principle of least privilege again, as in step 3.1). Verified with `docker compose exec bridge id`, which printed `uid=10001(app)`.

```dockerfile
CMD ["python", "main.py"]
```
The command the container runs when it starts. Written as a list (the "exec form") so Python runs as the container's main process (PID 1) and **receives stop signals directly**. With the plain-string form, a shell would sit in between and might not pass the signal on.

### docker-compose.yml, piece by piece

```yaml
services:
  mosquitto:
    image: eclipse-mosquitto:2
```
The broker uses a ready-made official image. Nothing to build. `:2` means "latest 2.x version".

```yaml
    volumes:
      - ./mosquitto/config/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
```
A **volume** (here a "bind mount") makes a file from my laptop appear inside the container. My existing config from step 1.2 is mounted where Mosquitto looks for its config. `:ro` = read-only: the container can read it but not change it.

```yaml
    ports:
      - "1883:1883"
```
**Port publishing**: "laptop port 1883 → container port 1883." The sensor and bridge don't need this; they talk to the broker over Compose's private network. It's only there so `mosquitto_sub -t '#' -v` on my laptop can still watch the traffic.

```yaml
    restart: unless-stopped
```
If the program crashes or Docker restarts, start the container again automatically, unless I stopped it on purpose.

```yaml
  sensor:
    build: ./sensor
```
Instead of a ready-made image, build one from the Dockerfile in `./sensor`.

```yaml
    env_file:
      - path: .env
        required: false
```
Load settings from `.env` if it exists. `required: false` because a clean checkout from GitHub has no `.env` (it's gitignored), and the README's "done when" requires that to work. The code's built-in defaults take over.

```yaml
    environment:
      MQTT_HOST: mosquitto
```
**The most important line.** In the playground, sensor and bridge used `localhost`. Inside a container, `localhost` means *that container itself*, and there's no broker in the sensor's container. Compose puts all services on a private network with a built-in DNS (name lookup), where **each service is reachable by its name**. So the broker is at `mosquitto`. This setting overrides whatever `.env` says.

```yaml
    depends_on:
      - mosquitto
```
Start the broker container *before* this one. It only guarantees start **order**, not that Mosquitto is actually ready to accept connections yet. That's fine, because both scripts already retry connecting (step 1.3/1.4 work paying off).

### Every command I ran, and why

**1. Check Docker is installed and running**
```
docker --version; docker compose version; docker info
```
The first two print versions. `docker info` asks the engine for its status: it fails if Docker Desktop isn't running. That was the case at first, so you started Docker Desktop.

**2. Check the Compose file before running anything**
```
docker compose config --quiet
```
Reads `docker-compose.yml` and checks it's valid without starting anything. `--quiet` = print nothing if it's fine.

**3. Build and start everything**
```
docker compose up --build -d
```
- `up`: create the network and containers and start them.
- `--build`: (re)build my images from the Dockerfiles first.
- `-d`: "detached", run in the background and give the terminal back. Without `-d`, logs stream in the terminal and Ctrl+C stops everything. That's nicer when you're running it yourself.

**First attempt failed:** `bind: address already in use` on port 1883. Something was already on that port. Investigated with:
```
lsof -nP -iTCP:1883 -sTCP:LISTEN 
```
`lsof` = "list open files". On macOS, network connections count as files. This shows which process is listening on TCP port 1883 (`-nP` = show numbers, not names, which is faster). The answer: my own playground broker (`mosquitto -c config/mosquitto.conf -v`), left running in a terminal tab since 6 October. Only one program can listen on a port at a time. **Lesson: run either the playground setup or Compose, never both.** After stopping the old broker, `docker compose up -d` worked.

**4. See what's running**
```
docker compose ps
docker compose logs sensor bridge
docker compose logs -f bridge          # -f = keep following live, Ctrl+C to stop watching
docker compose exec bridge id          # run a command inside a running container
```
`exec bridge id` printed `uid=10001(app)`: proof the bridge isn't running as root.

**5. Restart tests (the README's "recovers if you restart any single container")**
```
docker compose restart mosquitto
docker compose restart bridge
docker compose restart sensor
```
I timed each restart and read the logs afterwards.
- Broker restarted → the bridge logged `connected to mosquitto:1883` again about 10s later and kept forwarding. That's `reconnect_delay_set()` plus subscribing inside `_on_connect` doing their job, the exact thing 1.4 Q4 was about.
- Bridge restarted → it logged `received signal 15`, `disconnected, exiting`, then reconnected. Signal 15 = SIGTERM = "please stop", which is what Docker sends first.
- Sensor restarted → came back and kept publishing, **but** it never logged `disconnected, exiting`. Suspicious.

**6. Investigating the sensor**
```
docker compose stop sensor
docker inspect -f '{{.State.ExitCode}}' project-sensor-1
```
`docker inspect` shows everything Docker knows about a container. `-f` picks out one field. The exit code was **137**.

How to read exit codes: 0 = finished normally. **128 + N = killed by signal N.** 137 − 128 = 9 = **SIGKILL**, the "pull the plug" signal a program can't catch or clean up after.

### The bug: why Docker had to force-kill the sensor

How `docker stop` works: send SIGTERM ("please stop"), wait a grace period, and if the process is still running, send SIGKILL.

The sensor's loop was:
```python
while not _shutdown:
    ...publish...
    time.sleep(30)
```
The signal handler *did* run and set `_shutdown = True` (the log showed `received signal 15`). But Python then **goes back to sleeping for the rest of the 30 seconds**. Since Python 3.5, `time.sleep()` resumes after a signal handler instead of returning early (PEP 475). So the loop only noticed `_shutdown` after up to 30 seconds. Docker's grace period ran out first, and it pulled the plug. The `finally:` block (loop_stop, disconnect, "disconnected, exiting") never ran.

The bridge didn't have this problem because its loop sleeps only 1 second at a time.

Why it matters: a killed process doesn't disconnect cleanly, so the broker doesn't know it's gone until keep-alive times out. In real systems, a killed process can also lose half-written work. Every container stop or restart was ending in a forced kill.

Open question I noticed: Docker gave up after about 3 seconds, not the 10 seconds I expected as the default grace period. Worth checking why (Docker Desktop or Compose version settings?). It doesn't change the bug: even 10 seconds is shorter than a 30-second sleep.

### The fix

```python
_shutdown = threading.Event()

def _handle_signal(signum, frame):
    log.info("received signal %s, shutting down", signum)
    _shutdown.set()

while not _shutdown.is_set():
    ...publish...
    _shutdown.wait(PUBLISH_INTERVAL_SECONDS)
```
A `threading.Event` is a flag that something can *wait on*. `_shutdown.wait(30)` means "wait up to 30 seconds, **but return immediately if the flag gets set**." So it acts like `sleep(30)`, except a stop signal cuts it short. The connect-retry loop uses the same `wait()` instead of `time.sleep()`, so the sensor also stops promptly while it's still trying to reach the broker. `import time` was no longer used, so it was removed.

Re-tested after rebuilding (`docker compose up -d --build sensor`, which rebuilds and replaces only the sensor):
`stop took 1s, exit code 0`, and the log shows `received signal 15, shutting down` → `disconnected, exiting`. Clean.

### Lint fix (ruff)

```
ruff check sensor bridge tests
```
Ruff is the linter that CI will run in step 1.7. It found two things:
1. `import time` unused in the sensor, a leftover from the fix. Removed.
2. "Import block is un-sorted" in `bridge/main.py` and the tests. Ruff groups imports as standard library → third-party → my own code. It didn't know `validator` is my own module (it lives in `bridge/`, not an installed library), so it wanted it grouped with paho and dotenv. Fixed by telling it in `pyproject.toml`:
```toml
[tool.ruff.lint.isort]
known-first-party = ["validator"]
```
After that: `All checks passed!` and `32 passed` for the tests.

### Final checks (all passed)
- No `.env` file exists, so this *was* the clean-checkout scenario.
- All three containers up. The bridge restarts with exit code 0 and reconnects. A fresh sensor reading was `forwarded` within a second of restarting.

### How to run it myself
```
docker compose up --build          # everything, logs in this terminal, Ctrl+C stops all
docker compose up --build -d       # same, in the background
docker compose logs -f             # follow all logs (or: logs -f bridge)
docker compose restart sensor      # restart one service
docker compose down                # stop and remove containers + network (images stay)
mosquitto_sub -t '#' -v            # still works from the laptop, thanks to the published port
```
To change settings: `cp .env.example .env` and edit `.env`, e.g. `PUBLISH_INTERVAL_SECONDS=2` and `BROKEN_MESSAGE_PROBABILITY=0.3`, then `docker compose up -d` (Compose recreates the containers whose settings changed). Don't change `MQTT_HOST` there for Docker; Compose overrides it to `mosquitto` anyway.

Still open: the leftover `devceid = print("Select input")` at the bottom of `sensor/main.py` prints "Select input" in the sensor's container logs on every start. Decide whether to keep or remove it.

What surprised me / what broke:

Answers to the questions (in my own words):

1. Why can the bridge reach the broker at `mosquitto` instead of `localhost`?
The Bridge can reach mqtt in localhost at mosquitto because container has its own internal network and dns server that allows reaching services through their name so there is no need to call ip adress (localhost when done locally)

2. What's the difference between an image and a container?
An image is a package containing operating systems, software like python, Mqtt broker, and all the code, settings etc.. ready to be cloned and run as a container. It offers an unified way to store code and all dependecies needed to deply it seamlesly in any enviroment.

3. Why not run as root inside a container?

Running as a root in a container poses a risk to the container or even a system in case the code is expoited. According to the least privelage principle. The app doesn't require root privealge to run therefore it shouldn't have it. 

4. What does `depends_on` guarantee, and what doesn't it?
Depends on guarantees that service that other services depends on will be turned on first (mosquitto broker in our example). What it does not provide is assurring that dependand (ex. mosquito broker) will be fully running and the depending services will connect succesfully to it. 

### Exercises (hands-on, do them myself)

Start everything first with `docker compose up -d`. For each exercise: **predict what will happen before running it**, then run it and write one line about whether I was right. When finished: `docker compose up -d` again to get back to normal.

**1. Step inside a container.** *(10 min)*
```
docker compose exec bridge sh      # opens a shell INSIDE the bridge container
```
Inside it, try:
```
whoami                 # who am I in here?
pwd                    # where am I?
ls                     # which files are here, and why only these?
cat /etc/passwd        # find the "app" user the Dockerfile created
apt-get install curl   # try to install software
exit                   # leave the container
```
- Why does `apt-get` fail? Which Dockerfile line causes that, and is that good or bad?
- Compare `ls` here with `ls bridge/` on my laptop. Which files are missing, and why? (Hint: the `COPY` lines.)

**2. Prove `localhost` ≠ `mosquitto`.** *(5 min)*
```
docker compose exec bridge python -c "import socket; print(socket.gethostbyname('mosquitto'))"
docker compose exec bridge python -c "import socket; socket.create_connection(('localhost', 1883))"
docker compose exec bridge python -c "import socket; socket.create_connection(('mosquitto', 1883)); print('connected')"
```
- The first prints an IP address. Whose address is it, and who answered the name lookup?
- Why does the second one fail with "Connection refused"? (This is 1.6 Q1, proven by experiment.)

**3. One image, many containers.** *(10 min)*
```
docker images                              # the images: built once
docker compose up -d --scale sensor=3      # three containers from ONE sensor image
docker compose ps
docker compose logs -f bridge              # Ctrl+C to stop watching
```
- How many sensor images exist, and how many sensor containers? (This is 1.6 Q2.)
- All three use the same `DEVICE_ID`. What does the bridge's log look like? Which playground finding is this? (Hint: device spoofing, 29.9.)
- Back to normal: `docker compose up -d --scale sensor=1`.

**4. Watch the layer cache work.** *(10 min)*
1. Add a comment line anywhere in `sensor/main.py`, then run `docker compose build sensor`. Look for `CACHED` next to the `pip install` step.
2. Now add an empty line to the end of `sensor/requirements.txt` and build again.
- Which build was faster, and why? Which Dockerfile line order makes this possible?
- Undo both edits afterwards (`git restore sensor/main.py sensor/requirements.txt`).

**5. Settings via `.env`.** *(10 min)*
```
cp .env.example .env
```
In `.env` set `PUBLISH_INTERVAL_SECONDS=2` and `BROKEN_MESSAGE_PROBABILITY=0.3`, then:
```
docker compose up -d                    # Compose notices the change and recreates containers
mosquitto_sub -t dead-letter -v         # from the laptop: watch rejected messages
```
- Now also set `MQTT_HOST=localhost` in `.env` and run `docker compose up -d` again. Does it break? Why not? (Hint: the `environment:` block in `docker-compose.yml`.)
- Afterwards, put the interval back to 30. Is `.env` showing up in `git status`? Why not?

**6. `depends_on` and retries.** *(10 min)*
```
docker compose down                     # stop and remove everything
docker compose up -d bridge             # start ONLY the bridge
docker compose ps
```
- Did the broker start too, even though I only asked for the bridge? Which line caused that?
Now the opposite: broker down, bridge up.
```
docker compose stop mosquitto
docker compose logs -f bridge           # watch for ~30 seconds, Ctrl+C to stop
docker compose start mosquitto
```
- What does the bridge log while the broker is gone? How does the waiting time between retries grow? And what happens when the broker comes back? (This is 1.6 Q4 plus 1.4 Q4.)

**7. Recreate exit code 137 on purpose.** *(5 min)*
```
docker compose stop -t 0 sensor         # -t 0 = give it ZERO seconds to stop politely
docker inspect -f '{{.State.ExitCode}}' project-sensor-1
docker compose stop sensor              # normal stop, with a grace period
docker inspect -f '{{.State.ExitCode}}' project-sensor-1
docker compose start sensor
```
- Why 137 the first time and 0 the second? Which signal did the sensor get each time? (See "The bug" section above.)

**8. Does it restart by itself?** *(5 min)*
Stop the bridge's program from *inside* the container, the way a crash would:
```
docker compose exec bridge sh -c "kill 1"     # PID 1 = the main program (python main.py)
docker compose ps                              # run this a few times
```
- Did it come back on its own? Which line in `docker-compose.yml` is responsible?
- Then try `docker compose stop bridge` and wait. Does it come back this time? Why the difference? (Hint: the meaning of "unless-*stopped*".)

**9. Clean up and see what Docker stores.** *(5 min)*
```
docker compose down          # removes containers + network; images stay
docker images                # images are still there
docker system df             # how much disk Docker uses in total
docker compose up -d         # starts again quickly: no rebuild needed. Why?
```

What I'd do differently:

Notes: 
RUN useradd --create-home --uid 10001 app ~ where are we creating this user? Why?

What is yaml? /

Are we going to have te change docker enviroment / networking later on when we will be connecting to a real device in our local network and further out to azure?

### Answers to my notes (from Claude, 22.10.2026)

**Where are we creating the `app` user, and why?**
*Inside the image*, while it's being built. `RUN` executes a command in the image under construction, so `useradd` adds a line to the image's own `/etc/passwd` (Linux's list of users). The user does **not** exist on my Mac. It lives only inside the container, the same way a `pip install` in the Dockerfile doesn't install anything on my laptop.
- `--create-home` gives it a home folder (`/home/app`). Some tools expect one and fail without it.
- `--uid 10001`: Linux identifies users by number, not name. A high number avoids colliding with system users that already exist in the base image (0 = root, 1–999 = system accounts).
- `USER app` then switches every later step, and the running program, to that user.
- Why: by default a container runs as root. If my code were ever exploited, the attacker would be root inside the container, which makes escaping it or doing damage much easier. My scripts only need to read their own files and open network connections, so they get no more power than that (least privilege).
- Proof it worked: `docker compose exec bridge id` → `uid=10001(app)`.

**What is YAML?**
A text format for writing structured data (settings), designed to be easy for humans to read. It does the same job as JSON, which we already use for the messages, but without the braces and quotes:
```yaml
services:            # a key whose value is a nested block
  sensor:
    build: ./sensor  # key: value
    depends_on:
      - mosquitto    # "-" starts a list item
```
The same in JSON would be `{"services": {"sensor": {"build": "./sensor", "depends_on": ["mosquitto"]}}}`.
- **Indentation is the structure.** What's nested inside what is decided purely by how far a line is indented. Use spaces, never tabs. A wrong indent is the #1 YAML bug.
- `#` starts a comment (JSON can't have comments, which is one reason config files prefer YAML).
- It's everywhere in DevOps: Docker Compose, **GitHub Actions (step 1.7 is written in YAML)**, Kubernetes, dbt (week 4).

**Will Docker / networking need to change for the real ESP32 and for Azure?**
Two different directions, two different answers:

*1. ESP32 on the home network: yes, the broker must become reachable, but securely.*
- The ESP32 is a separate device on the Wi-Fi, outside the Compose network, so it can't use the name `mosquitto`. It will connect to the laptop's Wi-Fi IP address on port 1883.
- The published port was `"1883:1883"`, which (I found out while answering this) already exposed the broker to the **whole Wi-Fi** with anonymous access on. Changed to `"127.0.0.1:1883:1883"` (laptop only) until it's actually needed. Verified with `docker compose port mosquitto 1883` → `127.0.0.1:1883`.
- When the ESP32 arrives, do it in this order: (1) turn off anonymous access and give Mosquitto username/password logins (one per device, so a device's identity is tied to its login, not just the self-declared `device_id`), (2) only then open the port to the network again. Optionally (3) TLS (port 8883) so the Wi-Fi traffic is encrypted.
- Also: the laptop's Wi-Fi IP can change. A fixed IP (DHCP reservation on the router) or a hostname fixes that.

*2. Bridge → Azure: almost no networking change.*
- Inbound vs outbound is the key idea. The ESP32 case is **inbound** (something outside connecting *in* to the laptop, which needs an open port). Azure is **outbound**: the bridge connects *out* to IoT Hub over the internet, like a browser opening a website. Containers can make outbound connections by default, and the home router allows outgoing traffic, so no ports need opening.
- What changes is configuration and code, not networking: the IoT Hub connection string (a secret) goes into `.env`, which Compose already passes in via `env_file`, and `forward()` in `bridge/main.py` gets an IoT Hub destination (step 2.2).
- The connection to Azure is encrypted (TLS) and authenticated by the device credentials. That's why it's safe to go over the internet when the local broker isn't.

## Git and GitHub: explanation + terminal guide
Date: 22.10.2026 (written by Claude at my request, before pushing to GitHub for step 1.7)

### What git is

**Git is a time machine for a folder.** Every time I *commit*, git saves a snapshot of all tracked files, plus a message saying what changed and why, who made it, and when. I can look at any old snapshot, see exactly what changed between two of them, and undo mistakes.

It all lives in the hidden `.git` folder inside the project. Delete that folder and the history is gone; the files stay as they are now. `ls -a` shows it.

**Git and GitHub are not the same thing.**
- **Git** is the program on my laptop that keeps the history. It works fully offline.
- **GitHub** is a website that hosts a *copy* of the repository: a backup, a public portfolio, and a place where robots run things on my code (CI, step 1.7).
- The two are synced by hand: `git push` uploads my new commits, `git pull` downloads commits made elsewhere.

### The three places a change lives

```
 working folder  ──git add──►  staging area  ──git commit──►  local history  ──git push──►  GitHub
 (files I edit)                (what goes into                (.git folder)                 (origin)
                                the next commit)
```
1. **Working folder**: the files as I see them in VS Code. Editing changes only this.
2. **Staging area** (also called "the index"): a waiting room for the next commit. `git add` puts changes there. It exists so one commit can contain only *some* of my changes. That's how 1.6's code and the cleanups became separate commits.
3. **Local history**: `git commit` turns everything staged into a permanent snapshot.
4. **GitHub**: only gets commits when I `git push`.

### Key words

| Word | Meaning |
|---|---|
| repository (repo) | a project folder tracked by git, i.e. one with a `.git` inside |
| commit | one saved snapshot, with a message and a unique ID like `76b12e1` |
| branch | a named line of commits. Mine is `main`. Branches let you try something without touching `main` |
| remote | another copy of the repo somewhere else. `origin` = the standard name for the GitHub copy |
| push / pull | upload my commits to the remote / download theirs |
| clone | download a whole repo from GitHub to a new folder (what a "clean checkout" means) |
| `.gitignore` | list of files git should never track: `.env`, `.venv/`, `__pycache__/`... |
| HEAD | "where I am right now": usually the latest commit on my current branch |

### Everyday terminal workflow (90% of what I'll use)

```
git status                     # what changed? what's staged? ALWAYS run this first
git diff                       # exact line-by-line changes not yet staged
git add NOTES.md sensor/main.py   # stage specific files
git add .                      # stage everything changed (check git status first!)
git diff --staged              # review exactly what will be committed
git commit -m "Short summary of what now works"
git push                       # send new commits to GitHub
```
`git status` is safe and shows everything. Running it before and after each step is the habit that prevents mistakes like committing `.env`.

### Looking at history

```
git log --oneline              # one line per commit, newest first
git log --oneline -5           # just the last 5
git show 76b12e1               # what exactly changed in one commit
git log -p NOTES.md            # full history of one file, with changes
git blame sensor/main.py       # which commit last changed each line
```

### Undoing things (from safest to most dangerous)

```
git restore NOTES.md           # throw away my UNSTAGED edits to a file (gone for good!)
git restore --staged NOTES.md  # unstage a file, but keep my edits
git checkout bridge/validator.py   # older way to throw away edits; I used this in 1.5 to undo the deliberate break
git commit --amend             # fix the LAST commit's message or add a forgotten file (only before pushing!)
git revert 76b12e1             # make a NEW commit that undoes an old one: the safe way once pushed
```
Rule: **never rewrite commits that are already pushed** (`--amend`, `reset`, `rebase`), because GitHub and anyone who cloned it would disagree with my history. Once pushed, undo with `git revert`, which adds a new commit instead of erasing an old one.

And from 1.1: **a committed secret stays in the history forever**, even if a later commit deletes the file. If it ever happens, the fix is to change the secret, not to delete the file.

### Connecting to GitHub for the first time (step 1.7)

1. On github.com: **New repository**, Public, and **empty** (no README/.gitignore/license, or the first push conflicts with my local history).
2. Log in once from the terminal. Easiest is the GitHub CLI:
   ```
   brew install gh
   gh auth login                # choose GitHub.com → HTTPS → log in with browser
   ```
   GitHub no longer accepts my account password for `git push`. The alternatives are a personal access token or an SSH key.
3. Connect and upload:
   ```
   git remote add origin https://github.com/<me>/<repo>.git   # save the address as "origin"
   git remote -v                                              # check it
   git push -u origin main                                    # first push; -u remembers the link
   ```
4. From then on, after each commit, just `git push`.

### What becomes public when I push

Everything committed, in every version: all commit messages, dates and author name. My author email is already GitHub's private noreply address (`git config user.email` to check). NOT published: uncommitted changes, anything in `.gitignore` (`.env`, `.venv/`), and branches I don't push.

### Good commit habits (the history is part of the portfolio)

- **One logical change per commit**: "add tests" and "fix sensor shutdown" are separate commits when possible.
- **Message = what now works, not what I typed.** Summary line under about 70 characters, e.g. `Run the home half with Docker Compose (step 1.6)`. Then an empty line, then a body explaining *why* if it isn't obvious.
- **Commit at the end of each step** (README rule), so the history reads like the build guide.
- `git status` before every commit; never commit `.env`.

## Step 1.7 — CI (GitHub Actions)
Date: 22.10.2026

What I built:
- `.github/workflows/ci.yml`: the instructions GitHub follows on every push.
- The project is now on GitHub: https://github.com/Bantosito/Iot-Telemtr-Pipeline-Course
- A CI status badge at the top of `README.md`.

### CI from zero

**The problem CI solves.** Until now, checking the code meant *me* remembering to run `pytest` and `ruff` on *my* laptop before pushing. People forget. And "it passed on my laptop" can hide problems that only exist because of something on my laptop (a library I installed by hand, a file I never committed).

**CI = continuous integration**: every change gets checked automatically, the moment it's pushed. On every `git push`, GitHub:
1. starts a brand-new, empty Linux computer (a "runner") for a few minutes, free for public repos;
2. downloads my code onto it;
3. runs the steps listed in my workflow file: install, lint, test, build;
4. shows the result: **green ✓** if every step passed, **red ✗** if any failed. It shows next to the commit, in the **Actions** tab, and in the README badge.

Afterwards the runner is thrown away. Every run starts from scratch, so a pass really means "works on a clean machine", not "works on my laptop".

**Words:**
| Word | Meaning |
|---|---|
| GitHub Actions | GitHub's built-in CI system: the robot that runs the workflow |
| workflow | one YAML file in `.github/workflows/` describing *when* to run and *what* to run |
| trigger (`on:`) | the event that starts it: a push, a pull request, a schedule... |
| job | a group of steps that runs on its own runner (own fresh computer) |
| step | one command, or one ready-made "action", inside a job |
| action (`uses:`) | a reusable step someone else wrote, e.g. "download the repo" |
| runner | the temporary computer the job runs on (`ubuntu-latest` = Linux) |
| run | one execution of the workflow, e.g. "the run for commit 15a6ed1" |

### The workflow file, line by line

```yaml
name: CI
```
The name shown in the Actions tab and on the badge.

```yaml
on:
  push:
  pull_request:
```
**The trigger.** Run on every push to any branch, and on every pull request (someone proposing changes, e.g. from a fork), so their code is checked before I accept it.

```yaml
jobs:
  lint-and-test:
    runs-on: ubuntu-latest
```
The first job, named `lint-and-test`, on a fresh Ubuntu Linux computer.

```yaml
    steps:
      - uses: actions/checkout@v4
```
The runner starts empty, without even my code. This ready-made action does `git clone` of my repo onto it. `@v4` pins the action's version, so an update by its authors can't silently change my CI.

```yaml
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: requirements-dev.txt
```
Installs Python 3.12, the same version as my laptop and the Docker images. `cache: pip` saves downloaded libraries between runs (keyed on `requirements-dev.txt`), so later runs skip re-downloading them unless that file changes.

```yaml
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
```
`run:` = a normal terminal command, exactly what I'd type myself. Installs pytest, ruff, paho-mqtt and dotenv at the pinned versions.

```yaml
      - name: Lint (ruff)
        run: ruff check .
      - name: Test (pytest)
        run: pytest -v
```
The actual checks, the same commands I run locally. If a command fails (exit code not 0, same idea as exit code 137 in 1.6), the step turns red, the remaining steps are skipped, and the run fails.

```yaml
  build-images:
    needs: lint-and-test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build images
        run: docker compose build
```
A second job, on its own fresh computer. `needs: lint-and-test` means it only starts if the first job passed: no point building images from code that fails its checks. It builds both Docker images with the real Dockerfiles. Tests can't catch a broken Dockerfile, a file missing from a `COPY`, or a library that won't install on Linux, but a build can.

### What ruff is

**Ruff is a linter**: a tool that reads code *without running it* and flags likely mistakes and messy style. (Tests run the code; a linter only reads it.) Examples of what it catches:
- unused imports, e.g. the leftover `import time` in 1.6;
- variables that are used but never defined (a typo in a name), which would only crash at runtime otherwise;
- imports in a messy order (it wants: standard library → installed libraries → my own code).

It's very fast (written in Rust) and configured in `pyproject.toml`. Locally:
```
ruff check .          # list problems
ruff check . --fix    # fix the ones it safely can, automatically
```
In CI it guarantees nobody (including me in week 4) pushes code with these problems unnoticed.

### What I did, step by step, and why

The README's "done when" has three parts. Each one was proven on GitHub, not assumed.

**1. Pushed the project to GitHub (it was only on my laptop before).**
```
git remote add origin https://github.com/Bantosito/Iot-Telemtr-Pipeline-Course.git
git push -u origin main
```
The push itself started the first CI run, because the workflow file was in the pushed commits.

**2. "A push turns green".** Checked the result. Without the GitHub CLI, I asked GitHub's public API directly:
```
curl -s "https://api.github.com/repos/Bantosito/Iot-Telemtr-Pipeline-Course/actions/runs?per_page=1" | grep -E '"(status|conclusion)"'
```
- `curl -s URL` fetches a web address and prints the reply (`-s` = silent, no progress bar). The reply is JSON describing the latest run (`per_page=1`).
- `| grep -E '...'` keeps only the lines containing `"status"` or `"conclusion"`.
- Result: `completed` / `success`. ✅

(My first attempt was a long, unreadable polling script. It broke while parsing the reply, so I replaced it with this short one. Easier: `gh run list` / `gh run watch` after `brew install gh` + `gh auth login`, or just the **Actions** tab in the browser.)

**3. "A push with a failing test turns red".** A CI that's always green proves nothing (same idea as breaking the validator on purpose in 1.5). So I added an obviously fake test to the end of `tests/test_validator.py`:
```python
def test_deliberately_failing_for_ci_demo():
    assert 1 + 1 == 3
```
```
git commit -am "Deliberately failing test to check CI turns red"   # -a = stage all changed tracked files, -m = message
git push
```
Result: **failure**. Then I checked which step failed, using the run's ID:
```
curl -s ".../actions/runs/39856424297/jobs" | grep -E '"(name|conclusion)"'
```
- checkout, setup-python, install and **Lint (ruff)**: success;
- **Test (pytest): failure**. Exactly the step that should fail, for the reason it should;
- **build-images: skipped**, because of `needs: lint-and-test`. Proof that the dependency between jobs works.

**4. Undid the fake test, the safe way.**
```
git revert --no-edit HEAD
git push
```
- `git revert HEAD` makes a **new** commit that undoes the latest one (`HEAD`). `--no-edit` = accept the default message ("Revert ...").
- Why not delete the commit? It was already pushed. Rewriting pushed history causes trouble (see my git notes); revert adds instead of erasing. Both commits stay visible in the history, which is fine: it shows I tested my CI on purpose.
- Result: **success** again. ✅

**5. "The README shows the status badge".** Added under the README title:
```markdown
[![CI](https://github.com/Bantosito/Iot-Telemtr-Pipeline-Course/actions/workflows/ci.yml/badge.svg)](https://github.com/Bantosito/Iot-Telemtr-Pipeline-Course/actions/workflows/ci.yml)
```
`badge.svg` is an image GitHub regenerates after every run: green "passing" or red "failing". Clicking it opens the workflow's run list. ✅

### How to check CI myself
- **Browser:** repo page → **Actions** tab → click a run → click a job → expand a step to see its full terminal output (e.g. pytest's failure message).
- **The commit list:** a ✓ or ✗ next to each commit.
- **Terminal (after installing `gh`):** `gh run list`, `gh run watch`, `gh run view --log-failed`.

### What comes later with GitHub Actions
In step 3.2 the same system will **deploy** to Azure: on push to `main`, validate Bicep, deploy it, deploy the Function code. It will log in to Azure with OIDC instead of a stored password. CI checks the code; that will be CD (continuous *deployment*).

What surprised me / what broke:

Answers to the questions (in my own words):

1. What triggers your workflow?
The workflow is triggered automaticlay when repo is pushed/pull request is creted to github. Github actions look for yml/yaml files in .github/workflows folder and ci.yml that inside of it triggers the CI pipeline

2. Why also build the images in CI, not only run tests?
The test (pytest| ruff) does not check  whether the compose was written write or wheter the container can be composed so to assure that the image is valid and creates a working container.

### Exercises (hands-on, do them myself)

Each exercise: do it, watch the result, then write one line under it about what happened. Afterwards, always get CI back to green.

**1. Read a red run.** *(5 min, browser only)*
On GitHub: **Actions** tab → the run "Deliberately failing test to check CI turns red" → job `lint-and-test` → expand **Test (pytest)**. Find the line where pytest explains *why* `1 + 1 == 3` failed.
- Which job was skipped, and which line in `ci.yml` caused that?

**2. Make the linter fail, not the tests.** *(10 min)*
Add an unused import, e.g. `import os`, at the top of `tests/test_validator.py`.
- First run `ruff check .` locally. What does it say, and what's the rule code?
- Commit and push. Which step goes red this time? Did `Test (pytest)` even run? Why not?
- Fix it with `ruff check . --fix`, commit, push, and see green again.

**3. Make the build fail, not the code.** *(10 min)*
In `sensor/Dockerfile`, change `COPY main.py .` to `COPY mian.py .` (a typo).
- Run `pytest` and `ruff check .` locally: do they still pass? (They should. This is exactly the point of 1.7 Q2.)
- Push it. Which job fails now? Read the error message in the `Build images` step.
- Fix the typo, push, and see green again.

**4. Undo with revert myself.** *(5 min)*
After one of the exercises above, instead of fixing by hand, undo the breaking commit:
```
git log --oneline -3          # find the commit's ID
git revert --no-edit <ID>
git push
```
- Look at `git log --oneline` afterwards: what did revert add, and what did it NOT delete?

**5. Catch it before CI does.** *(5 min)*
Before pushing, run exactly what CI runs, locally:
```
ruff check .
pytest
docker compose build
```
- If all three pass locally, CI should pass too. Why is it still useful to have CI anyway? (Hint: a clean machine, and other people's pull requests.)

**6. Try `gh` (optional).** *(10 min)*
```
brew install gh
gh auth login
gh run list
gh run view --log-failed      # on a red run
```
- Compare with the `curl ... | grep` command from these notes. Which is easier, and why does `gh` need a login while `curl` didn't? (Hint: the repo is public, so reading it needs no login.)

**7. Bonus: break the trigger.** *(5 min, reading only, don't push this)*
Look at the `on:` block in `ci.yml`. If it said only `on: pull_request`, what would happen on my normal `git push` to `main`? And if it said `on: push: branches: [main]`, what would happen on a push to another branch?

What I'd do differently:

## Extra (after 1.7): Makefile as a local CI pipeline
Date: 27.10.2026 (written by Claude at my request)

What I built:
- `Makefile` in the project root: one-word shortcuts for the project's commands.
- `.github/workflows/ci.yml` now calls the same Makefile targets (`make lint`, `make test`, `make build`) instead of the raw commands.

Side note: I renamed the GitHub repo to **https://github.com/Bantosito/Iot-Telemetry-Pipeline**. Older links in these notes (`Iot-Telemtr-Pipeline-Course`) still work, because GitHub forwards them. Updated the saved address with `git remote set-url origin https://github.com/Bantosito/Iot-Telemetry-Pipeline.git` (check with `git remote -v`), and updated the badge links in the README.

### Makefiles from zero

`make` is a tool from 1976, already installed on macOS (`make --version`). It reads a file called `Makefile` and runs **named groups of commands**:
```makefile
test:            # the target's name, followed by a colon
	pytest -v    # the command(s) it runs - indented with a TAB
```
Then `make test` runs `pytest -v`.

`make` was built for compiling C programs, where it cleverly rebuilds only what changed. Python has nothing to compile, so in Python projects it's simply **a menu of the project's commands**: `make test` instead of remembering `pytest -v`, `make up` instead of `docker compose up --build -d`.

⚠️ **The TAB rule.** Command lines must start with a real TAB character, not spaces. With spaces, make fails with `missing separator`. (VS Code may turn tabs into spaces; for Makefiles it normally keeps tabs.)

### My Makefile, piece by piece

```makefile
.PHONY: help lint test build check up down logs
```
Tells make these names are *commands*, not files. Without it, a file called `test` in the folder would make `make test` say "nothing to do" (a leftover from make's file-building origins).

```makefile
help:
	@echo "make lint    - ruff: read the code for likely mistakes"
	...
```
The first target in the file is the **default**, so plain `make` prints this menu. The `@` hides the command itself and shows only its output (without it, make prints each command before running it).

```makefile
lint:
	ruff check .
test:
	pytest -v
build:
	docker compose build
```
The three checks CI runs, each with its own name.

```makefile
check: lint test build
	@echo "All checks passed - safe to push."
```
**Dependencies.** Names after the colon run *first*, in order: lint, then test, then build. **If any fails, make stops immediately** and the rest don't run, exactly like a red step in CI skipping the steps after it. The message only appears if all three passed.

```makefile
up:
	docker compose up --build -d
down:
	docker compose down
logs:
	docker compose logs -f bridge
```
Everyday Docker shortcuts.

### Why it works as a local CI pipeline

Before: CI ran `ruff check .`, `pytest -v`, `docker compose build`, and locally I had to remember to type the same three commands myself.
Now: one command runs the same checks before I push:
```
source .venv/bin/activate     # once per terminal tab: make uses whatever ruff/pytest it finds
make check
```
Ran it: ruff passed → 32 tests passed → both images built → `All checks passed - safe to push.`

**CI calls the Makefile too.** In `ci.yml`, `run: ruff check .` became `run: make lint`, and so on. The commands now live in **one place**: if I change or add a check in the Makefile, my laptop and GitHub both get it. They can't drift apart. Pushed it, and CI went green running through the Makefile. ✅

**What the local pipeline can't replace:** `make check` runs on *my* laptop, with my files, my installed tools and my `.venv`. GitHub CI runs on a clean machine and also checks other people's pull requests. Local = catch problems sooner; CI = the final word.

### Alternatives I might hear about
- **`just`**: a modern `make` alternative with simpler syntax and no TAB trap.
- **`tox` / `nox`**: Python-specific runners, e.g. testing against several Python versions.
- **pre-commit hooks**: run checks automatically on every `git commit`, so you can't even commit lint errors.

### Exercises (predict → run → record)

**1. The menu.** Run `make` with no target. Why does it show the help text? *(1 min)*
Is it becuase its the first command that appears?

**2. Watch it stop on failure.** *(5 min)* Add `import os` (unused) to the top of `tests/test_validator.py`, then run `make check`.
- Which step fails? Do the tests and the build still run? Why not? Compare with the red CI run in 1.7.
- Undo: `git restore tests/test_validator.py`. 

It stopped check on: import: Nosuch file or directory- returend error 1

**3. The TAB trap.** *(5 min)* In the `Makefile`, replace the TAB before `pytest -v` with 4 spaces and run `make test`. Read the error message. Undo with `git restore Makefile`.

RETURNED: Makefile:24: *** missing separator.  Stop.

**4. Forget the venv.** *(3 min)* Open a new terminal tab, `cd` into the project *without* activating the venv, and run `make test`. What happens, and why? (Hint: which `pytest` can the terminal find?)

make works but it cannot run

ruff check . make: ruff: No such file or directory make: *** [lint] Error 1
make: pytest: No such file or directory-> Error 1

Docker up/down works and logs work

**5. See what make runs.** *(2 min)* `make -n check` (`-n` = "dry run": print the commands without running them). Useful for checking what a target does before trusting it.

Interesting, good to know

**6. Add my own target.** *(10 min)* Add a target `watch` that runs `mosquitto_sub -t '#' -v`. Add it to `.PHONY` and to `help`. Run `make watch` while the stack is up.

Its in there, good addition 

## My questions about CI (answered by Claude, 27.10.2026)

**Why does CI need `setup-python` for the tests, but no setup for Docker before `docker compose build`?**

Because the runner already has Docker, but not *my* Python.
- `runs-on: ubuntu-latest` is not an empty computer. It's a ready-made Ubuntu machine with lots of tools preinstalled: git, **Docker + Docker Compose**, `make`, curl, Node... So `docker compose build` just works.
- Ubuntu also ships *a* Python, but `setup-python` is still needed:
  1. **Exact version**: the preinstalled Python is whatever Ubuntu ships and changes when GitHub upgrades `ubuntu-latest`. Pinning `"3.12"` = the same Python as my laptop and my Docker images.
  2. **A safe place to `pip install`**: recent Ubuntu blocks `pip install` into the system Python, to protect the OS's own tools. `setup-python` gives a separate Python where installing is allowed (like my `.venv`).
  3. **The pip cache**, for faster runs.
- **The deeper reason:** building an image only needs the Docker *engine*. Everything inside the image comes from the Dockerfile. `FROM python:3.12-slim` brings its own Python, whatever the runner has. The tests run directly on the runner, so the runner needs the right Python. The images carry their own environment, so the runner just needs Docker. That's the point of containers (1.6).

**How was CI set up on GitHub? Does GitHub just look for `ci.yml`?**

Almost: GitHub reads **every** `.yml`/`.yaml` file in `.github/workflows/`. `ci.yml` is only the name I chose. No other setup was needed:
1. GitHub Actions is **on by default** for every new repo.
2. On every event (push, pull request...), GitHub checks the commit for files in `.github/workflows/`.
3. For each file it reads `on:`. If the event matches, it queues a run.
4. A runner starts and works through `jobs:`.

So my first push "switched CI on" just by containing `.github/workflows/ci.yml`. There's no registration step and no button. Another file, e.g. `nightly.yml` with `on: schedule`, would run independently next to it.
- Optional settings live in the repo's **Settings → Actions** (turn Actions off, restrict which actions are allowed, permissions).
- Free for public repos on standard runners; private repos get a monthly allowance of minutes.
- The file name matters in one place: the README badge URL points to `.../workflows/ci.yml/badge.svg`, so renaming the file would break the badge.

**What is a README badge, and why have one?** *(answered by Claude, 27.10.2026)*

A small image at the top of the README that shows a **live status**. Mine is the green "CI | passing" under the title.
- It isn't stored in the repo. It's a link to an image GitHub draws fresh each time the README is viewed: `https://github.com/Bantosito/Iot-Telemetry-Pipeline/actions/workflows/ci.yml/badge.svg`. Green **passing** or red **failing**, based on the latest `ci.yml` run on `main`. Clicking it opens the Actions page.
- **Why:** it answers "does this actually work?" in one second, before anyone reads code. For reviewers and recruiters, it shows automated tests that pass right now, i.e. a maintained, checked project. For me, a red badge on my own README is hard to ignore. And it can't be faked: it reflects the real last run.
- Other badges (coverage %, version, license, Python version) work the same way, often via shields.io. For a portfolio, the CI badge is the one that matters.
