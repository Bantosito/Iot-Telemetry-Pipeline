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


## Step 1.8 — Azure account and budget alert
Date: 28.10.2026

What I built (in the Azure portal, by hand; it gets rewritten as code in step 2.1):
- An Azure free account. Billing currency: **DKK**.
- A monthly budget on my subscription, with email alerts at **50% actual** and **100% forecasted**.

What surprised me / what broke:
- The billing page showed **"Your payment data cannot be loaded"**. Everything else works so far. This is usually a portal display glitch (ad blocker, privacy extension, blocked cookies), not a problem with the subscription. Check: **Subscriptions** → my subscription → **Status = Active**, and note the offer name.

What the free account includes (my summary):
- $200 credit for the first 30 days, 12 months of selected services free, and spending protection (a spending limit).
- After the free period: *to verify on my own subscription*. With the classic free account, resources are **disabled** (not charged) when the 30 days or the credit run out, unless I **choose** to upgrade to pay-as-you-go. Look for a "spending limit" setting or an "Upgrade" banner on the subscription.

### Cloud costs from zero (written by Claude)

**How cloud billing works.** No upfront price: you pay for what you use, usually per hour that a resource exists or per operation it performs. A database that runs 24/7 is billed 24/7, even if nobody queries it. That's why a forgotten resource is the classic cloud-cost accident.

**Three kinds of "free" in my account:**
| Kind | What it means | Relevant for this project |
|---|---|---|
| 30-day credit | $200 to spend on anything for 30 days | a safety buffer while learning |
| 12 months free | selected services free up to a monthly amount (e.g. hours per month) | PostgreSQL flexible server, Burstable B1ms (step 2.3), *check it's on the list* |
| always free | small tiers that stay free | IoT Hub F1 (8,000 msgs/day), Functions (up to a number of executions per month) |

"Free" always means **free up to a limit**. Going over a limit, or picking a bigger tier by mistake (e.g. B2s instead of B1ms), costs money.

**Spending limit vs budget: two different safety nets.**
- **Spending limit** (part of the free account): when credit runs out, Azure *stops* resources instead of charging. A hard stop.
- **Budget** (what I created): **only sends emails**. It never stops anything. Hitting 100% means "you've been warned", nothing more.
- **Cost data is delayed** (hours, up to about a day), so alerts are an early warning, not real-time.

**My two alert rules:**
- **Actual 50%**: fires when I've *really spent* half the budget. A fact, but it arrives after the money is spent.
- **Forecasted 100%**: Azure projects my spending to the end of the month at the current rate, and fires if the projection goes **over** the budget. It warns *early*, before the money is spent: e.g. on day 5, "at this rate you'll spend 300%".
Together: forecast = early warning, actual = confirmation.

**Where things are in the portal:**
- **Cost Management + Billing** → currency, invoices, payment methods.
- **Cost Management → Budgets** → my budget and its alert rules.
- **Cost Management → Cost analysis** → what has been spent, by resource and by day.
- **Subscriptions** → my subscription: status, offer type, spending limit.

**Why first, before any resource:** from week 2 on I'll create IoT Hub, PostgreSQL and a Function App. If I misconfigure something, the budget email is how I find out in days instead of on next month's invoice. In step 2.1 the same budget is rewritten in **Bicep** (infrastructure as code), so it's documented and recreated automatically.

Answers to the questions (in my own words):

1. What in this project could cost money?
While its in the free account there will be no charge to the card, hoverwer if i change to pay as you go I will be charged for resources I use according to the billing.

2. What's the difference between "actual" and "forecasted" in a budget alert?
Actual cost is the current amount of money used on resources, so when it hits the set alert ammount it means that this amount was already used. Forecasted cost is a prediction that with this pace os spending by the end of alert period (ex. a month) spending will reach over set budget.

### Exercises (predict → run → record)

**1. Check my subscription's real terms.** *(5 min)*
Portal → **Subscriptions** → my subscription. Find: Status, offer name, and whether there's a spending limit or an "Upgrade" banner.
- Write down exactly what happens on day 31 for *my* account. Does it switch to pay-as-you-go by itself, or not?

