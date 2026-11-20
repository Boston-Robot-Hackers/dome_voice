# F04 — Don't listen while the robot is speaking

**Date Created:** 2026-11-19
**Priority**: High
**Done:** yes
**Tasks File Created:** yes
**Tests Written:** yes
**Test Passing:** yes

## Description

**The robot can hear itself.** `speech_output` plays through the speaker while `voice_input`'s mic is open, and the two nodes don't coordinate. The Seeed 2-mic HAT has no echo cancellation, so this has to be solved in software: **half-duplex**, the way most hobby voice robots do it.

### Scope

- **`speech_output` publishes whether it is speaking** on `/voice/speaking` (`std_msgs/Bool`): true before playback starts, false after it ends (including on error).
- **`voice_input` suspends wake detection while speaking is true**, then drains the mic for `wake_cooldown_secs` after it goes false. Audio is still read so the pipe never backs up.
- **The core library stays ROS-free.** `next_turn` already takes `ok_fn`; it gains a similar `is_muted_fn` callable. The node supplies it from the topic.
- Beeps are already played by `voice_input` itself, so they are covered by the existing cooldown.

### Out of scope

- Interrupting the robot mid-sentence (barge-in). It needs echo cancellation (F08's mic array).
- Moving `speech_output` to a queue, or loading Piper once. Worth doing; a separate feature.

## How to Demo
**Setup**: voice stack running.

**Steps**:
1. `ros2 topic pub --once /announcement ...` with text containing "hey marvin stop".
2. Watch `voice_input`'s log and `/intent`.

**Expected output**: the robot speaks the sentence; no wake is detected and no intent is published.
