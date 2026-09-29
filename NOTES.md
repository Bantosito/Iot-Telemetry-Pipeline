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

1.3Why 30 seconds specifically (work it out from the 8,000 msg/day free-tier limit)? Why read settings from env vars instead of hardcoding? What does the script do when asked to stop?:

    30 seconds message frequency is done to not go over the day limit of 8000msgs per day as there. It only accounts for 36%  of  dailylimit so there can be more devices aadded in the future. 

    The script nejaces differently in different places without code change. For example fake esp32 and real esp or local instance, docker instance and azure instance in the future. Env variables keep anythign secret out of source code.

    If you mean main.py it stoops the loop disconects and logs that 

What I'd do differently:

(shutdown-behavior answer still open — the sensor's _handle_signal / while-loop / finally-block walkthrough from chat)

## Playground observations — 29.9.2026

**Setup:** broker + bridge running, a fourth terminal subscribed to everything (`mosquitto_sub -t '#'`), then a *second* fake sensor process started without overriding `DEVICE_ID` — so it also defaulted to `sensor-01`.

**What happened:** both sensor processes published to the exact same topic (`telemetry/sensor-01`) under the same `device_id`. Neither the broker nor the bridge distinguished them. The broker has no concept of topic ownership — a topic is just a string, anyone connected can publish to it. The bridge's `validate()` only checks that `device_id` is a non-empty string; it never checks that it matches who's actually connected. Downstream, the two processes' readings were completely indistinguishable — interleaved, unattributable, no way to tell which one was "real."

**Why this matters:** same root cause as the anonymous-access risk from 1.2 — nothing on the wire proves who's sending a message. `device_id` is 100% self-declared in the payload right now, enforced by nothing. Anyone who can reach the broker can claim to be any device, including one that already exists (device spoofing).

**Where this gets fixed:** Azure IoT Hub (step 2.2, not built yet) gives each device its own identity and credentials — the *connection itself* is authenticated, not just a field in the JSON payload. That closes the broker-level gap. Worth digging into properly when we get there: even with per-device auth, it's still worth checking that the authenticated identity matches the `device_id` claimed *inside* the message — otherwise a legitimately-connected device could still spoof a different device's `device_id` in its payload. **Flagged to dig deeper at step 2.2.**

**MQTT keep-alive (the "ping back and forth" noticed on the bridge's connection):** on connect, a client negotiates a keep-alive interval with the broker (paho-mqtt defaults to 60s). If no other traffic passes in that window, the client sends a PINGREQ and the broker replies PINGRESP — a heartbeat with no payload, just proving the connection is still alive. If the broker hears nothing at all (not even a ping) for 1.5x the keep-alive interval, it assumes the client is dead and closes the connection — and would fire a Last Will message if one were configured (this project doesn't use one yet). That's how the broker tells "genuinely dead" apart from "quiet because there's nothing new to publish."