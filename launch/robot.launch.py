#!/usr/bin/env python3
# robot.launch.py — voice nodes for the physical robot (Seeed board assumed present)
# Author: Pito Salas and Claude Code
# Version: 2
# Created: 2026-11-19
# Updated: 2026-11-20
# Open Source Under MIT license
#
# Usage:
#   bl dome_voice robot.launch.py
#   bl dome2 robot.launch.py --options "d vo"            # via dome2's "voice" subsystem
"""Start the voice nodes: `voice_input` and `speech_output`.

Both get the installed `config/voice.yaml` as their `config` parameter.
`voice_input` reads its sections; `speech_output` reads `speech:` (volume,
tempo, playback device; F13). To change one, edit the YAML and rebuild.

The Piper install paths, `DOME_PIPER_BIN` and `DOME_PIPER_MODEL_PATH`, are
not tuning, so they stay in the shell environment that `provision_dome`
sets up, and `speech_output` inherits them.

Per stack/launch_conventions.md this file starts only dome_voice's own nodes.
"""

from better_launch import BetterLaunch, launch_this


@launch_this(ui=True)
def robot_launch():
    """Start `voice_input` and `speech_output`, both reading the installed voice.yaml."""
    bl = BetterLaunch()
    params = {"config": bl.find("dome_voice", "voice.yaml")}
    bl.node("dome_voice", "voice_input", name="voice_input", params=params)
    bl.node("dome_voice", "speech_output", name="speech_output", params=params)
