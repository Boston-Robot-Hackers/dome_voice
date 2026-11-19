---
version: "1.0"
generated: "2026-11-19"
---

# 05 — `launch/robot.launch.py`: Starting the Voice Nodes

## Introduction

`robot.launch.py` starts both voice nodes on the robot. It is small, but it is where `speech_output`'s settings actually come from, so it decides how the robot sounds.

It follows the stack-wide launch convention (`dome2/stack/launch_conventions.md`):

- **It starts only dome_voice's own nodes.** dome2 combines it with the rest, as the `voice` subsystem.
- **Its argument defaults are literals.** The environment is read in the body.

```
bl dome_voice robot.launch.py                  # settings from the environment
bl dome_voice robot.launch.py --speech_gain 0.4
bl dome2 robot.launch.py --options "d vo"      # with the drivers, via dome2
```

## Why the launch file passes environment variables

`speech_output_node` reads its settings from environment variables, not ROS parameters (chapter 04). So the launch file's job is to **build that node's environment**:

```python
bl.node("dome_voice", "voice_input", name="voice_input")
bl.node("dome_voice", "speech_output", "speech_output", env=speech_env(locals()))
```

better_launch **merges** `env` into the inherited environment, rather than replacing it, so the node still sees `PATH` and everything else.

`voice_input` gets one parameter, `config`: the installed `voice.yaml`, found with `bl.find("dome_voice", "voice.yaml")`. The node raises if it is empty, so it can only be started with a config.

## Three-level precedence

Each of the five speech settings is resolved in a fixed order:

1. **The launch argument**, if given on the command line.
2. **The shell's environment variable**, if set.
3. **The launch file's fallback**, from `ENV_FALLBACKS`.

```python
ENV_FALLBACKS = {
    "piper_bin": ("DOME_PIPER_BIN", "piper"),
    "piper_model_path": ("DOME_PIPER_MODEL_PATH", ""),
    "piper_length_scale": ("PIPER_LENGTH_SCALE", "1.0"),
    "speech_gain": ("SPEECH_GAIN", "0.25"),
    "speech_alsa_device": ("SPEECH_ALSA_DEVICE", "plughw:0,0"),
}

def speech_env(arguments: dict) -> dict:
    env = {}
    for name, (variable, fallback) in ENV_FALLBACKS.items():
        env[variable] = arguments[name] or os.environ.get(variable, fallback)
    return env
```

One table holds, for each argument, the variable it sets and the value used when nothing else says otherwise. Adding a sixth setting is one line.

### Why not `os.environ.get` in the signature?

That's how the file used to read:

```python
piper_bin: str = os.environ.get("DOME_PIPER_BIN", "piper"),
```

It looks natural, but **better_launch reads arguments by parsing the source**, not by running it. It can't evaluate a call, so the convention requires literal defaults. The empty string `""` now means "not given", and the body does the lookup.

### Why these fallbacks, and not the node's

The fallbacks here **differ from `speech_output`'s own defaults** (gain 0.25 vs 0.35, length scale 1.0 vs 1.25, device `plughw:0,0` vs the ALSA default). They are kept because they are what the robot has always run with. Using the node's defaults instead would have changed how the robot sounds, as a side effect of a launch-file cleanup.

**One subtlety of `or`:** an argument can't be set *to* the empty string, because `""` already means "not given". None of these settings has a useful empty value except `piper_model_path`, which is required anyway.

## Testing it without launching

`@launch_this` starts the launch as soon as the file is imported, so `test/test_launch.py` **strips the decorator**, executes the source, and replaces `BetterLaunch` with a mock. It then checks:

- every default is the literal `""`
- with nothing set, the env is exactly the five fallbacks
- a shell variable beats a fallback, and an argument beats both
- both nodes are started

dome2's `test_launch_conventions.py` separately checks the header, the usage lines, the docstrings and the no-cross-package rule.

## Observations

1. **Two places hold the speech defaults.** This file and `speech_output_node` each have their own. Moving the robot's values into the node, and deleting `ENV_FALLBACKS`' numbers, would leave one source.
2. **`locals()` is compact but implicit.** It passes every local, including `bl`, and relies on `speech_env` looking up only the names it knows. An explicit dict would be longer but plainer.
3. **There is no hardware check.** The spec says a subsystem with missing hardware should say so and skip. This launch starts `voice_input` regardless, and it crashes when its dependencies are missing.
4. **There is no `remote.launch.py`.** It was deleted on 2026-11-19 (dome2 F05), because the voice board is only on the robot.
