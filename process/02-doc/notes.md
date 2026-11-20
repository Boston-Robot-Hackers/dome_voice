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
