# F05 — Record turns and replay them offline

**Date Created:** 2026-11-19
**Priority**: High
**Done:** no
**Tasks File Created:** yes
**Tests Written:** no
**Test Passing:** no

## Description

Today every threshold in `voice.yaml` was set by trying it on the robot. **There's no way to tell whether a change made things better.** F06 (VAD), F07 (stop word) and F08 (mic array) all need a before/after number.

### Scope

- **Recording**: an optional `record_dir` setting. When set, each turn's audio (from about 1 s before wake detection to end of command, so the wake word's effect on the command can be heard; F10 reuses this) is saved as a 16 kHz mono WAV, with a JSON sidecar holding what the pipeline heard (wake score, raw text, intent).
- **Labelling**: the sidecar has an `expected` field the user fills in by hand (the intended command, or `none` for a false wake).
- **Replay**: `python3 -m dome_voice.replay <dir> [--config voice.yaml]` feeds each WAV through `VoiceRuntime` (its stream is already injectable) and prints wake rate, false-wake count, command accuracy, and median latency.
- **Background recordings**: the replay tool also accepts long WAVs with no commands (motor noise, room noise) and reports false wakes per hour.

### Out of scope

- A shipped recording corpus. Recordings are personal audio; they stay out of git (`.gitignore`).
- Automatic re-tuning.

## How to Demo
**Setup**: `record_dir` set in `voice.yaml`, a few labelled turns recorded.

**Steps**:
1. `python3 -m dome_voice.replay ~/voice_recordings`
2. Change `threshold` with `--config` and run again.

**Expected output**: a summary table per run; the two runs give different numbers.
