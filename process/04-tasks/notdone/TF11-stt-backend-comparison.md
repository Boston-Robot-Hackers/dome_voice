# TF11 Compare speech-to-text backends (Feature F11)

Ordered so you can **see Vosk small vs Vosk large on your own recordings after T02**.

## T01 — STT interface with a Vosk adapter
**Status**: not done
**Description**: Define the recogniser interface `capture_command` uses (feed audio, get partial/final text, endpoint). Wrap today's Vosk code as the first adapter. No behaviour change.
**Test**: the existing `capture_command` tests pass through the adapter; a fake adapter receives the same audio Vosk would.

## T02 — Replay `--stt`, with Vosk large
**Status**: not done
**Description**: Add `--stt` to the replay tool; `vosk-small` and `vosk-large` are model paths for the same adapter. Install the large model.
**Test**: with fake adapters, `--stt` picks the right one and the summary has one row per backend.
**You try it**: run both on your recordings and compare.

## T03 — sherpa-onnx adapter
**Status**: not done
**Description**: Adapter for a streaming zipformer model, with the command words as biasing hotwords.
**Test**: with a fake sherpa module, audio and hotwords reach it and its text comes back. A real-model check is *manual*.

## T04 — Moonshine adapter
**Status**: not done
**Description**: Adapter that buffers the turn and transcribes it at the end of the turn.
**Test**: with a fake Moonshine module, the full turn's audio is passed once and its text is returned.

## T05 — Whisper adapter
**Status**: not done
**Description**: whisper.cpp base.en adapter, with silence rejection so empty turns don't become hallucinated text.
**Test**: with a fake module, a silent turn returns empty text.

## T06 — Measure and choose
**Status**: not done
**Description**: Run all backends on the labelled recordings. Record accuracy, empty-turn rate, and latency in `process/02-doc/notes.md`. Switch the robot's config to the winner if it clearly beats Vosk small, and add its install to `provision_dome`. *Manual: real audio.*

## T07 — Tests, docs, full test run
**Status**: not done
**Description**: Fill test gaps, add literate docs for the new modules, update the spec's Dependencies section. Run `python3 -m pytest test/`.
