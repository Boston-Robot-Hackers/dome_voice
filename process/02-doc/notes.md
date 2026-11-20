# dome_voice — Notes

## Extraction from dome_control/

Extracted from `dome_control/voice/` 2026-05-07. Dead files `stt.py` and `wake_word.py` were dropped
(legacy pyaudio-based classes, broken imports, unused by the production pipeline).

## arecord vs pyaudio

Pipeline uses `arecord` subprocess (stereo S16_LE) rather than pyaudio. Avoids ALSA/pyaudio
device index conflicts on Raspberry Pi. Stereo→mono average in `read_mono_chunk`.

## Grammar constraint

**The Vosk grammar is derived from `PHRASE_INTENTS`** in `intent_mapper.py` (F03, 2026-11-19),
plus `[unk]`. Adding a voice command is one new row in that table. `voice.yaml` no longer has a
`grammar` key; a YAML that still names it raises.

## Tuned parameters

**Tune results go into `config/voice.yaml`, not into code** (F02, 2026-11-19). The file's
shape mirrors tune's `active.yaml`, so values can be copied mechanically.

The defaults live once, in `runtime.py`'s `VoiceConfigFile` (a strict pydantic model). A YAML
overrides only the keys it names, and an unknown key raises. This is the pattern dome_vision,
dome_semantic and dome_control's `spin_survey` use.

The old in-code table had `threshold` 0.7 and `wake_hits` 3, tuned for `alexa`. The robot never
ran with them, because its YAML replaced the table. They are the starting point for re-tuning
`hey_marvin`.

## What is built

- **Core library (no ROS):** `runtime.py` (config, mic, wake detection with muting, Vosk capture), `utterance_capture.py` (the LLM path's capture), `llm_turn.py` (Claude with intent tools), `intent_mapper.py` (the command table), `turn_recorder.py`, `audio_feedback.py`.
- **ROS nodes:** `voice_input` (either path, by `command_path`), `speech_output` (Piper, `/voice/speaking`), and `llm_node` on the VM.
- **Launches:** `launch/robot.launch.py` (robot) and `launch/remote.launch.py` (VM), included by dome2's `robot.launch.py` and `remote.launch.py` as `voice`.

## Recording turns

Set `record_dir: ~/voice_recordings` in `voice.yaml` for a session, then set it back to `none` before committing; `test_robot_yaml_does_not_record_turns` checks it. Recording works on the grammar path only.

## Mixer state (I02)

Saved with `alsactl store` on 2026-11-19 20:08: PGA 60, ADC HPF 0.0045xFs on both channels, PCM 100, DACs 118.

## Diagnostics

- **Mic levels:** `cd ~/voice_diag && python3 mic_diag.py ~/ros2_ws/src/dome_voice/config/voice.yaml`. Stop the voice launch first, because the mic opens only once.
- **Smoke test (grammar path, hardware):** `python3 -m dome_voice.runtime --trials 5`.
