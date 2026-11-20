# F11 — Compare speech-to-text backends on recorded turns

**Date Created:** 2026-11-19
**Priority**: Medium
**Done:** no
**Tasks File Created:** yes
**Tests Written:** no
**Test Passing:** no

## Description

**Vosk's small model is the weakest link we can change in software.** On 2026-11-19 it needed 20 dB of extra gain, and still missed quiet speech (I02). The robot is a **Raspberry Pi 5 with 16 GB**, so larger models fit.

**Choose by measurement, not reputation.** Run F05's recordings through each candidate and compare command accuracy and latency on this robot's own audio.

### Candidates

- **Vosk large** (`vosk-model-en-us-0.22`): a drop-in replacement, same grammar.
- **sherpa-onnx** (a streaming zipformer model): streaming, with contextual biasing toward the command words.
- **Moonshine**: built for edge devices; no grammar, so its text goes straight to the intent mapper.
- **Whisper** (whisper.cpp, base.en): robust to noise; slower, and can hallucinate on silence.

### Approach

- **A small STT interface.** `capture_command` talks to "a recogniser" through feed-audio / get-text calls, so each backend is an adapter. Vosk stays the default.
- **The replay tool takes a backend option** (`--stt vosk-small`, `--stt moonshine`, ...) and reports the same numbers for each.
- **Only the winner ships.** The others stay out of `package.xml` and `provision_dome` unless chosen.

### Scope

- The STT interface, adapters for the candidates, the replay option, and a results table in `process/02-doc/notes.md`.
- Switching the robot to the winner, if it clearly beats Vosk small.

### Out of scope

- Wake word models: openWakeWord works reliably today.
- LLM intent mapping (spec: Direction, not yet features).

### Depends on

- **F05**: the replay tool and a labelled set of recordings.

## How to Demo
**Setup**: F05's labelled recordings in `~/voice_recordings`; candidate models installed.

**Steps**:
1. `python3 -m dome_voice.replay ~/voice_recordings --stt vosk-small`
2. Repeat with each other `--stt` value.

**Expected output**: one row per backend with command accuracy, empty-turn rate, and median latency; the notes record which one the robot uses and why.
