# TF10 Continuous listening (Feature F10)

Ordered so you can **say "hey marvin explore" on the robot after T02**.

## T01 — Rolling pre-roll buffer
**Status**: not done
**Description**: Add `preroll_secs` to `StreamSettings`. The runtime keeps the last `preroll_secs` of chunks in a `deque(maxlen=...)`, whatever mode it is in.
**Test**: with a fake stream and a fake wake model that fires on chunk N, the buffer holds exactly the expected last chunks, in order.

## T02 — Feed the buffer to Vosk and strip the wake phrase
**Status**: not done
**Description**: On wake, `capture_command` feeds the buffer to the recogniser before live chunks. The wake phrase's words are added to the grammar and removed from the transcript. Endpointing counts only chunks after the wake.
**Test**: with a fake recogniser, the buffer reaches `AcceptWaveform` first; "hey marvin explore" maps to `exploration_start`; buffered audio does not set `command_started`.

## T03 — You try it: one breath
**Status**: not done
**Description**: Rebuild, run `bl dome_voice robot.launch.py`, and say "hey marvin explore" in one breath and with a pause, five times each. Note how many reach `/intent`. *Manual: robot.*

## T04 — Wake detection during a turn
**Status**: not done
**Description**: Every chunk read during a command also goes to the wake model. A wake during a turn drops the current capture and starts a new one from the buffer.
**Test**: a fake wake model that fires twice: the turn's transcript comes only from audio after the second wake.

## T05 — Remove the cooldown
**Status**: not done
**Description**: Drop `wake_cooldown_secs` once F04's muting is in. Reject the old key with a message saying where it went, as `grammar` is rejected.
**Test**: a turn followed immediately by a wake chunk is detected; the old key raises with that message.
**You try it**: say "hey marvin left" right after a turn ends.

## T06 — Tune the pre-roll length with F05
**Status**: not done
**Description**: Record one-breath and pause turns, replay with a few `preroll_secs` values, and keep the best in `voice.yaml`. Record the numbers in `process/02-doc/notes.md`. *Manual: real audio.*

## T07 — Tests, docs, full test run
**Status**: not done
**Description**: Fill test gaps (empty buffer, buffer shorter than `preroll_secs`, wake phrase absent from the transcript). Update `voice.yaml`'s comments, the literate doc for `runtime.py`, and the spec's *(planned)* markers. Run `python3 -m pytest test/`.
