# dome_voice — History

Completed work moved out of `current.md`, newest first.

## 2026-11-20 — LLM spike runs; speech streams; speech config in voice.yaml

- **F12 spike, T01–T03:** robot mic → `/voice/utterance` → VM (faster-whisper `base.en`, Claude) → `/voice/llm_reply` → robot relay → `/announcement`. Works end to end. The spike then switched from Opus to `claude-haiku-5-5` for latency.
- **Chore: `speech_output` streams Piper** (`--output_raw` into `aplay -t raw`, gain in numpy). First audio on a two-sentence reply: about 1.3 s, where the WAV path took about 2.2 s.
- **F13:** speech gain, length scale and device moved into `voice.yaml` under `speech:`. The launch's `ENV_FALLBACKS` and speech arguments are gone. The gain went from 0.25 to 0.5.

## 2026-11-19 — Voice works on the robot

### Plan and features

- **Spec rewritten** (`02-doc/spec.md` v2) after a review against newer techniques.
- **Features F03–F11 drafted**, each with a task file ordered so the user can try something on the robot after the first one to three tasks.
- **F10 widened to continuous listening:** the wake word is detected in the live stream, commands work in one breath, and there is no dead time between turns.
- **F11 added:** compare STT backends (Vosk large, sherpa-onnx, Moonshine, Whisper) with F05's replay. The robot is a Pi 5 with 16 GB.

### F03 (one command table)

- **T01:** `explore` maps to `exploration_start`.
- **T03:** the Vosk grammar is derived from `PHRASE_INTENTS` via `command_words()`; `voice.yaml` no longer has a `grammar` key.
- **T02 passed in a basic sense:** "hey marvin … explore" published `exploration_start` on `/intent`.

### F05 (record and replay)

- **T01:** `record_dir` saves each turn, from 1 s before the wake, as WAV + JSON (`dome_voice/turn_recorder.py`).
- **T02 (in part):** 16 turns recorded over three sessions. Offline replay of `capture_command` matched live exactly, which made the fixes below measurable.

### I02 (voice runtime and mic)

- **Runtime installed:** openwakeword 0.4.0 (bundles `hey_marvin`), vosk plus the small model, and Piper plus lessac. `provision_dome` installs all of it.
- **Fixed, in order found:**
  - A tick every 80 ms: `read_mono_chunk` subtracted each chunk's own mean.
  - The codec's ADC highpass was off, so the input DC swung rail to rail. Now on for both channels.
  - A slow wander at the mic input saturates the ADC at high gain and mutes speech. PGA lowered to 60 (30 dB).
  - Speech too quiet for Vosk: `stt_gain_db: 20` on Vosk's input only.
  - The wake beep started the command turn: skipped before capture, and shortened to 0.1 s.
  - Dead time between turns: `wake_cooldown_secs` 1.5 → 0.8.
  - Playback was nearly silent: PCM 100, DACs 118.
- **Result:** the last session got 6 of 8 commands, the last 6 in a row.
- **Mixer state saved** with `sudo alsactl store` (20:08): PGA 60, ADC HPF 0.0045xFs on both channels, PCM 100, DACs 118.

### Chores

- `beep()` raises when aplay fails instead of ignoring it.
- `speech_output`'s announcement callback catches only the errors `speak_text` can raise.
- `ruff check` and `ruff format` pass; `ruff.toml` excludes `01-literate/`, whose snippets are excerpts.
