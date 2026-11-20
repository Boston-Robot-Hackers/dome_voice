# F10 — Continuous listening: wake word detected in the live stream

**Date Created:** 2026-11-19
**Priority**: Medium
**Done:** no
**Tasks File Created:** yes
**Tests Written:** no
**Test Passing:** no

## Description

**Today listening switches between three modes.** The mic runs all the time, but only one consumer hears it at a time:

- **Waiting:** only openWakeWord hears the audio.
- **After the wake word:** only Vosk hears it, and wake detection is paused.
- **After the turn:** a cooldown (`wake_cooldown_secs`) during which nothing listens.

That causes three problems, all found on the robot on 2026-11-19 (I02):

- **"hey marvin explore" in one breath never works.** openWakeWord fires only after most of "marvin", so the start of the command has already gone to it.
- **There is dead time between turns.** A "hey marvin" spoken during the cooldown is lost, so the user has to wait.
- **A turn can't be restarted.** Saying "hey marvin" again during a turn isn't heard.

**The wake word stays.** It is still the gate in front of every command except F07's stop phrase. What changes is that it is detected continuously in the live stream.

### Approach

- **One reader, two listeners.** Every chunk goes to openWakeWord, always, including during a command.
- **A rolling buffer.** The last `preroll_secs` of audio is always kept (a `collections.deque` with `maxlen`).
- **On wake, Vosk starts from the buffer.** It is fed the buffered audio first, then live chunks, so nothing said right after the wake word is lost.
- **Vosk recognises the wake phrase too.** The buffer contains "hey marvin" itself. Its words are added to the grammar and removed from the transcript before intent mapping.
- **Endpointing counts only audio after the wake.** A pause after "hey marvin" behaves as today.
- **A wake during a turn restarts the turn.** The current capture is dropped, and a new one starts from the buffer.
- **No cooldown.** Its job (not re-triggering on the robot's own beeps and speech) moves to F04's muting.

### Decisions needed

- **Pre-roll length.** About 1.0 s should cover "hey marvin" plus detection delay; measure with F05's recordings.
- **Where the wake phrase's words come from.** The model name (`hey_marvin`) gives "hey marvin"; a custom `.onnx` would need a `wake_phrase` setting.
- **The wake beep.** In one-breath use it plays over the command. Shorten it, move it to the end of the turn, or drop it.

### Scope

- Continuous wake detection, the rolling buffer, feeding it to Vosk, stripping the wake phrase, restart on a second wake, and removing the cooldown.

### Out of scope

- Muting while the robot beeps or speaks: F04. **F10 depends on F04** to replace the cooldown.
- VAD endpointing (F06), and the always-on stop phrase (F07).

### Depends on

- **F04**, to replace the cooldown.
- **F05**, for measurement: its recordings already start 1 s before the wake.

## How to Demo
**Setup**: `bl dome_voice robot.launch.py`, and `ros2 topic echo /intent` in a second terminal.

**Steps**:
1. Say "hey marvin explore" in one breath, five times.
2. Say "hey marvin", pause, "explore", five times.
3. Right after a turn ends, say "hey marvin left".
4. Say "hey marvin, uh… hey marvin status".

**Expected output**: an intent for every attempt: `exploration_start` in 1 and 2; the turn in 3 isn't lost; 4 publishes the status intent once.
