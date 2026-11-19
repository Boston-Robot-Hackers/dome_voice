# dome_voice — Spec

## Purpose

Standalone Python package providing a complete voice pipeline for robot control. No ROS imports. Designed to be consumed by a ROS2 adapter node (e.g. `dome_voice/voice_input_node.py`).

## Pipeline

```
mic (arecord) → stereo→mono → bandpass filter
    → wake word detection (openWakeWord)
    → STT (Vosk, grammar-constrained)
    → intent mapping (transcript → intent dict)
    → audio feedback (beep via aplay)
```

## Public API

```python
from dome_voice import (
    VoiceRuntime,        # main loop: next_turn() → VoiceTurn
    VoiceTurn,           # dataclass: text, raw_text, wake_score, empty, metadata
    VoiceRuntimeConfig,  # frozen dataclass of all tuned parameters
    load_voice_runtime_config,  # loads from TUNED_VOICE_PARAMETERS or YAML file
    IntentMapper,        # maps transcript text → intent dict
    beep,                # short audio tone via aplay
)
```

## Configuration

Defaults live once, in `dome_voice/runtime.py`'s `VoiceConfigFile` (a strict pydantic model). The robot's tuned values live in `config/voice.yaml`, which overrides only the keys it names (F02). It reaches the code through:
- `voice_input`'s `config` parameter, which `robot.launch.py` sets to the installed file (no environment variable; dome2 F07)
- `load_voice_runtime_config(path=...)`, or `python3 -m dome_voice.runtime --config <path>`

## Dependencies

- `openwakeword` — wake word detection
- `vosk` — offline STT
- `numpy` — audio math
- `arecord` / `aplay` — ALSA audio I/O (system)

## Constraints

- Zero ROS imports anywhere in this package
- No assumptions about robot hardware beyond ALSA audio device index
- Grammar vocabulary must include every phrase in `intent_mapper.py`
