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