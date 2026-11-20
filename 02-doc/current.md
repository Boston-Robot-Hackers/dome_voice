# dome_voice — Current Session Handoff

## Snapshot

**Branch:** `main` (lives inside `ros2_ws/src/dome_voice/`, sibling to `dome_control/`)

This package was extracted from `dome_control/voice/` to be a standalone, ROS-free voice pipeline.
`dome_control/` consumes it via `voice_input_node.py` (the only ROS adapter).

**Completed work** is in `02-doc/history.md`.

## Open

### Plan

- **Features F03–F11** are drafted in `03-features/notdone/`, each with a task file in `04-tasks/notdone/`.
- **Suggested order:** F03 → F05 → F04 → F07 → F11 → F10 → F06 → F09 → F08.
- **Chores** are in `04-tasks/chores.md`.

### In progress: F12 (LLM loop spike)

- **The code is in `spikes/llm_loop/`**, and `README.md` there has the setup and run steps.
- **T01–T03 work end to end** (2026-11-20): robot mic → VM (faster-whisper, Claude) → robot speech. The VM is at `/home/pitosalas/ros2_ws/src/dome_voice` too.
- **Measured:** Whisper 0.3 s, Opus 1.4–1.8 s, Piper about 3 s before the first word. Since then the spike uses `claude-haiku-5-5`, and `speech_output` streams Piper (first word at about 1.3 s). Not yet re-measured end to end.
- **VM gotchas, now in the spike README:** Ubuntu's apt `brotli` 1.1 breaks the SDK ("Connection error"), so install `brotli>=1.2`; and the API account needs credit, separate from a Claude.ai plan.
- **Next, T04:** about 10 live exchanges, with findings and a go/no-go written into F12.

### Done: F13 (speech settings in voice.yaml)

- **`speech_output` reads `speech:` from `voice.yaml`**: gain (now 0.5), length scale, device. It takes the YAML as its `config` parameter, like `voice_input`. Only the Piper paths stay in the environment.
- **The launch has no arguments now**, and `SPEECH_GAIN`, `PIPER_LENGTH_SCALE` and `SPEECH_ALSA_DEVICE` are no longer read.
- **Outside this repo:** dome2's `TF05-launch-file-cleanup.md` still describes the old speech environment variables.

### Paused: F05 (record and replay)

- **Voice works on the robot** as of 2026-11-19: the last session got 6 of 8, the last 6 in a row.
- **T02 is mostly done:** 16 turns are recorded in `~/voice_recordings`. Left: once with motors running.
- **Next code task: T04, the replay tool.** It turns the ad hoc replay scripts used on 2026-11-19 into `python3 -m dome_voice.replay`.
- **Replay limit:** a recording ends where the live turn ended, so settings that listen longer can't be judged. T04 should record about 2 s past the turn's end.
- **To record again**, set `record_dir: ~/voice_recordings` in `voice.yaml`, then set it back to `none` before committing; the baseline test checks it.

### Paused: F03 (one command table)

- **Next:** T04, whole-word matching.
- **Decision pending:** what "stop" emits (F03's "Decision needed", task T05).

### I02 (voice runtime and mic): open

- **Mixer state is saved** (`alsactl store`, 2026-11-19 20:08): PGA 60, ADC HPF 0.0045xFs on both channels, PCM 100, DACs 118. **Left:** add it to `provision_dome` (a chore), so a fresh install gets it.
- **The wander's source is unknown.** Unplug the lidar or power off the motor board, and measure the muted fraction at PGA 80.
- **Untested with motors running.** All tests so far were with the robot standing still.
- **Close I02** once the mixer is provisioned, and the wander source is found or ruled out.
- **Diagnostic:** `cd ~/voice_diag && python3 mic_diag.py ~/ros2_ws/src/dome_voice/config/voice.yaml`. Stop `robot.launch.py` first, because the mic can only be opened once.

### Hardware decision, parked

- **The XVF3800 USB array would replace the HAT**, both mic and speaker output, for echo cancellation. F08 covers it.
- **Before buying:** find the wander's source, and try any USB mic with `mic_diag`.
- **Speaker:** the array's 3.5 mm output needs a powered speaker or a small amplifier.

### Outside this repo

- **provision_dome:** `manifest/pip.txt`, `manifest/bashrc`, `scripts/install-optional-deps.sh` are changed and not committed.
- **`~/.bashrc`:** `DOME_PIPER_*` paths changed.

## What Is Built

- `runtime.py` — `VoiceRuntime`, `VoiceRuntimeConfig`, `load_voice_runtime_config`, the full pipeline, `stt_gain_db`, the wake-beep skip.
- `turn_recorder.py` — `TurnRecorder`: each turn to WAV + JSON when `record_dir` is set.
- `intent_mapper.py` — `IntentMapper` and `command_words()`: 8 commands (stop, right, left, explore → `exploration_start`, describe, objects, status, help). The grammar is derived from this table.
- `audio_feedback.py` — `beep()` via aplay; raises when aplay fails.
- `voice_input_node.py`, `speech_output_node.py` — the ROS nodes.
- `test/` — 99 passed, 3 failed (I01's `voice_input_node` tests). `spikes/llm_loop/` has 12 more.
- `01-literate/` — literate docs.

## Known Issues

**I02 (open):** see above.

**I01: 3 test failures remain** (originally 5 of 42; found 2026-08-05): see
`05-issues/open/I01-test-suite-regressions.md`.
- `voice_input_node`'s beep path reads `self.voice_config`, unset on the
  node under test (3 failures).

## Quick Commands

```bash
# Build
colcon build --packages-select dome_voice

# Test
python3 -m pytest test/

# Lint
ruff check . && ruff format --check .

# Smoke test (hardware)
python3 -m dome_voice.runtime --trials 5
```
