# dome_voice — Spec

**Version 3** (2026-11-20). Allows offboard processing case by case, and plans an LLM command path next to the fixed grammar. Version 2 (2026-11-19) followed a review of the package against newer voice techniques and the robot's hardware. Requirements marked *(planned, Fnn)* are not built yet.

## Purpose

dome_voice gives the robot a spoken interface: it hears commands and turns them into `/intent` messages, and it speaks `/announcement` messages aloud.

**Where it runs:** on the robot (Raspberry Pi 5, 16 GB) by default. **Parts may run offboard** (the VM, or a cloud API), decided case by case in each feature.

**The stop path always runs on the robot**, offline, with no STT and no LLM in it.

## Structure

The package has two layers:

- **A ROS-free core library** (`runtime.py`, `intent_mapper.py`, `audio_feedback.py`, and future audio modules). No ROS imports; testable with plain pytest and recorded audio.
- **Two ROS nodes** that wrap the core: `voice_input` (mic → `/intent`) and `speech_output` (`/announcement` → speaker). They hold no voice logic of their own.

## Pipeline

```
mic (arecord) → mono
    → wake word (openWakeWord)            ─┐
    → always-on safety word (planned, F07) ─┴→ stop path, no STT
    → speech detection (planned, F06: Silero VAD)
    → STT (Vosk, grammar-constrained; backend chosen by measurement, F11)
    → intent mapping (transcript → intent)
    → /intent  + audio feedback (beep)

/announcement → Piper TTS → speaker
```

## Requirements

### Commands and intents

- **One command table** in `intent_mapper.py` is the only place commands are written. The Vosk grammar and the spoken help text are derived from it. *(planned, F03)*
- **Intent names follow the `/intent` contract** of the packages that act on them: dome_mission for exploration and navigation, dome_control for motion and perception queries. Every intent dome_voice emits has a consumer. *(planned, F03)*
- **Matching is by whole word**, not substring. *(planned, F03)*
- **Place and object names** come from the robot's map and dome_semantic at runtime and are added to the grammar, so "go to kitchen" becomes `navigation_go` with `slots.label`. *(planned, F09)*

### Safety

- **Stopping must not depend on the wake word.** A dedicated always-on phrase stops the robot with no STT and no LLM in the path. *(planned, F07)*

### Listening

- **The robot does not hear itself.** Wake detection is suspended while the robot speaks or beeps, and the mic is drained afterwards. *(planned, F04)*
- **The wake word is detected continuously in the live stream**, including during a command, with no dead time between turns. A second wake during a turn restarts it. *(planned, F10)*
- **A command can follow the wake word in one breath.** "hey marvin explore" works as well as "hey marvin … explore" with a pause. The audio from just before wake detection is kept and given to STT, so the start of the command is not lost to the wake detector. *(planned, F10)*
- **A command ends when the speaker stops talking**, detected by a voice-activity model, not by loudness thresholds. *(planned, F06)*
- **If the mic stream ends, `voice_input` fails loudly** (logs and exits non-zero), never silently.

### Measurement

- **The STT backend is chosen by measurement.** Candidates (Vosk large, sherpa-onnx, Moonshine, Whisper) are compared on recorded turns; the robot uses the winner. *(planned, F11)*
- **Tuning is measured, not guessed.** Turns can be recorded to WAV, and a replay tool runs recordings through the pipeline offline and reports wake rate, false wakes, and command accuracy. *(planned, F05)*

### Hardware

- **Today:** Seeed 2-mic HAT (`seeed2micvoicec`, card 0), capture and playback. No hardware echo cancellation.
- **Planned:** support a USB mic array with on-board DSP (ReSpeaker XVF3800) by config alone: card, channel count, and channel to use. *(planned, F08)*

## Public API (core library)

```python
from dome_voice import (
    VoiceRuntime,  # main loop: next_turn() → VoiceTurn
    VoiceTurn,  # dataclass: text, raw_text, wake_score, empty, metadata
    VoiceRuntimeConfig,  # frozen dataclass of all resolved parameters
    load_voice_runtime_config,  # defaults + YAML + overrides
    IntentMapper,  # maps transcript text → intent dict
    beep,  # short audio tone via aplay
)
```

## Configuration

- **`voice_input`**: defaults live once in `runtime.py`'s `VoiceConfigFile` (strict pydantic). `config/voice.yaml` overrides only the keys it names (F02). `robot.launch.py` passes it as the `config` parameter. No environment variables.
- **`speech_output`**: the `speech:` section of the same `config/voice.yaml` (gain, length scale, playback device), passed as the same `config` parameter (F13). Only the Piper install paths, `DOME_PIPER_BIN` and `DOME_PIPER_MODEL_PATH`, come from the environment.

## Dependencies

- `openwakeword`, `vosk`, `numpy`, `pydantic`, `pyyaml`
- `arecord` / `aplay` (ALSA), `piper` (TTS)
- Planned: `silero-vad` (ONNX, F06)

## Constraints

- Core modules import no ROS.
- No assumptions about hardware beyond the ALSA card numbers and channel layout in config.
- Every phrase in the command table is in the grammar (guaranteed by deriving it, F03).

## Direction, not yet features

- **An LLM path runs next to the fixed grammar, not instead of it.** An open STT (Whisper) plus an LLM turns speech into `/intent` messages or a spoken reply, and may run offboard. **The fixed-grammar path stays**, because other uses may need it. F12, a spike, decides whether to go ahead; a feature will follow if it does.
- **Each path has its own wake word:** "hey marvin" for the fixed grammar, and "hey robbie" planned for the LLM.
- **With no network, the LLM path says it is offline.** The fixed-grammar path and the stop phrase (F07) keep working, because neither depends on the network.
- **Barge-in** (interrupting the robot mid-sentence) needs echo cancellation, which needs the mic array (F08).
