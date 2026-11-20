# F07 — An always-on stop phrase

**Date Created:** 2026-11-19
**Priority**: High
**Done:** no
**Tasks File Created:** yes
**Tests Written:** no
**Test Passing:** no

## Description

To stop the robot today you say the wake word, wait for the beep, then say "stop": **1–2 seconds, and nothing happens if the wake word is missed.** Stopping is a safety function; it should be the fastest path, not the slowest.

### Scope

- **A second openWakeWord model** for a stop phrase, scored on every chunk alongside the wake word. openWakeWord shares its feature model between wake words, so the extra cost is small.
- **When it fires, publish the stop intent immediately.** No beep wait, no STT. It works whether or not the wake word was said, and also during command capture.
- **It stays active while the robot speaks** (F04), because that's when you most need it. This will cause some false stops from the robot's own voice; accepted, since a false stop is safe.
- **The phrase is 2–3 syllables.** A bare "stop" is too short for openWakeWord and will false-trigger. Candidates: "marvin stop", "robot stop".
- The model is trained off the robot (openWakeWord's training notebook on a GPU or Colab) and installed as an `.onnx` path in `voice.yaml`.

### Decision needed

**Which phrase?** Recommended: **"marvin stop"**, to match the wake word.

### Out of scope

- Hardware e-stop. This supplements it, never replaces it.

## How to Demo
**Setup**: robot exploring.

**Steps**:
1. Say "marvin stop" without the wake word.

**Expected output**: `stop` on `/intent` within about 300 ms of the end of the phrase; the robot stops. F05 replay reports false stops per hour of driving noise.
