---
version: "2.0"
generated: "2026-11-20"
---

# 05 — `launch/robot.launch.py`: Starting the Voice Nodes

## Introduction

`robot.launch.py` starts both voice nodes on the robot and hands each the same config file. **Since F13 (2026-11-20) it holds no settings of its own.** Everything the robot does is in `config/voice.yaml`.

It follows the stack-wide launch convention (`dome2/stack/launch_conventions.md`): **it starts only dome_voice's own nodes**, and dome2 combines it with the rest, as the `voice` subsystem.

```
bl dome_voice robot.launch.py
bl dome2 robot.launch.py --options "d vo"      # with the drivers, via dome2
```

## The whole launch

```python
@launch_this(ui=True)
def robot_launch():
    bl = BetterLaunch()
    params = {"config": bl.find("dome_voice", "voice.yaml")}
    bl.node("dome_voice", "voice_input", name="voice_input", params=params)
    bl.node("dome_voice", "speech_output", name="speech_output", params=params)
```

- **`bl.find` locates the *installed* copy** of `voice.yaml`, under `install/dome_voice/share/dome_voice/config/`. So a change to the YAML in the source tree needs `colcon build --packages-select dome_voice` before the robot sees it.
- **Both nodes get the same `config` parameter** and read their own sections: `voice_input` the wake, capture and beep settings, `speech_output` the `speech:` section.
- **Both nodes refuse to start without it.** There is no fallback config, so a node can't silently run on defaults.

## Where the environment still matters

`speech_output` needs `DOME_PIPER_BIN` and `DOME_PIPER_MODEL_PATH`, the Piper install paths. They are not tuning, so they are not in the YAML. `provision_dome` writes them into `~/.bashrc`, and the node **inherits** them from the shell that runs `bl`. The launch file passes no `env=`.

## What F13 removed

Before F13, this file built `speech_output`'s environment from five launch arguments, each resolved as *argument, else shell variable, else a fallback in `ENV_FALLBACKS`*. The fallbacks (gain 0.25, length scale 1.0, `plughw:0,0`) differed from the node's own defaults, so the robot's sound depended on how the node was started.

**Those values now live once, in `SpeechSettings`**, and `voice.yaml` writes out the robot's. The cost is that there are **no per-run overrides**: to try another volume, edit the YAML, rebuild, and relaunch.

## Testing it without launching

`@launch_this` starts the launch as soon as the file is imported, so `test/test_launch.py` **strips the decorator**, executes the source, and replaces `BetterLaunch` with a mock. It then checks:

- both nodes are started, in order
- each gets `{"config": <installed voice.yaml>}`
- `speech_output` gets no `env=` overrides
- the launch function takes no arguments

dome2's `test_launch_conventions.py` separately checks the header, the usage lines, the docstrings and the no-cross-package rule.

## Observations

1. **There is no hardware check.** The spec says a subsystem with missing hardware should say so and skip. This launch starts `voice_input` regardless, and it crashes when its dependencies are missing.
2. **A YAML edit needs a rebuild.** Because the launch uses the installed copy, editing `config/voice.yaml` does nothing until `colcon build`. A `--symlink-install` build would remove that step.
3. **There is no `remote.launch.py`.** It was deleted on 2026-11-19 (dome2 F05), because the voice board is only on the robot.
