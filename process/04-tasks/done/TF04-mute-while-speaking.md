# TF04 Don't listen while the robot is speaking (Feature F04)

**Date Created:** 2026-11-19

Ordered so you can **try it on the robot after TF04.2**.

## TF04.0 — Mute support in the core
**Status**: done (2026-11-20): `drain_mic` and `wake_result` extracted; 5 tests
**Description**: `wait_for_wake` takes `is_muted_fn`. While true, chunks are read and discarded. When it turns false, run the existing cooldown drain. `next_turn` passes it through.
**Test**: a fake wake model that would fire reports no wake while muted; after unmute plus cooldown, it fires.

## TF04.1 — `speech_output` publishes `/voice/speaking`
**Status**: done (2026-11-20): 3 tests
**Description**: True before synthesis, false in a `finally` after playback.
**Test**: with synthesis and playback mocked, the sequence is true, false, also on a playback error.

## TF04.2 — `voice_input` subscribes
**Status**: done (2026-11-20): `voice_input` and the spike's `robot_mic_pub.py`; 1 test, threading checked by hand in TF04.3
**Description**: Subscribe to `/voice/speaking`, keep the latest value, pass it as `is_muted_fn`. The main loop blocks, so the subscription needs an executor on a background thread; follow how dome_control handles this. **Do the same in the F14 spike's `robot_mic_pub.py`**, which calls the same `wait_for_wake`: until TF14.2 retires it, it is the LLM path's listener, and it crashed on 2026-11-20 when a wake during speech made its beep clash with `speech_output` over the speaker.
**Test**: the callback stores the value. *Threading is runtime-only.*

## TF04.3 — You try it
**Status**: done (2026-11-20, on the LLM path via `robot_mic_pub.py`): saying the wake word over a long reply gave no beep and no crash; an `/announcement` containing "hey jarvis" was spoken with no wake; `/voice/speaking` went true, then false.
**Description**: Publish an `/announcement` whose text contains "hey marvin stop". Expected: the robot says it, no wake in the log, nothing on `/intent`. Then say "hey marvin status" yourself; the spoken reply should not trigger anything. Record results here. *Manual: robot.*

## TF04.4 — Docs and full test run
**Status**: done (2026-11-20): literate docs for `runtime`, `voice_input_node` and `speech_output_node`; spec's Listening section. 125 passed; the failures are I01's 3 and an uncommitted `voice.yaml` gain change, neither from F04.
**Description**: Literate docs for both nodes; spec's Listening section. Run `python3 -m pytest test/`.
