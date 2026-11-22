# TF15 Speech starts sooner after an announcement, for Feature F15

**Date Created:** 2026-11-22

## TF15.0 — Measure where the 2 s goes, on the Pi

**Status**: not done

**Description**: Time each part separately on the robot, with the voice
nodes stopped so nothing else holds the card:
- **Piper load + first sentence:** `time (echo "linear speed 0.2, angular
  speed 0.7" | piper --model "$DOME_PIPER_MODEL_PATH" --output_raw --quiet
  > /dev/null)`, and the same with a two-sentence text, to see whether
  audio waits for the whole first sentence.
- **Piper load alone:** the same with a one-word text.
- **Card open and codec wake:** `time aplay -q -D "$SPEECH_ALSA_DEVICE" -f
  S16_LE -r 22050 -c 1 -d 1 /dev/zero` from idle, then again right after
  (warm).
- **In the node:** temporary timing logs in `stream_speech` (Piper start →
  first PCM chunk → first `aplay` write → end).

Record the numbers here, then choose which fixes in F15's scope to do.
**Stop and present the choice before TF15.1.**

**Test**: this task is the measurement. Manual, on the robot.

## TF15.1 — The chosen fixes

**Status**: not done

**Description**: Filled in after TF15.0, from F15's options: a long-lived
Piper process (`--json-input`), a long-lived audio output, shorter first
sentences. Each keeps `/voice/speaking`, `speech.gain` and priorities as
they are now, and shuts down cleanly with the node.

**Test**: unit tests in `test/test_speech_output_node.py`, with small shell
commands standing in for Piper and `aplay` (as the existing `stream_speech`
tests already do): one model load across several
announcements; `/voice/speaking` true and false around each; clean
shutdown stops the long-lived processes.

## TF15.2 — Tests and demo

**Status**: not done

**Description**: Write any remaining tests, run the suite, then F15's demo
on the robot. Record press → first sound for five presses, before and
after.

**Test**: this task is the test run; the demo is manual (speaker).
