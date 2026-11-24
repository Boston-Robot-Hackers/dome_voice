# TF15 Speech starts sooner after an announcement, for Feature F15

**Date Created:** 2026-11-22

## TF15.0 — Measure where the 2 s goes, on the Pi

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

**Status**: done (2026-11-22). Results, from `~/tts_timing.py` on dome-R1
(`en_US-lessac-medium`, 22050 Hz, `plughw:0,0`, voice nodes stopped):

| Measurement | Result |
|---|---|
| `aplay` 0.3 s, cold (after 30 s idle) / warm | +0.09 s / +0.04 s |
| Piper "Hi." first audio / done / speech | 0.66 s / 0.70 s / 0.77 s (twice, same) |
| Piper status sentence first audio / done / speech | 1.55 s / 1.60 s / 4.47 s (twice, same) |
| Piper "Okay. " + status sentence first audio | 1.59 s |

- **Model load ≈ 0.6 s**, paid on every announcement.
- **Synthesis ≈ 0.9 s** for the status sentence, about 5× faster than speech.
- **A one-sentence text's audio arrives all at the end** (first byte 0.05 s
  before done). "Okay." in front didn't start sound sooner. *Corrected
  later:* history.md records the old streaming path getting a two-sentence
  reply's first audio out in about 1.3 s instead of 2.2 s, so Piper does
  stream per sentence on real multi-sentence text. The "Okay." test was
  too short to show it.
- **Card open and codec wake are negligible.** Candidate 3 is ruled out.
- 1.55 s + 4.47 s matches the 5.9 s `/voice/speaking` window seen earlier.

**Proposed for TF15.1** (presented to the user, 2026-11-22): a long-lived
Piper (`--json-input`, WAV per utterance in `/dev/shm`, saves ~0.6 s) and a
cache of recent texts (~0.1 s on repeats). Clause splitting (first sound
~0.5 s) deferred until the first two are heard.

## TF15.1 — The chosen fixes

**Status**: done in code (2026-11-22); not yet run on the robot

**Checked first, on the Pi:** `--json-input` keeps one process and prints
each WAV's path when written. Two requests 3 s apart: one start, the second
done ~1 s after it was sent, WAV sizes matching the speech lengths.

**Description**:
- **`dome_voice/piper_server.py`** (new, no ROS):
  - `PiperServer` runs one `piper --json-input` process; `synthesize(text)`
    sends one JSON line, waits for the printed path, then reads and deletes
    the WAV in `/dev/shm`, checking it's int16 mono at the model's rate.
  - `SpeechCache` keeps the audio of the 32 most recent sentences.
  - `split_sentences` splits at `.`/`!`/`?` plus whitespace, so "0.2"
    stays whole.
- **`speech_output_node.py`:**
  - Starts the server at startup and closes it in `destroy_node`.
  - `speak_text` speaks **a sentence at a time, pipelined**: sentence n+1
    is synthesised (or taken from the cache) while sentence n plays.
    This keeps the old path's early start on multi-sentence replies,
    which a whole-text WAV would have lost.
  - `Playback` writes each sentence to `/dev/shm` and runs `aplay` on the
    file in the background, so playing never blocks synthesis.
  - `stream_speech` and the raw-streaming Piper command are gone.
  - `/voice/speaking`, `speech.gain` and priorities are unchanged.

**Expected on the robot:** first sound about 1.0 s after the first press
of Status (0.9 s synthesis, no model load), about 0.1 s on repeats from the
cache; for multi-sentence replies, the first sentence's synthesis only.

**Test**: `test/test_piper_server.py` (14) and `test/test_speech_output_node.py`
(27), all passing on the Mac with ROS faked (2026-11-22). A Python stand-in
for Piper's JSON mode shows one process start across several requests, WAV
cleanup, errors with Piper's stderr, and a wrong-rate WAV rejected. The node
tests show the pipeline order (synthesise 2 before waiting on 1), cache
reuse per sentence, gain, a failed playback stopped and raised, and Piper
closed on shutdown.

## TF15.2 — Tests and demo

**Status**: not done

**Description**: Write any remaining tests, run the suite, then F15's demo
on the robot. Record press → first sound for five presses, before and
after.

**Test**: this task is the test run; the demo is manual (speaker).
