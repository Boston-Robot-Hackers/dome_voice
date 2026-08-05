# dome_voice — Current Session Handoff

## Snapshot

**Branch:** `main` (lives inside `ros2_ws/src/dome_voice/`, sibling to `dome_control/`)

This package was extracted from `dome_control/voice/` to be a standalone, ROS-free voice pipeline.
`dome_control/` consumes it via `voice_input_node.py` (the only ROS adapter).

## What Is Built

- `runtime.py` — `VoiceRuntime`, `VoiceRuntimeConfig`, `load_voice_runtime_config`, full pipeline
- `intent_mapper.py` — `IntentMapper`: transcript → intent dict (8 commands: stop, right, left, explore, describe, objects, status, help)
- `audio_feedback.py` — `beep()` via aplay
- `speech_output_node.py` — ROS2 node: subscribes `/announcement`, speaks via Piper TTS + ALSA
- `__init__.py` — public API surface
- `test/` — 37/42 passing; see Known Issues
- `01-literate/` — literate docs: 00-overview, 01-runtime, 02-intent_mapper, 03-voice_input_node, 04-speech_output_node, X01-audio_feedback

## Recent Changes (2026-05-14)

- `speech_output_node.py`: env vars renamed `PIPER_BIN` → `DOME_PIPER_BIN`, `PIPER_MODEL_PATH` → `DOME_PIPER_MODEL_PATH`
- `launch/robot.launch.py`: same env var renames
- `01-literate/04-speech_output_node.md`: updated env var table
- `testvoice.py`: added `test_beep()` function for hardware smoke testing

## Known Issues

**5 of 42 tests failing (found 2026-08-05, not caused by any change this
session — pre-existing, previously undetected)**: see
`05-issues/open/I01-test-suite-regressions.md`.
- `voice_input_node`'s beep path reads `self.voice_config`, unset on the
  node under test (3 failures).
- `voice_runtime`'s fake-model test gets `"alexa stop"` instead of `"stop"`
  — wake word not stripped before the intent-mapper step.
- `voice_runtime_config`'s `CONTROL_VOICE_TUNE_CONFIG` env var override
  isn't taking effect in `load_voice_runtime_config`.

## Quick Commands

```bash
# Build
colcon build --packages-select dome_voice

# Test
python3 -m pytest test/

# Smoke test (hardware)
python3 -m dome_voice.runtime --trials 5
```