**2. Put a date in my calendar.** *(2 min)*
Find the date my 30-day credit ends (it's shown on the subscription or the free services page). Put a reminder **3 days before it** in my calendar: "Azure free credit ends — check resources and costs."

**3. Look at the cost tools while they're empty.** *(5 min)*
Open **Cost analysis**. It should show ~0 DKK. Find where I could group costs "by resource". Predict: when PostgreSQL exists in step 2.3, will its cost appear immediately? (Hint: the delay.)

**4. Find the free services list.** *(10 min)*
Portal search: **"Free services"**. Find *Azure Database for PostgreSQL flexible server* and *IoT Hub*.
- What exactly is free: which tier, how many hours or messages per month?
- Work it out: a B1ms server running 24/7 for a 31-day month is 744 hours. Does that fit inside the free monthly hours?

**5. Read my budget's alert rules back.** *(3 min)*
Open the budget → edit. Check both rules are there: 50% *Actual*, 100% *Forecasted*. Which one would fire first if I accidentally created an expensive resource on day 2 of the month, and why?

**6. Fix the payment-data error (optional).** *(5 min)*
Open the payment page in a private browser window with extensions off. Does the error disappear? If yes, it was the browser, not the account.

What I'd do differently:


## Can I set a hard spending limit? (answered by Claude, 28.10.2026)

**Only partly. Azure has no general "never charge me more than X" switch.**
- **Spending limit** = the only real hard limit. It exists only on credit-based offers (free trial, Visual Studio subscriptions). When the credit runs out, Azure *stops* resources instead of charging. **Pay-as-you-go has no spending limit**, which is why "what happens on day 31" matters.
- **Budgets only send alerts.** But a budget can trigger an **action group**, which can run automation (e.g. a script that stops or deletes resources at 100%): a DIY hard limit. Not exact, because cost data is hours late, so a small overshoot is possible.
- **Prevention beats limits:**
  - **Azure Policy**: rules like "only allow PostgreSQL B1ms, only IoT Hub F1". Azure *refuses* to create anything bigger, even by mistake or from a pipeline.
  - **Infrastructure as code**: every resource and its tier is written down and reviewed.
  - **Teardown**: delete the resource group when idle; IaC rebuilds it in one command (step 3.3). PostgreSQL can be *stopped* to pause compute billing (max 7 days, then it auto-starts; storage is still billed).
- **Plan for this project:** budget alerts + a Policy restricting tiers + teardown when idle.


## Week 2 kickoff: Bicep or Terraform? (discussion with Claude, 28.10.2026)

**Decision: Terraform** (the README originally planned Bicep). README steps 2.1, 2.3, 2.4 and 3.2 were updated.

Both tools do the same job: **describe cloud resources in text files, and the tool makes the cloud match.** The difference is who makes them and how they track what exists.

| | **Bicep** | **Terraform** |
|---|---|---|
| Made by | Microsoft | HashiCorp (owned by IBM since 2025) |
| Clouds | Azure only | any: Azure, AWS, GCP, plus GitHub, Kubernetes, Datadog… |
| Language | Bicep (compiles to Azure's ARM JSON) | HCL |
| Tracks what exists via | Azure itself, nothing extra to manage | a **state file** that must be stored safely, usually remotely (e.g. Azure Storage) |
| Preview changes | `az deployment ... what-if` | `terraform plan` |
| New Azure features | supported immediately | sometimes later (the `azapi` provider fills gaps) |
| Learning curve | gentle if you know Azure | steeper: providers, state, backends |
| Job market | Azure-only companies | far more common in job ads, especially consultancies and multi-cloud teams |
| Licence | free, open source | source-available since 2023; **OpenTofu** = the fully open fork |

**Bicep: pros/cons.** Less to learn, nothing extra to go wrong, no state file to protect or lose, always current with Azure. But it's an Azure-only skill that doesn't transfer to AWS or GCP.

**Terraform: pros/cons.** One tool and one way of thinking for every cloud, a huge community, and what job postings ask for. The extra concept is **state**: Terraform's memory of what it created. It can contain secrets and must be shared between laptop and CI, so it lives in a remote backend, which must exist *before* Terraform can use it (a chicken-and-egg problem solved by a small bootstrap step).

**Why Terraform here:** the project is a portfolio for job applications, and Terraform is what the ads ask for. Its concepts (state, plan/apply, providers, remote backends, locking) apply to every cloud, and Bicep can be picked up quickly later for an Azure-only job. The state file is extra work, but it's exactly what interviewers ask about ("where do you keep your state, and how do you lock it?").


## Quick questions (answered by Claude, 28.10.2026)

### Where are the Azure CLI and Terraform installed? Does it matter that my venv is active?
- Homebrew installs everything under **`/opt/homebrew`**: the program files in `/opt/homebrew/Cellar/<name>/<version>/`, plus a shortcut in **`/opt/homebrew/bin/`**, which is on the terminal's search path. Check with `which az` and `which terraform`.
- **The venv doesn't matter.** A venv only changes which *Python things* the terminal finds (`python`, `pip`, `pytest`, `ruff`) by putting `.venv/bin` first on the search path. Terraform is a single Go program. The Azure CLI is Python, but brew gives it **its own private Python**, separate from `.venv`.

| Installed with | Lives in | Works |
|---|---|---|
| `pip install` (venv active) | `.venv/` in this project | only here, only with the venv active |
| `brew install` | `/opt/homebrew/` | everywhere, every project, venv or not |

(That's why `make test` failed without the venv, while `docker` and `make` worked.)

### My subscription is called "Azure subscription 1". Is it the free one?
The name is just a default label that every new subscription gets. The real offer type is stored separately:
```
az account show --query id --output tsv          # prints the subscription ID
az rest --method get --url "https://management.azure.com/subscriptions/<ID>?api-version=2022-12-01" --query subscriptionPolicies
```
- `az rest` sends a request directly to Azure's management API; `--query` picks out one part of the reply.
- My result: `"quotaId": "FreeTrial_2014-09-01"` → **Free Trial**; `"spendingLimit": "On"` → the hard limit is active.
- **So, day 31:** when the credit or the 30 days run out, Azure **stops resources, it doesn't charge my card.** It only becomes pay-as-you-go if I *choose* to upgrade, and upgrading turns the spending limit off. After that, budget alerts are the main protection.
- Quick check of which subscription the terminal uses: `az account show --output table`.

### What is Homebrew, what is a tap?
**Homebrew (`brew`) = a package manager for macOS**: install, update and remove software with one command, including dependencies (e.g. it gave `azure-cli` its own Python). Like `apt` on Ubuntu.

| Word | Meaning | Example |
|---|---|---|
| formula | recipe for a command-line tool | `terraform`, `azure-cli`, `mosquitto` |
| cask | recipe for a regular Mac app | `brew install --cask docker` |
| bottle | pre-compiled package, so installs are fast | automatic |
| tap | an extra source of formulas (a Git repo on GitHub) | `hashicorp/tap` |
| Cellar | where packages actually live | `/opt/homebrew/Cellar/` |

**Why a tap for Terraform:** Homebrew's main collection only accepts open-source licences. After Terraform's 2023 licence change, it froze Terraform at 1.5.7. HashiCorp publishes current versions in its own tap:
- `brew tap hashicorp/tap` = also look in github.com/hashicorp/homebrew-tap;
- `brew install hashicorp/tap/terraform` = install *from that tap* (got v1.17.0).

**Useful commands:**
```
brew install <name> / brew uninstall <name>
brew list                 # what's installed
brew info <name>          # version, location, dependencies
brew update               # refresh available versions
brew outdated             # what has newer versions
brew upgrade [<name>]     # upgrade everything or one package
brew doctor               # diagnose Homebrew problems
brew services list        # background services started by brew
```
**Idea for later:** a `Brewfile` listing this project's tools, so `brew bundle` installs all of them on a new Mac (like `requirements.txt`, but for system tools).


### What is a Brewfile, and does it go to GitHub? *(28.10.2026)*
A `Brewfile` lists the **system tools** a project needs, like `requirements.txt` does for Python packages. **Yes, it's committed to GitHub**: it contains only tool names, no secrets, and it lets anyone (or me on a new Mac) install everything with one command.
- Mine: `tap "hashicorp/tap"`, `brew "hashicorp/tap/terraform"`, `brew "mosquitto"`, `cask "azure-cli"`, `cask "docker-desktop"`, and `gh` as an optional commented line.
- How I made it: `brew bundle dump --file=<somewhere> --force` writes *everything* installed on the Mac to a file; then I copied over only this project's tools (not unrelated ones like mac-mouse-fix).
- Commands:
```
brew bundle            # install everything in ./Brewfile that's missing
brew bundle check      # is everything installed and up to date?
brew outdated          # which installed packages have newer versions
brew upgrade <name>    # upgrade one package
```
- First check said mosquitto and docker-desktop "need to be installed or updated": they're installed but **outdated** (`brew outdated` confirmed). Upgrade when convenient: upgrading Docker Desktop restarts running containers.


## Step 2.1 — Terraform, part 1: bootstrap (log, written by Claude, 28.10.2026)

### Tools installed
```
brew install azure-cli                  # the Azure CLI: "az"
brew tap hashicorp/tap                  # add HashiCorp's own package source
brew install hashicorp/tap/terraform    # Terraform v1.17.0
az login                                # opens the browser, logs the terminal in to Azure
```
Check: `terraform -version` → `Terraform v1.17.0`; `az account show --output table` → `Azure subscription 1`, `Enabled`, the Free Trial (see quick questions).

### Why a "bootstrap" step at all: the chicken-and-egg problem
Terraform keeps a **state file**: its own record of "I created these resources, and these are their IDs". Next time it compares that record with my `.tf` files and with what really exists in Azure, and works out what to change.

The state file shouldn't live on my laptop:
- CI (step 3.2) must use the **same** state as my laptop, or they'd each think they own different things;
- if the laptop dies, the state is gone, and Terraform "forgets" everything it created;
- it can contain secrets (connection strings, keys), so it needs proper access control.

So it goes into an **Azure Storage account**. But who creates that storage account? If Terraform did, where would the state *of the storage account* live? That's the chicken-and-egg problem. Solution: create it **once, by hand, with `az` commands**, outside Terraform. This one-time setup is called **bootstrapping**.

It goes in its **own resource group** (`rg-tfstate`), separate from the project's resources. When I delete the project's resource group (step 3.3, teardown), the state survives.

### Problem 1: "Subscription was not found"
First command:
```
az storage account check-name --name sttfstatebantos --output table
```
(asks Azure whether that storage account name is still free; names are global across all of Azure)

Error: `(SubscriptionNotFound) Subscription b9efd0b9-... was not found.`, even though the subscription clearly exists and is Enabled.

**The real cause: resource providers.** Azure is made of hundreds of separate services, each called a **resource provider**:
| Provider | Service |
|---|---|
| `Microsoft.Storage` | storage accounts (where the Terraform state will live) |
| `Microsoft.Devices` | IoT Hub |
| `Microsoft.DBforPostgreSQL` | PostgreSQL (step 2.3) |
| `Microsoft.Web` | Function Apps (step 2.4) |

A new subscription has most of them **switched off** ("NotRegistered"). Registering one = ticking "I want to use this service". It's **free, creates nothing and costs nothing**.
- The **portal** registers providers automatically the first time you click "Create...", so you never notice.
- The **CLI and Terraform** sometimes don't, and Azure then returns a misleading error like "Subscription not found".

### The fix, command by command
```
az provider show --namespace Microsoft.Storage --query registrationState --output tsv
```
- `az provider show`: show information about one provider;
- `--namespace Microsoft.Storage`: which provider;
- `--query registrationState`: keep only the registration status from the reply;
- `--output tsv`: plain text instead of JSON.

Result: `NotRegistered`. That's the cause.

```
az provider register --namespace Microsoft.Storage --wait 2>/dev/null
```
- `az provider register`: switch the provider on;
- `--wait`: don't return until it's finished (10–60 s). Without it the command returns at once and registration continues in the background;
- `2>/dev/null`: throw away error output. `2>` = "send error output to...", `/dev/null` = a black hole that discards anything written to it. (The opposite of `2>&1` from 1.5, which *merges* errors into normal output.)

I joined it to the check with `;` = "then run the next command, whatever happened" (unlike `&&`, which only continues on success).

Ran `show` again → **`Registered`** ✅. Same for **`Microsoft.Devices`** (IoT Hub) → `Registered` ✅. The others get registered when their steps come.

**The `SyntaxWarning` lines** that `az` printed: the Azure CLI is a Python program, and brew gave it Python 3.14, which warns about an outdated escape sequence inside Microsoft's own code. Harmless; nothing to do with this project. That's why I hid it with `2>/dev/null`.


### What is a resource provider, and why did Azure say "Subscription not found"? *(28.10.2026)*
Azure is hundreds of separate services, each a **resource provider** (`Microsoft.Storage` = storage accounts, `Microsoft.Devices` = IoT Hub, `Microsoft.DBforPostgreSQL` = PostgreSQL...). A new subscription has most of them **switched off**. The portal switches them on silently when you first create something; the CLI/Terraform sometimes don't, and Azure then gives misleading errors like "Subscription not found".
```
az provider show --namespace Microsoft.Storage --query registrationState --output tsv   # NotRegistered / Registered
az provider register --namespace Microsoft.Storage --wait                              # switch it on (free, creates nothing)
```
Full walkthrough → [11-terraform.md](11-terraform.md) (step 2.1 bootstrap log)

### What do `2>/dev/null` and `;` mean in a command?
- `2>/dev/null`: throw away a command's **error output**. `2` = the error stream, `>` = send to, `/dev/null` = a black hole. (`2>&1` instead *merges* errors into normal output.)
- `;`: run the next command **no matter what**. `&&` runs it **only if the previous succeeded**.


## Azure fundamentals, with AWS comparisons (written by Claude, 28.10.2026)

*A reference "map of Azure". It will grow as the project meets new services. AWS equivalents are included because job ads often ask for "Azure or AWS", and the concepts transfer.*

### 1. What a cloud provider actually sells
Instead of buying servers, you **rent** computing as services, billed by use. Services sit on a scale from "you manage more" to "the provider manages more":

| Model | You manage | Provider manages | Azure example | AWS example |
|---|---|---|---|---|
| **IaaS** (infrastructure) | OS, runtime, app, data | hardware, network | Virtual Machines | EC2 |
| **PaaS** (platform) | app + data only | OS, patching, scaling, backups | PostgreSQL flexible server, App Service | RDS, Elastic Beanstalk |
| **Serverless / FaaS** | just the code | everything, scales to zero | **Azure Functions** | Lambda |
| **SaaS** (software) | nothing, you just use it | everything | Microsoft 365, Power BI | (e.g. QuickSight) |

This project is almost all **PaaS + serverless** (IoT Hub, PostgreSQL flexible server, Functions). That's deliberate: no servers to patch.

### 2. How Azure is organised (the hierarchy)

```
Microsoft Entra ID tenant      ← my organisation's identity directory ("Default Directory")
└── Management groups          ← optional folders of subscriptions, for big companies
    └── Subscription           ← "Azure subscription 1": a billing + access boundary
        └── Resource group     ← a folder for related resources: rg-tfstate, later rg-iot-...
            └── Resource       ← one actual thing: a storage account, an IoT Hub, a database
```

| Azure level | What it is | Closest AWS equivalent |
|---|---|---|
| **Entra ID tenant** (formerly Azure AD) | the directory of users, groups, app identities | IAM + IAM Identity Center |
| **Management group** | groups subscriptions, applies policies to all of them | AWS Organizations, Organizational Units (OUs) |
| **Subscription** | where costs are billed and limits apply; my Free Trial | an **AWS account** |
| **Resource group** | a mandatory folder for resources, deleted as a unit | *nothing mandatory*: AWS uses tags, CloudFormation stacks, or separate accounts |
| **Resource** | a storage account, a hub, a database | a resource (S3 bucket, EC2 instance...) |

**Key Azure difference: resource groups.** Every Azure resource must be in exactly one resource group. That makes "delete everything for this project" a single action (step 3.3 teardown), and it's why the Terraform state lives in its *own* group, `rg-tfstate`. AWS has no direct equivalent, which is one of the first differences people notice when switching.

**Regions and availability zones** work the same way in both clouds:
- a **region** = a geographic location with data centres, e.g. `northeurope` (Ireland), `westeurope` (Netherlands), `swedencentral`. AWS names them like `eu-west-1` (Ireland), `eu-north-1` (Stockholm);
- **availability zones** = physically separate data centres *inside* one region, so one fire or power cut doesn't take everything down;
- why it matters: latency (closer = faster), data residency (EU data staying in the EU), price (differs per region), and not every service or tier exists in every region.

**Azure Resource Manager (ARM)** is the single "front door" API for every create/change/delete in Azure. The portal, `az`, Terraform and Bicep all talk to ARM. (AWS has no single equivalent; each service has its own API.) **Resource providers** (`Microsoft.Storage`, `Microsoft.Devices`...) are the services behind ARM; see the bootstrap log for why they need registering.

### 3. Main service categories: Azure ↔ AWS

| Category | Azure | AWS | Used in this project? |
|---|---|---|---|
| Virtual machines | Virtual Machines | EC2 | no |
| Serverless functions | **Azure Functions** | Lambda | ✅ step 2.4 |
| Containers (simple) | Container Apps, Container Instances | ECS / Fargate, App Runner | maybe later |
| Kubernetes | AKS | EKS | no |
| Object/file storage | **Storage account** (Blob, Files, Queues, Tables) | S3, EFS, SQS, DynamoDB (separate services) | ✅ Terraform state; Function App needs one |
| Relational database | **Azure Database for PostgreSQL / MySQL**, Azure SQL | RDS, Aurora | ✅ step 2.3 |
| NoSQL database | Cosmos DB | DynamoDB | no |
| IoT device gateway | **IoT Hub** | AWS IoT Core | ✅ step 2.2 |
| Event streaming | Event Hubs | Kinesis, MSK (Kafka) | ✅ indirectly: IoT Hub's built-in endpoint *is* Event Hubs-compatible |
| Message queues | Service Bus, Storage Queues | SQS, SNS | no |
| Identity | **Microsoft Entra ID**, managed identities | IAM, IAM roles | ✅ step 3.1 |
| Access control | **Azure RBAC** (role assignments) | IAM policies | ✅ steps 3.1–3.2 |
| Guardrails / rules | **Azure Policy** | Service Control Policies, AWS Config | maybe (tier limits) |
| Secrets | Key Vault | Secrets Manager, Parameter Store | maybe |
| Monitoring / logs | **Azure Monitor**, Log Analytics, Application Insights | CloudWatch, X-Ray | ✅ step 4.3 |
| Cost tools | **Cost Management + Budgets** | Cost Explorer + AWS Budgets | ✅ step 1.8 |
| Networking | Virtual Network (VNet), NSG | VPC, Security Groups | lightly (database firewall) |
| Native IaC | ARM templates / **Bicep** | CloudFormation / CDK | — (I chose Terraform, which does both clouds) |
| BI / reporting | Power BI | QuickSight | ✅ step 4.2 |

### 4. Storage options in depth

#### 4.1 The storage account: Azure's storage "container of services"
In Azure, most storage lives inside a **storage account**: one named resource with a globally unique name (that's why `sttfstatebantos` had to be checked across all of Azure; it becomes part of a web address, `https://sttfstatebantos.blob.core.windows.net`). One storage account offers **four services**:

| Service inside a storage account | What it stores | AWS equivalent |
|---|---|---|
| **Blob storage** | any files ("blobs" = binary large objects): images, backups, logs, **Terraform state** | **S3** |
| **Azure Files** | network file shares a computer can mount like a drive | EFS / FSx |
| **Queue storage** | simple message queues | SQS (basic) |
| **Table storage** | simple key-value NoSQL tables | DynamoDB (very basic) |

**Key difference:** AWS has a *separate* service for each (S3, EFS, SQS, DynamoDB). Azure bundles them under one storage account, with shared settings (location, redundancy, security). We only use **Blob storage**.

Blob storage's structure, compared to S3:
```
Storage account  (sttfstatebantos)     ≈  the S3 "namespace" (no direct equivalent)
└── Container    (tfstate)              ≈  an S3 bucket
    └── Blob     (iot.terraform.tfstate) ≈  an S3 object
```
⚠️ A blob **"container" has nothing to do with Docker containers**. Same word, completely different meaning: here it's just a folder for blobs.

#### 4.2 Redundancy: how many copies, where
Every storage account keeps **multiple copies** of the data. You choose how far apart they are:

| Option | Copies | Survives | Cost |
|---|---|---|---|
| **LRS** (locally redundant) | 3 copies in **one data centre** | a disk/server failure | cheapest |
| **ZRS** (zone-redundant) | 3 copies across **3 availability zones** in one region | a whole data centre going down | more |
| **GRS** (geo-redundant) | LRS + 3 more copies in a **second region** hundreds of km away | a whole region going down | more again |
| **GZRS** | ZRS + a second region | both | most |

AWS S3 standard is roughly like ZRS by default (copies across availability zones); cross-region replication is opt-in.
**For the Terraform state: LRS.** It's tiny, cheap, versioned, and if a whole Azure data centre burned down, I could recreate it.

#### 4.3 Access tiers: how often the data is read
| Tier | For | Storage price | Read price | AWS S3 equivalent |
|---|---|---|---|---|
| **Hot** | data used often | highest | lowest | S3 Standard |
| **Cool** | rarely read, ≥30 days | lower | higher | S3 Standard-IA |
| **Cold** | very rarely read, ≥90 days | lower still | higher | S3 Glacier Instant Retrieval (roughly) |
| **Archive** | almost never; hours to get back | very low | high + slow | S3 Glacier Deep Archive |

Terraform reads its state on every run → **Hot** (the default).

#### 4.4 Other storage you'll hear about
| Azure | What | AWS |
|---|---|---|
| Managed Disks | the hard drive attached to a VM | EBS |
| Data Lake Storage Gen2 | Blob storage + a real folder hierarchy, for big-data analytics | S3 + Lake Formation |
| Databases (PostgreSQL, Azure SQL, Cosmos DB) | structured data you *query* | RDS, Aurora, DynamoDB |

**Files vs databases:** blob storage = files you read and write whole (like Terraform state). A database = structured data you query ("average temperature per hour for sensor-01"). That's why the readings go into **PostgreSQL** (step 2.3), not blob storage.

#### 4.5 Securing a storage account (what we'll set on ours)
- **No public access to blobs**: nobody on the internet can read the state file anonymously. (The AWS equivalent: S3 "Block Public Access", now on by default.)
- **Minimum TLS 1.2**: refuse old, insecure encryption versions for connections.
- **Versioning**: every overwrite keeps the previous version, so a corrupted state can be restored. (S3 has the same feature.)
- **Encryption at rest**: always on in Azure; data on disk is encrypted automatically.
- Access by **Entra ID roles (RBAC)** or by **account keys** (like a master password for the whole account). Terraform will use my `az login` for now; step 3.2 switches CI to OIDC.

### 5. How the services map onto this project

```
 sensor → Mosquitto → bridge ──► IoT Hub (Microsoft.Devices)          ≈ AWS IoT Core
                                     │ built-in Event Hubs endpoint      ≈ Kinesis
                                     ▼
                                 Azure Function (Microsoft.Web)          ≈ Lambda
                                  (needs its own storage account)
                                     ▼
                                 PostgreSQL flexible server              ≈ RDS for PostgreSQL
                                     ▼
                                 dbt → Power BI                          ≈ dbt → QuickSight
 Around it: Terraform state in Blob storage (≈ S3), Entra ID + managed identity (≈ IAM roles),
            Cost Management + budget (≈ AWS Budgets), Azure Monitor (≈ CloudWatch)
```

### 6. Exercises (predict → run → record)

**1. Where am I in the hierarchy?** *(5 min)*
```
az account show --output table       # tenant + subscription
az group list --output table         # resource groups in my subscription
```
Which tenant name do I see, and which resource groups exist? Why is `rg-tfstate` there already?

**2. Regions.** *(5 min)*
```
az account list-locations --query "[?metadata.regionCategory=='Recommended'].name" --output tsv
```
Is `northeurope` in the list? Find the region closest to Denmark. (`--query` filters Azure's reply; `[?...]` means "only items where...".)

**3. Providers.** *(5 min)*
```
az provider list --query "[?registrationState=='Registered'].namespace" --output tsv
```
Which providers are registered now? Which ones did *I* register, and which were already on?

**4. Compare in the portal.** *(10 min)*
Portal → search "Storage accounts" → Create (**don't actually create**, just read the form). Find on the form: region, redundancy (LRS/ZRS/GRS...), performance tier. Which settings from section 4 do I recognise?

**5. Write it in my own words.** *(10 min)*
Without looking: draw the Azure hierarchy (tenant → subscription → resource group → resource) and write the AWS equivalent next to each level. Then check against section 2.


### Bootstrap, continued (28.10.2026)

**Checked the storage account name is free:**
```
az storage account check-name --name sttfstatebantos --output table 2>/dev/null
```
Result: `NameAvailable: True`. Storage account names are **global across all of Azure** (3–24 characters, lowercase letters and digits only), because the name becomes part of a web address: `https://sttfstatebantos.blob.core.windows.net`. Naming: `st` = storage (Microsoft's naming convention prefix), `tfstate` = what it's for, `bantos` = makes it unique.

**Command 1: create the resource group**
```
az group create --name rg-tfstate --location northeurope --output table 2>/dev/null
```
- `az group create`: create a resource group, a named folder that every Azure resource must live in. Deleting it deletes everything inside. It costs nothing by itself.
- `--name rg-tfstate`: `rg-` is the conventional prefix for resource groups.
- `--location northeurope`: the region (Ireland). A resource group's location is where Azure stores its *metadata*; the resources inside it can technically be elsewhere, but keeping them together is simplest.
- Result: `northeurope  rg-tfstate` ✅.
- Why its own group: so deleting the project's resource group later (step 3.3) never deletes the Terraform state.

See [12-azure-fundamentals.md](12-azure-fundamentals.md) for what resource groups, regions and storage accounts are, compared to AWS.


### Why create things with `az` (or Terraform) instead of the Azure portal? *(29.10.2026)*
Same result either way, but commands are:
1. **Repeatable**: run again identically (step 3.3 rebuilds everything from nothing); portal setups depend on remembering ~30 options.
2. **Self-documenting**: every setting is visible in the command (`--sku Standard_LRS`, `--allow-blob-public-access false`).
3. **Reviewable and shareable**: saved in `infra/bootstrap.sh`, committed, readable by others; clicks can't be reviewed.
4. **Automatable**: scripts and CI (step 3.2) can run commands, not clicks.
5. **The infrastructure-as-code mindset**: `az` = infrastructure as *commands*, Terraform = infrastructure as a *description*, portal = neither.

The **portal is better for**: exploring which options exist, checking results visually, one-off things, cost and monitoring dashboards.
**Habit: create with code, inspect in the portal.** In companies, manual portal changes in production ("ClickOps") are discouraged or blocked, because they aren't repeatable or reviewable.

### Is bootstrapping the Terraform state backend with `az` normal? *(29.10.2026)*
Yes. The state backend is the one piece usually **not** made by the Terraform that uses it (chicken-and-egg). Common options:
1. a few `az` commands run once, saved in a script (`infra/bootstrap.sh`) ← what I'm doing;
2. a separate tiny Terraform project with a *local* state file that only creates the storage account;
3. HCP Terraform (HashiCorp's hosted service) stores state for you, so no storage account is needed.

Everything after the bootstrap is Terraform; `az` is then only for logging in and checking.


### What does "bootstrap" mean? *(29.10.2026)*
**The small first setup that must exist before the normal process can run**, which can't be done *by* the thing it starts.
- From "pulling yourself up by your own bootstraps" (getting started with nothing to help you). Also where **"booting"** a computer comes from: a tiny built-in program starts first, just to load the operating system.
- **Here:** Terraform's normal job is creating everything and recording it in its **state file**. The state file needs a storage account to live in, and Terraform can't create its own storage place (chicken-and-egg). So the storage account is created **once, by hand, with `az`**, before Terraform runs. After that, Terraform takes over.
- Other uses of the word: a *bootstrap script* (first-time project setup, like the Brewfile); *Bootstrap* the CSS framework (unrelated); *bootstrapping a startup* (no outside investors).

**Command 2: create the storage account** *(typed and run by me, 31.10.2026)*
```
az storage account create \
  --name sttfstatebantos \
  --resource-group rg-tfstate \
  --location northeurope \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false \
  --output table
```
- `\` at the end of a line = "the command continues on the next line".
- `--sku Standard_LRS`: SKU = product variant. **Standard** = normal disks (vs Premium SSD); **LRS** = 3 copies in one data centre (cheapest; fine for a small, versioned state file).
- `--kind StorageV2`: the current general-purpose type (Blob, Files, Queues, Tables).
- `--min-tls-version TLS1_2`: refuse old, insecure encryption on connections.
- `--allow-blob-public-access false`: no blob can ever be made publicly readable.

Checked by Claude with a read-only command:
```
az storage account show --name sttfstatebantos --resource-group rg-tfstate \
  --query "{name:name, location:primaryLocation, sku:sku.name, kind:kind, tls:minimumTlsVersion, publicBlobAccess:allowBlobPublicAccess, state:provisioningState}" \
  --output table
```
(`--query "{a:b, ...}"` picks fields from Azure's long JSON reply and gives them short column names.)

| Location | Sku | Kind | Tls | PublicBlobAccess | State |
|---|---|---|---|---|---|
| northeurope | Standard_LRS | StorageV2 | TLS1_2 | False | Succeeded ✅ |

Habit: **create with code, inspect in the portal**. Portal → Resource groups → `rg-tfstate` → `sttfstatebantos` → Configuration shows the same settings as checkboxes.

**Command 3: create the `tfstate` container** *(typed and run by me, 31.10.2026)*
```
az storage container-rm create --storage-account sttfstatebantos --resource-group rg-tfstate --name tfstate --output table
```
- A **blob container** = a folder for blobs (files) inside Blob storage. Like an S3 bucket. **Not** a Docker container. Terraform's state file will live here.
- `container-rm` = create it through **Azure Resource Manager** (the control plane), where my Owner role is enough. Plain `container create` would use the data plane, which needs a data role or the account key. See "ARM, control plane vs data plane" in [12-azure-fundamentals.md](12-azure-fundamentals.md).

**What went wrong the first time:** I ran a version of the command, but the container didn't exist afterwards. Claude checked with read-only commands:
```
az storage container-rm list --storage-account sttfstatebantos --resource-group rg-tfstate --output table    # → empty
az storage container-rm exists --storage-account sttfstatebantos --resource-group rg-tfstate --name tfstate  # → "exists": false
```
Ran it again on **one line** with `!` (so no `\` line break could break while pasting) → `"exists": true` ✅.
Lesson: **"done" isn't proof**. Check the result with a read-only `show`/`list`/`exists` command after every change.

### 7. ARM (Azure Resource Manager): control plane vs data plane *(31.10.2026)*

**ARM is the single front door for *managing* Azure.** Every create/change/delete/configure request goes through it:
```
  Portal (clicks) ─┐
  az CLI ──────────┤
  Terraform ───────┼──►  ARM  (https://management.azure.com)  ──►  resource providers
  Bicep ───────────┤      checks: who are you? are you allowed?       Microsoft.Storage
  az rest ─────────┘      then forwards the request                   Microsoft.Devices ...
```
ARM does three jobs:
1. **Authentication**: who are you? (`az login`, through Entra ID);
2. **Authorisation**: are you allowed? (my role: **Owner** of the subscription);
3. **Routing**: send the request to the right resource provider. That's why an unregistered provider gave "Subscription not found": ARM had nowhere to route it.

**ARM resource ID**, the full address of a resource:
```
/subscriptions/b9efd0b9-.../resourceGroups/rg-tfstate/providers/Microsoft.Storage/storageAccounts/sttfstatebantos
```
= subscription → resource group → provider → resource type → name. Terraform stores these IDs in its state; that's how it links each code block to a real resource.

**The "two doors" into a service:**
| | **Control plane** (management) | **Data plane** (contents) |
|---|---|---|
| Question | "manage the *thing*" | "use what's *inside*" |
| Examples | create a storage account or container, change TLS | upload, read or delete a **file** (blob) |
| Address | ARM: `management.azure.com` | the service's own: `sttfstatebantos.blob.core.windows.net` |
| Who's allowed | management roles: Owner, Contributor | **data roles** (Storage Blob Data Contributor) **or** the secret access key |
| CLI | `az storage account create`, `az storage container-rm ...` | `az storage container create`, `az storage blob upload` |

- **Why separate:** "may manage infrastructure" ≠ "may read the data". An admin who sets up finance's storage shouldn't read finance's files. Being **Owner does not by itself grant data access**. (Loophole: Owners can read the **access keys** through ARM, and a key opens the data door. Step 3.1 closes this kind of gap with identities and roles.)
- **`-rm` in commands** = "through Resource Manager" (the control plane).
- **Terraform's state:** reading and writing the state file is data plane. For now Terraform fetches the account key via my `az login`; later we switch to roles.
- **AWS:** has the same split (S3 `CreateBucket` = control, `PutObject` = data), but **one permission system (IAM)** covers both. Azure has **two layers** (management roles + data roles), a classic surprise when switching clouds.

### 8. Blob vs NoSQL vs SQL *(31.10.2026)*
A blob container is **not** really a NoSQL database. Both store things under a *key* (a name), but they're for different jobs:

| | **Blob container** | **NoSQL DB** (Cosmos DB, DynamoDB, Table storage) | **SQL DB** (PostgreSQL) |
|---|---|---|---|
| Stores | **files**: any bytes | **records/documents** with fields | **rows** in tables with fixed columns |
| Looks inside? | **no**: doesn't know what's in a file | **yes**: find records by fields | **yes**: SQL with joins, averages, filters |
| Usage | upload/download a file **whole** | get/put records, query by key/field | `SELECT AVG(temp) ... GROUP BY hour` |
| Item size | huge (TBs per blob) | small (KBs) | small rows, very many |
| Like | an online folder of files | a searchable filing cabinet | a strict spreadsheet + query language |
| AWS | S3 | DynamoDB | RDS for PostgreSQL |

The NoSQL option *inside* a storage account is **Table storage** (simple key-value).
**In this project:** Terraform state = one file read/written whole → **blob**. Sensor readings = data I'll ask questions of (hourly averages, last reading) with a fixed shape (the contract), used by dbt and Power BI → **PostgreSQL**.

### What does "rm" mean in `az storage container-rm`? *(31.10.2026)*
**RM = Azure Resource Manager (ARM)**, Azure's single front door for *managing* resources (`management.azure.com`). `container-rm` creates the container through ARM, the **control plane**, where my Owner role is enough. Plain `container` uses the **data plane** (the service's own address), which needs a data role or the account's access key. Owner ≠ data access in Azure. → [12-azure-fundamentals.md](12-azure-fundamentals.md), section 7

### Is a blob container like a NoSQL database? *(31.10.2026)*
No. Blob = **files**, stored and fetched whole; it can't look inside or query them (like S3). NoSQL = **records with fields** you can query (Cosmos DB, DynamoDB, Azure Table storage). SQL = **tables** with full queries (PostgreSQL). Terraform state → blob; sensor readings → PostgreSQL. → [12-azure-fundamentals.md](12-azure-fundamentals.md), section 8

**Command 4: versioning + soft delete** *(typed and run by me, 31.10.2026)*
```
az storage account blob-service-properties update --account-name sttfstatebantos --resource-group rg-tfstate --enable-versioning true --enable-delete-retention true --delete-retention-days 7 --output table
```
- `blob-service-properties update`: change settings of the account's **Blob service** as a whole (not one file). A control-plane change through ARM, so Owner is enough.
- `--enable-versioning true`: every overwrite of the state file keeps the previous version, so a broken state can be rolled back.
- `--enable-delete-retention true --delete-retention-days 7`: **soft delete**. A deleted blob goes to a recycle bin for 7 days before it's really gone.
- Cost: old versions are a few KB each, practically nothing.

Checked by Claude (read-only):
```
az storage account blob-service-properties show --account-name sttfstatebantos --resource-group rg-tfstate \
  --query "{versioning:isVersioningEnabled, softDelete:deleteRetentionPolicy.enabled, days:deleteRetentionPolicy.days}" --output table
```
→ `Versioning True | SoftDelete True | Days 7` ✅

**Bootstrap complete:** `rg-tfstate` → storage account `sttfstatebantos` (Standard_LRS, TLS 1.2, no public access, versioning, soft delete) → container `tfstate`.

### Why blob storage for the Terraform state? *(31.10.2026)*
The state is **one JSON file**, Terraform's record of everything it created. Where it lives needs:
| Need | Why | Blob storage provides |
|---|---|---|
| **Shared** | laptop and CI (3.2) must use the *same* state, or they fight over resources | one file at one address both can reach |
| **Durable** | lost state = Terraform forgets what it created | 3 copies (LRS), independent of my laptop |
| **Locked while in use** | two simultaneous `apply` runs would corrupt it | Terraform takes a **blob lease** (temporary lock); a second run gets "state locked" |
| **Private** | state can contain **secrets** in plain text | private container, no public access, TLS 1.2 |
| **Recoverable** | a bad run can break it | versioning + soft delete |

Terraform has a built-in **`azurerm` backend** for this: just name the account, container and file.
**Alternatives:** a local file (Terraform's default: not shared, no locking, lost with the laptop; experiments only); **git: never** (secrets would be public forever, no locking, merge conflicts; `*.tfstate` goes in `.gitignore`); a database (overkill, and ours is created *by* Terraform: chicken-and-egg); HCP Terraform (hosted, adds an external service).
**AWS equivalent:** state in an **S3 bucket** with versioning, plus locking (historically a DynamoDB table; newer Terraform can lock in S3 itself).

### Why is the Terraform state stored in blob storage? *(31.10.2026)*
The state is one JSON file that must be **shared** (laptop + CI), **durable**, **locked** while in use (Terraform takes a blob lease), **private** (it can contain secrets) and **recoverable** (versioning + soft delete). Blob storage does all five, and Terraform's built-in `azurerm` backend uses it directly. Never put state in git (secrets, no locking). AWS: S3 bucket + locking. → [11-terraform.md](11-terraform.md)


### Writing `infra/bootstrap.sh` (I wrote it; Claude reviewed it, 31.10.2026)

**What the file is:** the four bootstrap commands (plus provider registration) saved as a script, so the state backend can be rebuilt identically (step 3.3) and anyone can read exactly what was created. **Committed to git**: it contains no secrets.

**Structure I used** (good):
- `#!/usr/bin/env bash`: the **shebang**. Tells the system to run the file with bash; `env` finds bash wherever it's installed.
- `set -euo pipefail`: `-e` stop at the first failing command; `-u` stop on unset variables (catches typos); `-o pipefail` a failed part of a `|` pipe fails the whole line. Standard at the top of serious bash scripts.
- Variables at the top (`LOCATION=...`, no spaces around `=`), a comment block saying what the script is for, a comment above each command.

**Review: bugs in my first version** (found with `bash -n`, a syntax check that runs nothing):
1. 🔴 **Variables without `$`**: `--name RESOURCE_GROUP` passes the literal text "RESOURCE_GROUP". It would have created a resource group *named* RESOURCE_GROUP, and `--location LOCATION` would fail. Correct: `--name "$RESOURCE_GROUP"` (the quotes protect values containing spaces).
2. 🔴 **Stray ```` ``` ```` at the end**, left over from copying Markdown. A backtick starts *command substitution* in bash, so bash searched for the closing one: `unexpected EOF while looking for matching ``'`. The script wouldn't even start.
3. 🔴 **Spaces after `\`**. `\` continues a command only if it's the **very last character** on the line. With trailing spaces it escapes a space instead, and the command ends there (`az storage account create` with no options), so `set -e` stops the script. Probably the same thing that broke my first container command.
4. 🔴 **Wrong value**: `--resource-group CONTAINER` in the container command; it needs `$RESOURCE_GROUP`.
5. 🟡 **Hard-coded names** in the last command instead of variables. It works, but a renamed variable wouldn't reach it.
6. 🟡 **`2>/dev/null` in a script hides real errors.** With `set -e`, a failing command would stop the script with *no message*. Fine for hiding harmless warnings in the terminal; not in scripts.
7. ⚪ A space before every `\`, 2-space indentation of options, a comment typo.

Correct pattern:
```bash
# Create the resource group that holds only the Terraform state
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output table
```
Checks that run nothing:
```
bash -n infra/bootstrap.sh              # syntax check: silent = OK
grep -n '\\ \+$' infra/bootstrap.sh     # find "\" followed by spaces: no output = OK
```

**Open prediction (idempotency):** what happens if the script runs a second time, when everything already exists? To be checked once the script is fixed.

### Why an `infra/` folder?
A convention separating **application code** (`sensor/`, `bridge/`) from **infrastructure code** (bootstrap + Terraform):
- Terraform reads **every `.tf` file in the folder it runs in**, so it needs its own folder;
- one clear place for "how the cloud is built";
- CI can react by path (e.g. only run `terraform plan` when `infra/` changed, step 3.2).

Other common names: `terraform/`, `iac/`, `deploy/`.

### `chmod` and "executable"
**`chmod` = change mode = change a file's permissions.** `ls -l` shows them:
```
-rwxr-xr-x  1 antoniratajczyk  staff  1712 Oct 31 14:51 bootstrap.sh
│└┬┘└┬┘└┬┘
│ │  │  └─ others:  r-x
│ │  └──── group:   r-x
│ └─────── owner:   rwx  (me)
└───────── "-" = regular file ("d" = directory)
```
r = read, w = write, x = execute (run as a program). Before: `-rw-r--r--`. `chmod +x` added `x` for owner, group and others, giving `-rwxr-xr-x`.

**Executable** = the system may run the file as a program: `./infra/bootstrap.sh`. macOS then reads the **shebang** to know which program runs it.
- Without `x`: "permission denied". `bash infra/bootstrap.sh` still works, because then *bash* is the program and the script is just a file it reads.
- `./` = "in this folder". Without it, the terminal only searches its PATH (`/opt/homebrew/bin`...).
- **Git stores the `x` bit**, so clones can run the script directly.


### Should `bootstrap.sh` be gitignored, since it has names in it? *(31.10.2026)*
**No, commit it.** Test: *"If a stranger had this file, could they get into anything?"* Names, region and settings aren't secrets. The storage account name is even part of a public URL. Security comes from **authentication** (login, keys, roles), not hidden names. Real secrets (account keys, connection strings, passwords, tokens) must never be in the file, and aren't: the script uses my `az login`, which lives in my user profile. If a script ever needs a secret, it reads it from an environment variable or `.env` at runtime.

### What is `chmod`, and what does "executable" mean? *(31.10.2026)*
`chmod` = change mode = change file permissions (`r` read, `w` write, `x` execute, for owner / group / others; see them with `ls -l`). `chmod +x file` adds "may be run as a program": `-rw-r--r--` → `-rwxr-xr-x`. Then `./file` runs it, and the shebang (`#!/usr/bin/env bash`) picks the interpreter. Without `x`: "permission denied" (but `bash file` still works). Git keeps the `x` bit. → [11-terraform.md](11-terraform.md)

### Why must `\` be the last character on a line? *(31.10.2026)*
In bash, `\` + line break = "the command continues on the next line". If any space follows the `\`, it escapes the *space* instead, so the command ends there and the next line runs as a separate (broken) command. Invisible in most editors. Find them with `grep -n '\\ \+$' file`.

### What does `$` do in bash? *(31.10.2026)*
`NAME="value"` sets a variable; **`$NAME` reads it**. Without `$`, bash uses the literal text `NAME`. Write `"$NAME"` in quotes, so values with spaces stay one argument.


### Testing the script with a fake `az` (Claude, 03.11.2026)

After my second version passed `bash -n` and the `grep` check, Claude ran it against a **fake `az`** to see exactly which arguments each call would receive, **without contacting Azure**.

**The idea: a stub.** A stand-in for a real external program that only *prints* what it's given. Same idea as 1.5, where the validator was tested without a broker; here the script is tested without Azure.

**How the swap works: `PATH`.** When a script says `az`, the terminal searches the folders listed in **`PATH`**, in order, and runs the **first** `az` it finds (normally `/opt/homebrew/bin/az`; see `which az`). Put a folder with a different `az` at the *front* of PATH, and the script uses that one.

**The commands:**
```
mkdir -p .../scratchpad/fakebin          # a folder for the fake, outside the project (-p: no error if it exists)
printf '#!/usr/bin/env bash\necho "az called with:"; for a in "$@"; do echo "   [$a]"; done\n' > .../fakebin/az
chmod +x .../fakebin/az                  # make the fake runnable
```
The fake `az` is two lines:
```bash
#!/usr/bin/env bash
echo "az called with:"; for a in "$@"; do echo "   [$a]"; done
```
- `"$@"` = **all arguments** the program received, each kept separate exactly as bash split them;
- `for a in "$@"; do ... done` = loop over them;
- `echo "   [$a]"` = print each **inside brackets**, so you can *see* where each argument starts and ends (glued words, missing spaces).

Run the script with the fake first in PATH:
```
PATH="/private/tmp/claude-501/-Users-antoniratajczyk-Desktop-Project/60d36abb-4847-4ccc-83b7-cab3adc76262/scratchpad/fakebin:$PATH" bash infra/bootstrap.sh
```
- `PATH="fakebin:$PATH"` = my folder first, then the normal PATH (`$PATH` = its current value, `:` separates folders);
- written **before** a command, it applies to **that command only**.

**What it revealed in my second version:**
| Call | Received | Verdict |
|---|---|---|
| Register Storage | `[--namespace] [Microsoft.Storage]` | ✅, but `--wait` was commented out |
| Register Devices | `[--namespace] [Microsoft.Devices#--wait]` | 🔴 |
| Group create | `[--name] [rg-tfstate--location] [northeurope]` | 🔴 |
| Storage account | all options correct | ✅ |
| Container | `[--storage-account] [STORAGE_ACCOUNT]` | 🔴 missing `$` |
| Versioning | right values, typed out | 🟡 not using variables |

- **Devices:** `Microsoft.Devices\` had **no space before `\`**, so bash glued it to the next line `#--wait 2>/dev/null`, giving `Microsoft.Devices#--wait 2>/dev/null`. **A `#` only starts a comment after a space**; glued to a word, it's an ordinary character. And the `2>/dev/null` became *active*, so the error would be thrown away and `set -e` would stop the script **silently**.
- **Group:** `"$RESOURCE_GROUP"\` without a space glued onto `--location`, making the name `rg-tfstate--location`, with `northeurope` left over as a stray argument.
- **Commenting out continuation lines** works only by accident (when there's a space before the `#`). And removing `--wait` means registration continues in the background, so on a new subscription the next command could start too early. Keep `--wait`, drop only `2>/dev/null`, and delete leftover lines instead of commenting them out.

**Three levels of checking a script:**
| Check | Catches |
|---|---|
| `bash -n script.sh` | bash can't even *read* it (e.g. the stray ```` ``` ````) |
| `grep -n '\\ \+$' script.sh` | invisible spaces after `\` |
| **fake `az` in PATH** | it runs but **sends the wrong arguments** (glued words, missing `$`, wrong values) |


### What is `PATH`? *(03.11.2026)*
The list of folders the terminal searches, **in order**, when you type a program name (`az`, `pytest`, `terraform`). It runs the **first** match. See it with `echo $PATH`; see which match wins with `which az`.
- Activating the venv puts `.venv/bin` first, which is why `pytest` is found then.
- `NAME=value command` sets a variable **for that one command only**; e.g. `PATH="mydir:$PATH" bash script.sh` makes the script find programs in `mydir` first.

### What is a stub / fake (like the fake `az`)? *(03.11.2026)*
A stand-in for a real external program or service, used to test *your* code without the real thing. The fake `az` only printed its arguments (`"$@"`, each in `[brackets]`), revealing that the script would send `Microsoft.Devices#--wait` and `rg-tfstate--location`. Same idea as testing the validator without a broker (1.5). → [11-terraform.md](11-terraform.md)

### When is `#` a comment in bash? *(03.11.2026)*
Only at the start of a word: at the beginning of a line or **after a space**. Glued to a word (`Devices#--wait`) it's an ordinary character.


### Why does `bash -n` say "syntax OK" no matter what I put in the script? *(03.11.2026)*
Because it only checks **grammar, not meaning**, and it **runs nothing**. It checks that bash can *read* the script (complete quotes, backticks, `if`/`fi`, `do`/`done`), not whether commands exist, variables are set or arguments make sense. Like a grammar checker accepting "The purple car ate seventeen Tuesdays".
- My experiment: `$HUJ` → `bash -n` says OK (valid grammar). **Running** it → `HUJ: unbound variable`: that's `set -u` stopping at *runtime* on an unset variable (without `-u` it would silently become empty).
- It catches: unclosed `"` or backtick (like the stray ```` ``` ````), `if` without `fi`, `do` without `done`, a stray `(`.
- So use all three checks: `bash -n` (grammar) → `grep -n '\\ \+$'` (spaces after `\`) → fake `az` (real behaviour: glued words, missing `$`, unset variables). Only real `az` can confirm Azure accepts the arguments.


### Third version: all checks pass (03.11.2026)
- `bash -n` → syntax OK; `grep` → no spaces after `\`; **fake `az`** → all six calls receive exactly the right arguments, `--wait` back on both registrations.
- `grep -n "sttfstatebantos\|rg-tfstate\|northeurope" infra/bootstrap.sh` → the names appear **only in the variables** (lines 15–18), so a rename is a one-line change.

### The script ran "in a loop": infinite recursion
When I ran the real script, it never finished. **Cause:** a line `./infra/bootstrap.sh` had ended up *inside* the script (probably pasted by accident), so **the script called itself**: run commands → reach that line → start a new copy from the top → ... forever. **Infinite recursion** = something that calls itself with no condition to stop. Each copy waits for its child, and the child never finishes. The last command (versioning) never ran, because every copy got stuck before it.
- Stop a runaway script with **Ctrl+C** (maybe several times for a self-calling one).
- The fake test didn't catch it, because the line was added *after* the last test. **Re-check after every edit.**

**Damage check (read-only, by Claude):**
```
az group list --query "[].{name:name, location:location}" --output table
az storage account list --query "[].{name:name, group:resourceGroup, sku:sku.name, tls:minimumTlsVersion}" --output table
az storage container-rm list --storage-account sttfstatebantos --resource-group rg-tfstate --query "[].name" --output tsv
az storage account blob-service-properties show --account-name sttfstatebantos --resource-group rg-tfstate --query "{versioning:isVersioningEnabled, softDelete:deleteRetentionPolicy.enabled, days:deleteRetentionPolicy.days}" --output table
```
→ still exactly **one** resource group, **one** storage account (same settings), **one** container; versioning and soft delete still on. Nothing damaged.

### Idempotency, proven by accident
**Idempotent** = running something once or ten times gives the **same end result** (2.1 question). It matters because infrastructure scripts get re-run: after a failure halfway, by CI on every push, or by someone unsure whether it already ran.
- The loop re-ran the first five commands many times against resources that **already existed**. With `set -e`, the first failing command would have stopped everything, so every re-run **succeeded**, and nothing was duplicated.
- Why: `az group create`, `storage account create`, `container-rm create` go through ARM as **"make sure this exists with these settings"** (an HTTP PUT), not "add another one". Re-registering a provider = already registered, nothing to do. The versioning command *sets* values, so setting the same values again changes nothing.
- Counter-example: "append a line to a file" is **not** idempotent. Ten runs = ten lines.
- This is also the core of Terraform: you describe the *end state*, and running `apply` again on an unchanged setup does nothing ("No changes").


### Why did my script run "in a loop"? *(03.11.2026)*
It contained the line `./infra/bootstrap.sh`, so it **called itself**: every copy started a new copy, forever (**infinite recursion**). Stop with Ctrl+C. Nothing was damaged, because every command in it is idempotent. → [11-terraform.md](11-terraform.md)

### What does "idempotent" mean? *(03.11.2026)*
Running it once or ten times gives the **same end result**. Azure's create commands go through ARM as "make sure this exists like this" (PUT), so re-running them changes nothing. Not idempotent: "append a line to a file". Terraform is built on this idea: `apply` on an unchanged setup = "No changes".


### Final version: the real run (run by Claude at my request, 03.11.2026)
Checks first: `bash -n` OK; `grep` found no spaces after `\` and **no self-call**; fake `az` → **exactly 6 calls** (`... | grep -c "az called with"` counts them).

Real run:
```
./infra/bootstrap.sh 2>&1 | grep -v "SyntaxWarning\|excludedActions\|^\s*$"
```
(`2>&1` merges warnings into the normal output; `grep -v` shows everything **except** lines matching the known `az` noise and empty lines (`^\s*$`). Only for readability; the script itself shows everything.)

| Command | Result |
|---|---|
| 2× provider register | finished silently (already registered) |
| resource group | `northeurope rg-tfstate` |
| storage account | `WARNING: A storage account with the provided name sttfstatebantos is found. Will continue to update the existing account.` → `Succeeded` |
| container | `tfstate`, `Deleted: False` |
| versioning | `IsVersioningEnabled: True` |

- **The warning is idempotency in Azure's own words**: it exists, so it just makes sure the settings match.
- `CreationTime: 2026-10-29`: still the **same** account from Thursday, not a new one.
- All settings match: Hot tier, no public blob access, HTTPS only, TLS 1.2, `Succeeded`.

**Bootstrap done.** `infra/bootstrap.sh` is the documented, repeatable recipe for the state backend; committed to git (no secrets in it).


## Step 2.1 — Terraform, part 2: first files (explained by Claude, 03.11.2026)

Checkpoint commit (done by me): `fff538a`, with `infra/bootstrap.sh`, `Brewfile`, `README.md` and `NOTES.md`. CI green. `git ls-files -s infra/bootstrap.sh` → `100755`: git stored the executable bit (`755` = `rwxr-xr-x`). The typos in the message stay, because pushed history isn't rewritten.

### Terraform from zero
I write **`.tf` files describing the end state**; Terraform makes Azure match.
| Command | What it does |
|---|---|
| `terraform init` | one-time setup per folder: downloads the **provider** (plugin that talks to Azure) and connects to the state backend |
| `terraform plan` | **preview**: compares files + state + real Azure, prints what it *would* create/change/destroy; changes nothing |
| `terraform apply` | does what the plan said, after I type `yes` |
| `terraform destroy` | deletes everything this configuration created |

**HCL**, the file format, is made of blocks:
```hcl
block_type "label" {
  argument = "value"
  nested_block {
    other_argument = 123
  }
}
```
- Terraform reads **every `.tf` file in the folder as one configuration**; splitting into files is only for humans. Convention: `versions.tf` (settings + providers), `main.tf` (resources), later `variables.tf`, `outputs.tf`.
- Strings in `"quotes"`, `=` assigns, `#` comments.

### Task 1: `.gitignore` for Terraform
```
.terraform/        # downloaded provider plugin: big, machine-specific, re-downloaded by init
*.tfstate          # state files: may contain secrets (ours lives in Azure; this guards against local copies)
*.tfstate.*        # state backups
crash.log          # written if Terraform crashes
```
**Commit `.terraform.lock.hcl`**: it records the exact provider version, so the laptop and CI use the same one (like pinned `requirements.txt`).

### Task 2: `infra/versions.tf`, two blocks
**`terraform { ... }`**, settings for Terraform itself:
- `required_version = ">= 1.9"`: refuse older Terraform versions.
- `required_providers { azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" } }`:
  - `azurerm` = the **Azure Resource Manager provider**: turns `.tf` files into ARM requests;
  - `source` = download from the Terraform Registry, publisher `hashicorp`;
  - `~> 4.0` = **pessimistic constraint**: any 4.x, never 5.0 (major versions may break things; upgrade on purpose).
- `backend "azurerm" { ... }`: **where the state lives** (= the bootstrap):
  | Argument | Value |
  |---|---|
  | `resource_group_name` | `"rg-tfstate"` |
  | `storage_account_name` | `"sttfstatebantos"` |
  | `container_name` | `"tfstate"` |
  | `key` | `"iot.terraform.tfstate"`, the state file's name inside the container |
  - **The backend block can't use variables**: Terraform reads it before anything else exists.

**`provider "azurerm" { features {} }`**: settings for the Azure plugin. `features {}` is required, even empty.

**Subscription ID via an environment variable** (azurerm v4 requires it; not a secret, but no reason to publish it):
```
export ARM_SUBSCRIPTION_ID=$(az account show --query id --output tsv)
```
- `$(...)` = run the inner command and paste its output;
- `export NAME=value` = set it for this terminal session and every program started from it;
- the provider reads `ARM_SUBSCRIPTION_ID` automatically. **Per terminal tab**, like the venv.

### Then
```
cd infra
terraform init
```
Expected: "Successfully configured the backend azurerm!", "Installing hashicorp/azurerm v4.x.x", "Terraform has been successfully initialized!". Creates `.terraform/` and `.terraform.lock.hcl`.


### Why don't I see any files after `terraform init`? *(03.11.2026)*
Two separate reasons to check:
1. **Hidden files.** Names starting with a dot (`.terraform/`, `.terraform.lock.hcl`, `.gitignore`, `.venv/`) are **hidden** by `ls` and Finder. `ls -la` shows them: `-a` = all files including hidden, `-l` = long list with permissions and sizes. (In Finder: Cmd+Shift+. toggles hidden files.)
2. **`init` in a folder with no `.tf` files** doesn't fail. It prints "Terraform initialized in an empty directory!" and creates **nothing**. In my case `versions.tf` had never been saved, so `infra/` contained only `bootstrap.sh`. Checked with:
```
ls -la infra/                                    # what's really in the folder
find . -name "*.tf" -not -path "./.venv/*"       # search the project for .tf files
```
In VS Code, an **unsaved** tab shows a dot (●) instead of ✕. Create files by right-clicking the folder → New File, then Cmd+S.


### The big picture of step 2.1 (the "builder" analogy)
- **`.tf` files = the blueprint**: I write what should exist.
- **Terraform = the builder**: reads the blueprint, builds it in Azure.
- **State file = the builder's notebook**: "I built X, it's at Y". Without it the builder forgets what it built.
- **Bootstrap = the shelf for the notebook**: the storage account, built first, by hand.

| # | Step | Analogy |
|---|---|---|
| A | bootstrap (`infra/bootstrap.sh`) | build the shelf |
| B | `infra/versions.tf` | which **toolbox** (azurerm plugin) + **where the notebook is** (backend). Creates nothing in Azure |
| C | `terraform init` | fetch the toolbox, open the notebook |
| D | `infra/main.tf` + `plan` + `apply` | the first real blueprint: a resource group |
| E | IoT Hub + budget in code | more blueprint |
| F | `destroy` → `apply` → `plan` says "No changes" | README "done when" |

### Writing `versions.tf`: my mistakes and fixes (04.11.2026)
1. `required version` → **`required_version`**. Argument names never contain spaces.
2. Missing `backend "azurerm"` block.
3. `provider "azurerm"` was *inside* `terraform { }` and had no `{ }`. It's a **separate block after** `terraform` closes, with `features {}` inside.
4. Typo `storage_acount_name` → `storage_account_name`. Terraform only accepts exact argument names ("unsupported argument").
5. I put `infra/versions.tf` in `.gitignore`, thinking it held secrets. **Wrong: it only has names and versions, and must be committed** (or CI can't run Terraform). `.gitignore` gets Terraform's **generated** files instead: `.terraform/`, `*.tfstate`, `*.tfstate.*`, `crash.log`.
   **Rule:** commit what *I write* (`.py`, `.tf`, `.sh`, Dockerfile, `.yml`); ignore what's **generated** (`.venv/`, `__pycache__/`, `.terraform/`) and **real secrets** (`.env`, `*.tfstate`).

Every `{` needs a matching `}`. The file is two blocks side by side:
```
terraform {          ← block 1 opens: version, required_providers, backend
}                    ← block 1 closes
provider "azurerm" { ← block 2 opens
  features {}
}                    ← block 2 closes
```

**`terraform fmt`**: rewrites `.tf` files in Terraform's one official style (2-space indent, aligned `=`), like `ruff --fix` for Python. `terraform fmt -check -diff` only *shows* differences, changing nothing.

### `terraform init` + `terraform plan` (04.11.2026)
I ran `init` (without the `export`), then `plan`:
```
Acquiring state lock. This may take a few moments...
No changes. Your infrastructure matches the configuration.
Releasing state lock. This may take a few moments...
```
- **Why "No changes":** the blueprint is still empty. `versions.tf` is only settings, with no resources. Plan compared my files ("nothing should exist"), the state ("nothing built") and Azure (only resources Terraform *manages*: none), so there was nothing to do. Correct starting point.
- Terraform ignores `rg-tfstate` and the storage account, because the bootstrap made them with `az` and they aren't in its state. Deliberate.
- **`Acquiring/Releasing state lock`** = the blob **lease** (locking) seen live: no second run could change the state meanwhile.

What `init` created (checked by Claude, read-only):
```
ls -la infra/                                       # .terraform/ and .terraform.lock.hcl appeared (hidden: start with a dot)
az storage blob list --account-name sttfstatebantos --container-name tfstate --auth-mode key \
  --query "[].{name:name, size:properties.contentLength}" --output table
```
- `.terraform/` = the downloaded plugin (gitignored).
- `.terraform.lock.hcl` = **azurerm 4.81.0** locked (within `~> 4.0`). **Commit it.**
- In Azure: **`iot.terraform.tfstate`, 181 bytes**, the `key` from `versions.tf`. A near-empty notebook. Backend proven end to end.
- (`--auth-mode key` = read the blob list using the account key, which `az` fetches through ARM because I'm Owner: the "data door" from the Azure guide §7.)

**Why it worked without `export ARM_SUBSCRIPTION_ID`:** with no resources, the provider never made Azure requests, so it never needed the subscription ID; the backend used my `az login` directly. Once `main.tf` has a resource, the provider needs it, so `export` first.

### Quick questions (04.11.2026)
- **Why "No changes" after `init`?** No resources described yet; `versions.tf` is only settings. Terraform only manages resources in its own state, so the bootstrap resources are ignored.
- **What goes in `.gitignore`?** Commit what I write (incl. `.tf` and `.terraform.lock.hcl`); ignore generated files (`.venv/`, `.terraform/`) and real secrets (`.env`, `*.tfstate`).
