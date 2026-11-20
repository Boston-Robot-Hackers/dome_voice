# F13 — Speech output settings in voice.yaml

**Date Created:** 2026-11-20
**Priority**: Medium
**Done:** yes
**Tasks File Created:** yes
**Tests Written:** yes
**Test Passing:** yes
**Description**: `speech_output` reads its volume, tempo and playback device from `config/voice.yaml`, the same way `voice_input` reads its settings (F02). This closes the gap the spec names: *"speech_output ... Should move to the same YAML pattern; not yet a feature."*

## The problem today

- **Speech settings have three layers of defaults that disagree:** `speech_output_node.py`'s own (gain 0.35, length scale 1.25), `robot.launch.py`'s `ENV_FALLBACKS` (0.25, 1.0, `plughw:0,0`), and the shell's variables.
- **Volume isn't where the rest of the voice config is.** To change it you set `SPEECH_GAIN` or pass a launch argument, and you can't see from any file what the robot uses.
- **Running `speech_output` by hand** (as the F12 spike does) gets the node's defaults, not the robot's, unless all three variables are given on the command line.

## Scope

- **A `speech:` section in `voice.yaml`**, validated by the same strict pydantic model (`VoiceConfigFile`): `gain` (> 0), `length_scale` (> 0), `alsa_device` (a string; empty means ALSA's default).
- **The defaults live once, in the model.** They are the values the robot ran with: gain 0.25, length scale 1.0, device `plughw:0,0`.
- **`voice.yaml` writes the robot's values out**, like every other section. The gain goes to **0.5**, because the robot was too quiet on 2026-11-20.
- **`speech_output` takes the YAML as its `config` parameter**, as `voice_input` does, and refuses to start without it.
- **`robot.launch.py` passes the installed `voice.yaml` to both nodes.** `ENV_FALLBACKS`, `speech_env` and the five speech launch arguments go away.
- **`SPEECH_GAIN`, `PIPER_LENGTH_SCALE` and `SPEECH_ALSA_DEVICE` are no longer read.**

## Out of scope

- **`DOME_PIPER_BIN` and `DOME_PIPER_MODEL_PATH` stay environment variables.** They are install paths that `provision_dome` writes into `~/.bashrc`, so they differ per machine and are not tuning.
- **No per-run overrides** for speech settings. To try another volume, edit the YAML, rebuild and restart the node.
- **`beep()`'s device.** It still reads `SPEECH_ALSA_DEVICE`, which nothing sets now, so beeps use ALSA's default. Logged as a chore; TF08 plans `playback_card`.

## How to Demo
**Setup**: `colcon build --packages-select dome_voice`, then `source /home/pitosalas/ros2_ws/install/setup.bash`.

**Steps**:
1. Start the voice nodes: `bl dome_voice robot.launch.py`.
2. Publish an announcement: `ros2 topic pub --once /announcement dome_control/msg/Announcement "{text: 'Testing the new volume.', priority: 2, source: test}"`.
3. Change `speech: gain:` in `/home/pitosalas/ros2_ws/src/dome_voice/config/voice.yaml`, rebuild, relaunch, and publish again.

**Expected output**: The robot speaks at the volume the YAML sets. `speech_output` logs the gain, length scale and device it loaded, and the file they came from.
