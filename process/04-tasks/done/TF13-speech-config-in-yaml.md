# TF13 Speech output settings in voice.yaml for Feature F13

**Date Created:** 2026-11-20

## TF13.0 — `speech:` section in the config model
**Status**: done
**Description**: Add `SpeechSettings` (`gain` > 0, `length_scale` > 0, `alsa_device`) to `VoiceConfigFile` in `runtime.py`, with the robot's values as defaults. Add `load_speech_settings(path)`, which loads the YAML through the same strict model and returns the speech section. `VoiceRuntimeConfig` is unchanged, so `voice_input` and its baseline are not affected.

**Test**: defaults with no YAML; a partial `speech:` section overrides only its keys; an unknown key raises; gain or length scale ≤ 0 raises; a missing named file raises.

## TF13.1 — `speech_output` reads the YAML
**Status**: done
**Description**: `speech_output` gets the `config` parameter, loads `load_speech_settings`, and logs what it loaded. It stops reading `SPEECH_GAIN`, `PIPER_LENGTH_SCALE` and `SPEECH_ALSA_DEVICE`. `parse_speech_gain` and `parse_length_scale` go, because pydantic validates now.

**Test**: the node uses the YAML's values; a missing `config` parameter raises with a hint; the environment variables are ignored.

## TF13.2 — The launch file passes the YAML to both nodes
**Status**: done
**Description**: `robot.launch.py` gives `speech_output` the same `params={"config": ...}` as `voice_input`. Remove `ENV_FALLBACKS`, `speech_env`, and the launch arguments.

**Test**: both nodes get the installed `voice.yaml`; the launch function has no speech arguments.

## TF13.3 — The robot's YAML and the docs
**Status**: done
**Description**: Add the `speech:` section to `config/voice.yaml` (gain 0.5, length scale 1.0, `plughw:0,0`). Update the spec, the F12 spike README (how to start `speech_output` alone), and the literate docs for `runtime`, `speech_output_node` and the launch file.

**Test**: the robot YAML loads, and its speech section has the expected values.

## TF13.4 — Tests and a check on the robot
**Status**: done
**Description**: The full suite passes, apart from I01's 3 known failures. On the robot, `speech_output` started with the installed YAML speaks an announcement at the new volume.

**Test**: manual on the robot, 2026-11-20:
- `ros2 run dome_voice speech_output --ros-args -p config:=/home/pitosalas/ros2_ws/install/dome_voice/share/dome_voice/config/voice.yaml` logged `gain 0.5, length scale 1.0, device plughw:0,0` and spoke a test announcement.
- Without `config`, it exits with the `needs the config parameter` error.
- `bl dome_voice robot.launch.py` started both nodes; `/speech_output` had the installed YAML as `config`.
- Suite: 111 passed, plus I01's 3 known failures.
