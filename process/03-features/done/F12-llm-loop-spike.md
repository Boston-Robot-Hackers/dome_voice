# F12 — LLM conversation loop (spike)

**Date Created:** 2026-11-20

**Priority**: Medium
**Done:** yes
**Tasks File Created:** yes
**Tests Written:** yes
**Test Passing:** yes
**Description**: An experiment. Speech goes from the robot's mic to a node on the VM, which transcribes it, sends it to an LLM, and sends the reply back. The robot speaks it.

## Intent

Find out whether open-ended spoken conversation is worth building, and what the round trip feels like: latency, transcription quality, reply quality.

**This is a spike, not production code.** All of its code lives in this repo, in `spikes/llm_loop/` (next to `dome_voice/` and `test/`). It isn't part of the installed Python package and has no `ros2 run` entry points. It does not touch the command path, `/intent`, or the stop path, so the spec's offline rule for commands still holds.

## Shape

```
robot: mic → wake word → capture until silence → /voice/utterance (raw PCM)
VM:    /voice/utterance → faster-whisper → Claude API → /voice/llm_reply (String)
robot: /voice/llm_reply → /announcement → speech_output (Piper) → speaker
```

## Decisions

- **The VM transcribes.** The robot sends raw audio: 16 kHz mono int16, as `std_msgs/UInt8MultiArray` on `/voice/utterance`. The audio gets `stt_gain_db`, because the mic is quiet (I02).
- **The robot side reuses the runtime's wake and capture helpers** (`wait_for_wake`, `read_mono_chunk`, the silence cutoff). Vosk is not used.
- **The spike has its own wake word**, apart from the fixed grammar's "hey marvin". **"hey robbie" is the goal**; it needs a custom openWakeWord model (F14). Until then `hey_jarvis` stands in.
- **STT is faster-whisper** (`base.en`), local on the VM. It's one pip install, and the model downloads on first run.
- **The LLM is Claude**, through the `anthropic` Python SDK. It is the easiest to set up: one pip install and an API key, with no model to download and no GPU. It uses `claude-haiku-5-5` at low effort, the fastest model, since replies are one or two sentences (switched from `claude-opus-5-5` on 2026-11-20; Opus took 1.4–1.8 s per reply). Haiku has no server-side refusal fallback, so a refusal gets a fixed spoken reply. It keeps the conversation history, and is told to answer in one or two short spoken sentences.
- **Transport is plain ROS 2 topics.** The robot and the VM share a network and a `ROS_DOMAIN_ID`.
- **The VM replies with a plain `String`; the robot relays it to `/announcement`.** Publishing `Announcement` from the VM would mean building `dome_control` there, which pulls in `dome_semantic`, `dome_telemetry_msgs`, and `better_launch`. With the relay on the robot, the VM needs only stock ROS 2.

## Limits

- **The mic opens only once.** While the spike runs, `voice_input` must not be running, so `speech_output` is started by itself.
- **No echo cancellation:** the robot might hear its own reply. The spike ignores the mic while `speech_output` is speaking only if this turns out to be a problem.

## How to Demo
**Setup**: See `spikes/llm_loop/README.md`. On the robot, `speech_output` runs alone. On the VM, `ANTHROPIC_API_KEY` is set and `vm_llm_node.py` is running.

**Steps**:
1. On the robot, run `python3 /home/pitosalas/ros2_ws/src/dome_voice/spikes/llm_loop/robot_mic_pub.py`.
2. Say "hey jarvis", wait for the beep, then ask an open question ("what's the tallest mountain in Europe?").
3. Wait for the robot to speak.

**Expected output**: The robot speaks a short, relevant answer. The VM node logs the transcript, the reply, and the time for each stage (STT, LLM).

## Findings (TF12.3, 2026-11-20)

**Setup:** 8 exchanges, Haiku (`claude-haiku-5-5`, low effort), Whisper `base.en` on the VM, wake word `hey_jarvis`, robot standing still.

### Latency

- **STT:** 0.3 s, once 0.7 s.
- **LLM:** 0.7–1.1 s.
- **About 3.5 s from the end of speech to the first spoken word**, estimated, not measured: 1.0 s of silence to end the turn, 1.0–1.4 s of STT and LLM, and about 1.3 s for Piper to start.
- **The silence cutoff and Piper's start are now the larger costs**, not the LLM.

### Transcription

- **5 of 8 were right.** 3 had errors:
  - "I'm here robot joke": the start of the sentence was lost.
  - "spot or curve" for "Spock or Kirk".
  - "steak on the bread", probably a misheard word.
- **The LLM covers for errors well.** It guessed "robot joke" and asked a short question about "spot or curve". The next turn, said again with context, came through clean.
- **A cut-off start is a capture problem, not a Whisper one.** F10 (keeping the audio from before wake detection) applies to this path too.

### Replies

- **Short, spoken-style, on topic**, and they kept context across turns (the Star Trek follow-up).
- **No command-like request did anything.** "explore" got chat back, and "what do you see?" got "I don't have a camera". This was expected, since the spike has no tools; the requests still show what a command path needs:
  - `/intent` tools for commands: exploration, motion, navigation.
  - Robot state in the prompt or as tools: time, what it sees, status.

### Self-hearing

- **None seen.** No transcript in the log matches one of the robot's replies.

### Recommendation: go

**Go, with a feature (F14) for an LLM command path next to the fixed grammar.**

- Claude gets the `/intent` contract as tool definitions, so one request either emits an intent or answers.
- Perception and status queries become tools too.
- It gets its own wake word, "hey robbie", trained in F14.
- With no network, it says it is offline.

**Still open for F14:**
- Measure the latency end to end, rather than estimate it.
- Check self-hearing with longer replies and with the motors running.
- Measure the wake word's hit and false-wake rates.
