# F08 — Support a USB mic array (ReSpeaker XVF3800)

**Date Created:** 2026-11-19
**Priority**: Low (until the hardware is bought)
**Done:** no
**Tasks File Created:** yes
**Tests Written:** no
**Test Passing:** no

## Description

As reported on the HBRC list, the Seeed 2-mic HAT "picks up a lot of noise… nothing like Alexa level." A **USB mic array with an on-board DSP** does beamforming, noise suppression and echo cancellation in hardware, at no CPU cost to the Pi. The **ReSpeaker XVF3800 USB 4-Mic Array** is the recommended board.

### Scope

- **Capture layout from config**: `capture_channels` and `capture_channel` (which channel to use) replace the hard-coded stereo average. The Seeed HAT stays the default (2 channels, average).
- **Playback through the array's output**, so its echo cancellation can hear what the robot says. `speech_output` and `beep` use the configured playback card. Today `beep` ignores both its `device_index` argument and `playback_card`.
- **Measure with F05's replay**: same phrases and noise, old board versus new.

### Out of scope

- Barge-in (interrupting the robot mid-sentence). Possible once echo cancellation works; a separate feature.
- Direction of arrival ("turn toward me"). A separate feature.

## How to Demo
**Setup**: XVF3800 plugged in; `voice.yaml` points at its card.

**Steps**:
1. Drive the robot and give commands.
2. Replay F05's recordings made on each board.

**Expected output**: commands work with motors running; replay shows fewer empty turns and false wakes than the Seeed baseline.
