# F12 — LLM conversation loop (spike)

**Priority**: Medium
**Done:** no
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
2. Say "hey marvin", wait for the beep, then ask an open question ("what's the tallest mountain in Europe?").
3. Wait for the robot to speak.

**Expected output**: The robot speaks a short, relevant answer. The VM node logs the transcript, the reply, and the time for each stage (STT, LLM).
