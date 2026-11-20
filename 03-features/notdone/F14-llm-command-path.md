# F14 — LLM command path, next to the fixed grammar

**Date Created:** 2026-11-20
**Priority**: High
**Done:** no
**Tasks File Created:** yes
**Tests Written:** no
**Test Passing:** no
**Description**: A second way to talk to the robot. A wake word of its own ("hey robbie") sends the turn to Whisper and Claude on the VM. Claude either emits an `/intent` (explore, turn, go somewhere, describe what it sees) or answers in speech, including general questions and chat. Code can also send Claude a question as text, for example a gamepad button for "tell me a robot joke". The fixed grammar ("hey marvin") keeps working unchanged.

## Intent

F12 showed the loop is fast enough (STT 0.3 s, Haiku 0.7–1.1 s) and copes well with transcription errors. What it lacked was the ability to *do* anything. This feature turns it into a command path, so it can replace the fixed grammar where open speech helps.

**This is production code**, in the `dome_voice` package, and it replaces the spike's scripts.

## Shape

```
robot  voice_input: mic → wake word
         "hey marvin" → Vosk grammar → IntentMapper → /intent        (unchanged)
         "hey robbie" → capture → /voice/utterance (16 kHz int16 PCM)
VM     llm node: /voice/utterance → Whisper → Claude (with tools)
         tool call → /intent  (JSON String, source "llm")
         always    → /voice/llm_reply (String; empty when nothing to say)
robot  voice_input: /voice/llm_reply → /announcement → speech_output

any node: /voice/llm_text (String) → VM llm node, skipping Whisper    (e.g. a gamepad button)
```

## Decisions

- **One mic process, two wake words.** The mic opens only once, so `voice_input` listens for both. openWakeWord scores several models in one pass, and the one that fires picks the path.
- **The LLM path is off unless `voice.yaml` names `llm_wake_word`.** With it set to `none`, `voice_input` behaves exactly as today.
- **Claude gets the `/intent` contract as tools**, one tool per intent the consumers handle:
  - dome_control: `stop`, `turn_left`, `turn_right`, `describe_scene`, `list_objects`, `get_status`.
  - dome_mission: `exploration_start`, `exploration_stop`, `navigation_go` (slot `label`), `navigation_cancel`.
- **Queries are intents too.** `describe_scene`, `list_objects` and `get_status` are answered by dome_control with an announcement, so Claude doesn't need to see the camera itself.
- **The VM publishes `/intent` directly.** It is a JSON `std_msgs/String`, so the VM still needs only stock ROS 2.
- **The VM always answers each utterance on `/voice/llm_reply`**, with an empty string when an intent's consumer will do the talking. That one-reply rule is what makes the offline check below possible.
- **No network → "I'm offline".** If no reply arrives within `llm_timeout_secs`, `voice_input` announces that the LLM path is offline. If the VM is up but the Claude API fails, the VM replies with a fixed sentence.
- **General questions and chat are first-class.** Claude answers them in speech and calls no tool, as in the F12 spike.
- **Text in, as well as speech.** The VM node also takes questions as text on `/voice/llm_text` and treats them like a transcript. Text and speech share one conversation history.
- **The system prompt has two parts.**
  - **Fixed rules** live in code: speak in short plain sentences, use the tools for commands, and expect speech-recognition errors.
  - **The persona** is a separate text file, `config/llm_persona.md`: who the robot is, where it comes from, its likes, dislikes and attitude.
- **F14 ships only a placeholder persona** (name and a single sentence). Writing the real one is later work, and needs no code change, only a node restart. A missing persona file is an error, not a silent default.
- **The current time starts each user message**, so "what time is it?" works without a tool. It isn't in the system prompt, so that prompt stays the same across turns and can be cached.
- **Wake word:** `hey_jarvis` stands in until a "hey robbie" model is trained (T05).

## Safety

- **The LLM path is never the stop path.** Claude has a `stop` tool, because people will say "stop" to it, but stopping must not depend on the network. F07's always-on stop phrase stays the safety path.

## Out of scope

- **Place names from the map** (F09). Claude passes whatever label it hears to `navigation_go`; dome_mission decides whether it knows the place.
- **Writing the persona.** F14 only loads it from its file.
- **Gamepad buttons.** F14 only provides `/voice/llm_text`; mapping buttons to text comes later, and is tested with `ros2 topic pub` until then.
- **A status update written by Claude.** "Give a full update on the robot status" calls `get_status`, and dome_control speaks its usual reply. For Claude to compose the update from real robot state, the robot would need to publish that state; that would be its own feature.
- **Limiting the conversation history.** It grows for as long as the VM node runs, as in the spike.
- **Echo cancellation and barge-in** (F08).

## How to Demo
**Setup**: On the robot, `robot.launch.py` with `llm_wake_word` set in `voice.yaml`, plus dome_control and dome_mission. On the VM, the LLM node with `ANTHROPIC_API_KEY` set.

**Steps**:
1. Say "hey jarvis, go explore the room".
2. Say "hey jarvis, what do you see?".
3. Say "hey jarvis, tell me a joke".
4. `ros2 topic pub --once /voice/llm_text std_msgs/String "data: 'tell me a robot joke'"`.
5. Say "hey marvin explore".
6. Stop the VM node and say "hey jarvis, turn left".

**Expected output**:
1. `/intent` shows `exploration_start` with source `llm`, and the robot starts exploring.
2. `describe_scene` is published, and dome_control speaks a description.
3. The robot tells a joke, and no intent is published.
4. The robot tells a robot joke, with no speech in.
5. The fixed grammar still emits `exploration_start` with source `voice`.
6. The robot says the LLM path is offline.
