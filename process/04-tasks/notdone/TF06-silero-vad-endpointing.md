# TF06 End commands with a voice-activity model (Feature F06)

**Date Created:** 2026-11-19

Ordered so you can **A/B old and new endpointing live on the robot after TF06.1**. The switch is temporary: TF06.4 removes the loser.

## TF06.0 — Slice: VAD endpointing behind a switch
**Status**: not done
**Description**: A `SpeechDetector` wrapper around Silero VAD (reuse openWakeWord's bundled model if possible), loaded once. Add `endpointing: rms | vad` and `vad_threshold` to config; `capture_command` uses VAD probabilities when `vad`. Time one chunk on the Pi and record it.
**Test**: with a scripted fake detector, a command ends after `silence_secs` of non-speech, gives up after `command_start_secs`, stops at `max_command_secs`.

## TF06.1 — You try it
**Status**: not done
**Description**: `python3 -m dome_voice.runtime --config config/voice.yaml --trials 10` with `endpointing: rms`, then `vad`, standing still and with motors running. Compare empty turns and how quickly it responds after you stop talking. Record results here. *Manual: robot.*

## TF06.2 — openWakeWord VAD gate
**Status**: not done
**Description**: Pass `vad_threshold` to the openWakeWord model so wakes with no speech are rejected.
**Test**: the model is constructed with it (mocked).
**You try it**: drive with nobody talking; count false wakes against before.

## TF06.3 — Measure with replay (if F05 exists)
**Status**: not done
**Description**: Replay the F05 baseline with each endpointing mode, and with `live_filter` on and off. Record results in notes. *Manual: real audio.*

## TF06.4 — Remove the loser
**Status**: not done
**Description**: Assuming VAD wins: delete the RMS path (`noise_floor`, `silence_cutoff`, `FLOOR_MAX_DBFS`, `silence_dbfs`, `silence_margin`) and the `endpointing` switch. If the filter didn't help, delete `LiveBandpass`, `sox_chain`, `live_filter` too. Removed YAML keys raise with the replacement named.
**Test**: old keys raise with that message.

## TF06.5 — Docs and full test run
**Status**: not done
**Description**: Runtime literate doc; spec. Run `python3 -m pytest test/`.
