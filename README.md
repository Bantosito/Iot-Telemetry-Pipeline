# IoT telemetry pipeline — build guide

[![CI](https://github.com/Bantosito/Iot-Telemtr-Pipeline-Course/actions/workflows/ci.yml/badge.svg)](https://github.com/Bantosito/Iot-Telemtr-Pipeline-Course/actions/workflows/ci.yml)

A sensor at home streams readings into Azure, where they're stored, modelled and shown in a report. The cloud side is defined in code and deployed automatically.

This file is the plan. **It contains no code on purpose.** Each step tells you what the piece is, why it exists, what to build, how you know it's done, and questions you should be able to answer afterwards.

**How this was built:** I built this project with an AI pair programmer (Claude Code), which wrote much of the code with me. To make sure I understood every piece rather than just collecting it, each step has a gate: before moving on, I answer that step's questions in my own words in [`NOTES.md`](NOTES.md), my learning log for the whole project.

```
 AT HOME                                          AZURE
 ┌──────────┐  MQTT  ┌───────────┐  ┌────────┐     ┌─────────┐  ┌──────────┐  ┌────────────┐  ┌─────────────┐
 │  sensor  │ ─────► │  broker   │─►│ bridge │ ──► │ IoT Hub │─►│ Function │─►│ PostgreSQL │─►│ dbt →       │
 │ (fake →  │        │(Mosquitto)│  └───┬────┘     └─────────┘  └──────────┘  └────────────┘  │ Power BI    │
 │  ESP32)  │        └───────────┘      │ bad readings                                         └─────────────┘
 └──────────┘                           ▼
                                  dead-letter topic
```

---

## How to use this guide

- **One step at a time, in order.** Each builds on the last.
- **Commit at the end of every step**, with a message saying what now works. Your commit history is part of the portfolio.
- **Answer the questions in `NOTES.md`** in your own words. If you can't answer one, you haven't finished the step. These answers are your interview preparation.
- **Stuck for 45 minutes?** Stop. Write down exactly what you expected, what happened, and what you tried. Then ask (me, docs, a forum). Writing it down solves it half the time.
- **Use AI to explain, not to write.** Ask "why does this error happen?" rather than "write this for me".

Time budget: about 9 hours a week of building. Each week has a milestone. If you miss one, note why in `NOTES.md` and carry on. Don't restart.

---

## The message contract

Every part of the pipeline agrees on this shape. Decide it before writing code; it's the one design document everything else depends on.

| Field | Type | Rule |
|---|---|---|
| `schema` | integer | Always `1` for now. Lets you change the format later without breaking old data. |
| `device_id` | string | Not empty. Which sensor sent it. |
| `ts` | string | ISO 8601 **with a timezone**, e.g. `2026-09-23T12:00:00+00:00`. |
| `temperature_c` | number | Between -40 and 125. |
| `humidity_pct` | number | Between 0 and 100. |

The whole message must stay under **512 bytes**. The IoT Hub free tier counts messages in 0.5 KB chunks, so a bigger one costs double.

**Questions:** Why include a schema version? Why must the timestamp have a timezone? What goes wrong if the sensor's clock is wrong?

---

# Week 1 — The home half

**Milestone:** readings flow from a fake sensor through the broker to the bridge, bad ones are caught, it all starts with one command, and CI is green on GitHub.

## 1.1 Repo and tools

**What it is:** your GitHub repository and local setup.

**Build:**
- A public GitHub repo with this README, a `.gitignore` and an empty `NOTES.md`.
- Install Python 3.12, Docker Desktop, Git, VS Code, and the Mosquitto command-line tools (`mosquitto_pub`, `mosquitto_sub`).
- Create a Python virtual environment for the project.

**Done when:** the repo is on GitHub and `docker run hello-world` works.

**Questions:** What does a virtual environment protect you from? What belongs in `.gitignore`, and why must secrets never be committed, even if you delete them later?

## 1.2 The broker (Mosquitto)

**What it is:** an MQTT broker is a post office for small messages. Devices **publish** to a **topic** (like `telemetry/sensor-01`), and anyone **subscribed** to that topic receives it. Senders and receivers never talk directly, so you can add or remove either side without touching the other. It's the standard way IoT devices send data, because it's light enough for a microcontroller.

**Build:** run Mosquitto in a Docker container on port 1883 with a small config file. For now, allow anonymous connections, and write a comment saying that this is only acceptable locally.

**Done when:** in two terminals, `mosquitto_sub -t 'test/#' -v` receives what you send with `mosquitto_pub -t test/hello -m "hi"`.

**Questions:** What do `+` and `#` mean in a topic subscription? What are QoS 0, 1 and 2, and which would you pick for sensor readings? Why is anonymous access dangerous if the broker were reachable from the internet?

## 1.3 The fake sensor

**What it is:** a small Python script that pretends to be the ESP32. It lets you build and test everything else before touching hardware.

**Build:** using the `paho-mqtt` library, publish a reading that follows the contract every N seconds (read N from an environment variable; default 30). Make the values drift slowly, like real temperature does, rather than jumping randomly. Add a setting that deliberately sends a broken message some of the time. You'll need it later.

**Done when:** `mosquitto_sub` shows a new, valid reading every few seconds, and the script retries rather than crashing if the broker isn't up yet.

**Questions:** Why 30 seconds? (Work it out: the free IoT Hub tier allows 8,000 messages a day.) Why read settings from environment variables instead of hard-coding them? What does your script do when it's asked to stop?

## 1.4 The bridge

**What it is:** the gatekeeper between your home and the cloud. It subscribes to all sensor topics, **validates** every message against the contract, and forwards the good ones. Bad ones are published to a **dead-letter topic** together with the reason they were rejected. Nothing is silently thrown away, so a broken sensor shows up as data you can see, not a mysterious gap.

**Build:**
- One function that takes raw message bytes and either returns a clean reading or raises an error saying exactly what's wrong. Keep it separate from the MQTT code; it's the part you'll test.
- The MQTT part: subscribe, call that function, forward or dead-letter.
- "Forward" for now means printing to the log. Design it so the destination can be swapped for Azure later without rewriting the rest.
- If forwarding fails, log it, count it and keep running.
- Every minute, log how many valid, invalid and failed messages it has seen.

**Done when:** with the broken-message setting on, good readings are logged, bad ones appear on the dead-letter topic with a clear reason, and valid + invalid equals messages sent.

**Questions:** Why validate at home rather than only in the cloud? Why should one bad message never crash the bridge? If the bridge restarts, does it miss messages? Why subscribe inside the "on connect" callback rather than once at startup?

## 1.5 Tests

**What it is:** code that checks your code, so you can change things without fear.

**Build:** `pytest` tests for the validation function only. One test for a valid reading, then one for each way a message can be wrong: not JSON, not an object, too big, wrong schema, missing or empty device, bad or timezone-less timestamp, missing, non-numeric or out-of-range values. Tip: in Python `True` counts as a number. Decide whether your validator should accept it.

**Done when:** all tests pass, and deliberately breaking the validator makes at least one fail.

**Questions:** Why test the validation function but not the MQTT connection? What's a parametrised test and why is it useful here?

## 1.6 Docker Compose

**What it is:** Docker packages each program with everything it needs into an **image**, so it runs the same on any machine. Compose starts several containers together, on a shared network where they find each other by service name.

**Build:** a `Dockerfile` each for the sensor and the bridge (small Python base image, install requirements, run as a non-root user), and a `docker-compose.yml` that starts broker, sensor and bridge. Settings come from a `.env` file that isn't committed. Commit a `.env.example` instead.

**Done when:** on a clean checkout, `docker compose up --build` runs the whole thing, and it recovers if you restart any single container.

**Questions:** Why can the bridge reach the broker at `mosquitto` instead of `localhost`? What's the difference between an image and a container? Why not run as root inside a container? What does `depends_on` guarantee, and what doesn't it?

## 1.7 CI (GitHub Actions)

**What it is:** continuous integration. A robot runs your checks on every push, so broken code is caught immediately, and the green badge shows reviewers it works.

**Build:** a workflow in `.github/workflows/` that installs dependencies, runs a linter (`ruff`) and the tests, and builds the Docker images.

**Done when:** a push turns green, a push with a failing test turns red, and the README shows the status badge.

**Questions:** What triggers your workflow? Why also build the images in CI, not only run tests?

## 1.8 Azure account and budget alert

**What it is:** your cloud account, and a safety net. **Do this before creating anything else in Azure.**

**Build:** create an Azure free account. Then set up a monthly budget with email alerts, at 50% actually spent and at 100% forecast. Check which currency your account is billed in first. Do it in the portal this time; you'll define it in code in week 2.

**Done when:** the budget exists and you understand what the free account includes, for how long, and what happens after the first 30 days.

**Questions:** What in this project could cost money? What's the difference between "actual" and "forecasted" in a budget alert?

---

# Week 2 — Into Azure

**Milestone:** a reading sent at home ends up as a row in a PostgreSQL table in Azure.

## 2.1 Infrastructure as code (Bicep)

**What it is:** instead of clicking resources together in the portal, you describe them in a file, and Azure creates exactly that. The file is the documentation, it can be reviewed, and you can delete everything and recreate it identically. This is the skill you didn't get to own at Everllence.

**Build:** a `main.bicep` for a resource group deployment, starting with the IoT Hub, plus the budget from 1.8 rewritten as a subscription-level Bicep file. Deploy with the Azure CLI (`az deployment ...`).

**Done when:** you can deploy it, delete the resource group, and deploy it again with the same result.

**Questions:** What's a resource group? What does "idempotent" mean, and why does it matter here? Why must some resource names be globally unique, and how do you generate one?

## 2.2 IoT Hub

**What it is:** Azure's front door for devices. Each device has its own identity and credentials, so the hub knows who sent what and can block one device without affecting others.

**Build:** the free (F1) tier. Register one device identity for your bridge, get its connection string, and keep it only in `.env`. Add an IoT Hub destination to the bridge alongside the log destination.

**Done when:** `az iot hub monitor-events` shows your readings arriving in Azure.

**Questions:** Why is the bridge one "device", not each sensor? What are the free tier's limits? What happens when you exceed them?

## 2.3 PostgreSQL

**What it is:** where the readings are stored. A managed database: Azure handles backups and updates.

**Build:** an Azure Database for PostgreSQL flexible server, Burstable B1ms (check it's covered by your free account), in Bicep. Design the raw readings table yourself: which columns, which types, what the primary key is, and how to stop the same reading being inserted twice.

**Done when:** you can connect from your laptop and query an empty table you created.

**Questions:** Why store raw readings rather than only averages? How do you prevent duplicates? Why restrict which IP addresses can connect?

## 2.4 Azure Function

**What it is:** a small piece of code that Azure runs whenever something happens, here whenever a message reaches the IoT Hub. You don't manage a server. You've used these at Everllence; the new part is defining and deploying it yourself.

**Build:** a Python Function triggered by IoT Hub messages (via its built-in Event Hub-compatible endpoint) that writes each reading into Postgres. Add the Function App to your Bicep.

**Done when:** a reading sent at home appears as a row within a minute. **That's the week 2 milestone.**

**Questions:** What happens if the database is down when a message arrives? What's a consumer group? Why might the same message be processed twice, and how does your table design cope?

---

# Week 3 — Automate it

**Milestone:** delete the whole resource group, run one pipeline, and everything comes back working.

## 3.1 Managed identity

**What it is:** a way for Azure resources to prove who they are to each other without passwords. The Function gets an identity, and the database trusts that identity.

**Build:** give the Function App a managed identity and use it to connect to Postgres (Microsoft Entra authentication) instead of a password.

**Done when:** there's no database password anywhere in the Function's settings.

**Questions:** Why is a managed identity safer than a password in a setting? What's the principle of least privilege, and what permissions does the Function actually need?

## 3.2 Deployment pipeline (OIDC)

**What it is:** GitHub Actions deploying to Azure. OIDC (federated credentials) lets GitHub prove to Azure which repository and branch is asking, so no long-lived secret is stored in GitHub.

**Build:** a workflow that, on push to `main`, validates the Bicep, deploys it, then deploys the Function code. Set up the federated credential in Microsoft Entra.

**Done when:** a push to main updates Azure with no manual steps, and no Azure password or secret key is stored in GitHub.

**Questions:** Why is OIDC better than storing a secret? What happens if someone opens a pull request from a fork?

## 3.3 Teardown and rebuild

**Build:** delete the resource group. Run the pipeline. Re-register the device, update `.env`, and confirm readings flow again. Write down every manual step you still needed; each one is something to automate or document.

**Done when:** you've rebuilt from nothing and recorded how long it took. **That's the week 3 milestone.**

---

# Week 4 — Make it useful, then break it

**Milestone:** a modelled dataset, a report, and a written incident.

## 4.1 dbt

**What it is:** a tool for transforming data inside the database using SQL files, with tests and documentation built in. It's how data teams turn raw tables into trustworthy ones, and it appears in many Danish data engineering job ads.

**Build:** a dbt project with a **staging** model (clean up the raw table) and **marts** (e.g. hourly averages per device, and a device dimension). Add tests: not null, unique, accepted ranges, and a freshness check on the raw data.

**Done when:** `dbt build` runs green and you can show the lineage graph.

**Questions:** Why separate staging from marts? What does a freshness test catch that a unit test can't? How is this like the star schemas you built in Power BI?

## 4.2 Power BI

**What it is:** your existing strength, on top of the new platform.

**Build:** a small report on the marts: temperature over time per device, and a "last reading received" indicator.

**Done when:** a screenshot is in the README.

## 4.3 Incident drill

**What it is:** practice at what you said you want to do: putting out fires.

**Build:** add an alert that fires when no readings have arrived for 10 minutes (Application Insights or Azure Monitor). Then break things on purpose, one at a time: stop the bridge, send malformed messages, stop the database, exceed the free-tier quota if you dare. For at least one, write an incident note in the README: what broke, how you noticed, how long it took to find, what you changed so it's caught faster next time.

**Done when:** the alert reached your phone, and the incident note is in the README. **That's v1.**

---

# After v1

- Swap the fake sensor for a real ESP32. The contract doesn't change, which is the point of having one.
- Rewrite the bridge in Go, and compare memory use and image size with the Python version.
- Run the home half on a Raspberry Pi or mini PC instead of your laptop.

---

## NOTES.md template

```
## Step X.Y — <name>
Date:
What I built:
What surprised me / what broke:
Answers to the questions:
What I'd do differently:
```

## Reference docs

- Mosquitto: https://mosquitto.org/documentation/
- paho-mqtt (Python): https://pypi.org/project/paho-mqtt/
- Docker Compose: https://docs.docker.com/compose/
- GitHub Actions: https://docs.github.com/actions
- Azure IoT Hub, Bicep, Functions, PostgreSQL flexible server, managed identities: search each name on https://learn.microsoft.com
- dbt: https://docs.getdbt.com/
