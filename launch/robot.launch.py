#!/usr/bin/env python3
# robot.launch.py — voice nodes for the physical robot (Seeed board assumed present)
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-19
# Updated: 2026-11-19
# Open Source Under MIT license
#
# Usage:
#   bl dome_voice robot.launch.py                        # settings from the environment
#   bl dome_voice robot.launch.py --speech_gain 0.4
#   bl dome2 robot.launch.py --options "d vo"            # via dome2's "voice" subsystem
"""Start the voice nodes: `voice_input` and `speech_output`.

`voice_input` gets the installed `config/voice.yaml` as its `config`
parameter.

`speech_output` is configured through environment variables, so each argument
here sets one of them for that node. An empty argument (the default) means
the shell's variable, and if that is unset too, the value in `ENV_FALLBACKS`.
Those fallbacks differ from `speech_output`'s own defaults on purpose: they
are what the robot has always run with.

Per stack/launch_conventions.md this file starts only dome_voice's own nodes,
and its defaults are literals; the environment is read in the body.
"""

import os

from better_launch import BetterLaunch, launch_this

# argument name -> (environment variable, value when neither is set)
ENV_FALLBACKS = {
    "piper_bin": ("DOME_PIPER_BIN", "piper"),
    "piper_model_path": ("DOME_PIPER_MODEL_PATH", ""),
    "piper_length_scale": ("PIPER_LENGTH_SCALE", "1.0"),
    "speech_gain": ("SPEECH_GAIN", "0.25"),
    "speech_alsa_device": ("SPEECH_ALSA_DEVICE", "plughw:0,0"),
}


def speech_env(arguments: dict) -> dict:
    """The environment for `speech_output`: argument, else shell, else fallback."""
    env = {}
    for name, (variable, fallback) in ENV_FALLBACKS.items():
        env[variable] = arguments[name] or os.environ.get(variable, fallback)
    return env


@launch_this(ui=True)
def robot_launch(
    piper_bin: str = "",
    piper_model_path: str = "",
    piper_length_scale: str = "",
    speech_gain: str = "",
    speech_alsa_device: str = "",
):
    """Start `voice_input` and `speech_output`.

    Each argument overrides one environment variable for `speech_output`:

    - piper_bin: `DOME_PIPER_BIN`, the piper executable.
    - piper_model_path: `DOME_PIPER_MODEL_PATH`, the voice model file.
    - piper_length_scale: `PIPER_LENGTH_SCALE`; above 1.0 speaks slower.
    - speech_gain: `SPEECH_GAIN`, output volume.
    - speech_alsa_device: `SPEECH_ALSA_DEVICE`, the ALSA playback device.
    """
    bl = BetterLaunch()
    bl.node(
        "dome_voice",
        "voice_input",
        name="voice_input",
        params={"config": bl.find("dome_voice", "voice.yaml")},
    )
    bl.node(
        "dome_voice",
        "speech_output",
        "speech_output",
        env=speech_env(locals()),
    )
