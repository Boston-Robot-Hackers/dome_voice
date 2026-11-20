# TF04 Don't listen while the robot is speaking (Feature F04)

Ordered so you can **try it on the robot after T03**.

## T01 — Mute support in the core
**Status**: not done
**Description**: `wait_for_wake` takes `is_muted_fn`. While true, chunks are read and discarded. When it turns false, run the existing cooldown drain. `next_turn` passes it through.
**Test**: a fake wake model that would fire reports no wake while muted; after unmute plus cooldown, it fires.

## T02 — `speech_output` publishes `/voice/speaking`
**Status**: not done
**Description**: True before synthesis, false in a `finally` after playback.
**Test**: with synthesis and playback mocked, the sequence is true, false, also on a playback error.

## T03 — `voice_input` subscribes
**Status**: not done
**Description**: Subscribe to `/voice/speaking`, keep the latest value, pass it as `is_muted_fn`. The main loop blocks, so the subscription needs an executor on a background thread; follow how dome_control handles this.
**Test**: the callback stores the value. *Threading is runtime-only.*

## T04 — You try it
**Status**: not done
**Description**: Publish an `/announcement` whose text contains "hey marvin stop". Expected: the robot says it, no wake in the log, nothing on `/intent`. Then say "hey marvin status" yourself; the spoken reply should not trigger anything. Record results here. *Manual: robot.*

## T05 — Docs and full test run
**Status**: not done
**Description**: Literate docs for both nodes; spec's Listening section. Run `python3 -m pytest test/`.
