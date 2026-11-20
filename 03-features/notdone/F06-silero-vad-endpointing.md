# F06 — End commands with a voice-activity model

**Date Created:** 2026-11-19
**Priority**: Medium
**Done:** no
**Tasks File Created:** yes
**Tests Written:** no
**Test Passing:** no

## Description

`capture_command` decides when you've stopped talking by **loudness**: a learned noise floor, a margin, a clamp at −22 dB, a "2 loud chunks" rule, and Vosk's own endpointing on top. Motor noise is loud, so it reads as speech. This is the most fragile part of the code and accounts for six config keys.

**Replace it with Silero VAD** (ONNX, under 1 ms per chunk on the Pi), which is trained to tell speech from noise.

### Scope

- Speech start and end come from Silero's speech probability per chunk, with one threshold and the existing `silence_secs`, `command_start_secs` and `max_command_secs`.
- **Remove** `noise_floor`, `silence_cutoff`, `FLOOR_MAX_DBFS`, and the `silence_dbfs` / `silence_margin` keys. *Persisted-format change:* old keys raise with a message naming the replacement.
- Turn on openWakeWord's own Silero gate (`vad_threshold`) so wakes with no speech in them are rejected.
- **Measure with F05's replay** before and after. Also measure with `live_filter` off: if the bandpass doesn't help, remove `LiveBandpass` (it costs a Python loop over every sample).

### Out of scope

- Changing the STT engine.

## How to Demo
**Setup**: F05 baseline recordings.

**Steps**:
1. `python3 -m dome_voice.replay ~/voice_recordings` on main and on this branch.

**Expected output**: command accuracy the same or better, fewer empty turns while driving, and median latency no worse.
