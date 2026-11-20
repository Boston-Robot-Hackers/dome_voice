# TF08 Support a USB mic array (Feature F08)

Ordered so you can **hear the new board before any code**, then switch to it with config alone after T03.

## T01 — You try the board raw
**Status**: not done
**Description**: Plug in the XVF3800. Record `arecord -l`, channel count, sample rates, and which channel is the processed signal in `02-doc/notes.md`. Record 30 s while driving with `arecord`, the same with the Seeed HAT, and listen to both. *Manual: hardware.*

## T02 — Configurable capture layout
**Status**: not done
**Description**: Add `capture_channels` and `capture_channel` (none = average all). `open_arecord` and `read_mono_chunk` use them.
**Test**: fake 1-, 2- and 6-channel streams give the right mono samples.

## T03 — Playback card from config
**Status**: not done
**Description**: `beep` uses `playback_card`, not `SPEECH_ALSA_DEVICE`. Remove the unused `device_index` argument and `VOICE_DEVICE_INDEX`. Point `speech_output` at the array's output.
**Test**: `beep` runs `aplay -D plughw:<playback_card>,0` (mocked).

## T04 — You try it
**Status**: not done
**Description**: Switch `voice.yaml` to the array. Drive and give commands; say a command while the robot is speaking. If F05 exists, replay both boards' recordings and compare. Record results here. *Manual: robot.*

## T05 — Docs and full test run
**Status**: not done
**Description**: Spec's Hardware section, `voice.yaml` comments, literate docs. Run `python3 -m pytest test/`.
