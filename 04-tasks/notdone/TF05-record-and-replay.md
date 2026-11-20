# TF05 Record turns and replay them offline (Feature F05)

Ordered so you can **listen to what the robot hears after T01**, before any replay tool exists.

## T01 — Slice: record each turn to WAV
**Status**: done (`dome_voice/turn_recorder.py`; tests in `test/test_turn_recorder.py`)
**Description**: Add optional `record_dir` to `StreamSettings`. When set, `VoiceRuntime` keeps the current turn's chunks, starting about 1 s before wake detection, and writes `<timestamp>.wav` plus `<timestamp>.json` (wake score, raw text, intent). No work when unset.
**Test**: with a fake stream and `tmp_path`, one turn writes one WAV of the right length and a sidecar; unset writes nothing.

## T02 — You try it
**Status**: not done
**Description**: Set `record_dir: ~/voice_recordings`, run `python3 -m dome_voice.runtime --config config/voice.yaml --trials 10`, once standing still and once with motors running. Play the WAVs back (`aplay`) and look at the sidecars. Note what the noise sounds like. *Manual: robot.*

## T03 — Background recording mode
**Status**: not done
**Description**: `python3 -m dome_voice.runtime --record-background <secs>` saves raw mic audio for that long, for false-wake measurement.
**Test**: with a fake stream, the WAV has the requested length.
**You try it**: record 10 minutes of driving noise.

## T04 — Replay tool
**Status**: not done
**Description**: `dome_voice/replay.py`: a WAV-to-stream adapter, models loaded once, each WAV run through `VoiceRuntime`, compared to the sidecar's hand-filled `expected` field. Prints wake rate, false wakes (and per hour for background WAVs), command accuracy, median latency.
**Also**: recordings end when the live turn ended, so a setting that listens longer can't be judged. Record about 2 s past the turn's end, and replay must stop at the original end only when comparing to live.
**Test**: the adapter round-trips a sine WAV; with fake models and two fixture sidecars, the summary counts are correct.
**You try it**: label T02's recordings, run `python3 -m dome_voice.replay ~/voice_recordings`, then again with a different `threshold`.

## T05 — Baseline
**Status**: not done
**Description**: About 50 labelled turns and 30 minutes of driving noise with today's config. Record the numbers in `02-doc/notes.md`. *Manual: real audio.*

## T06 — Git-ignore, docs, full test run
**Status**: not done
**Description**: Ignore recording directories. Literate doc for `replay.py`; "how to tune" in notes. Run `python3 -m pytest test/`.
