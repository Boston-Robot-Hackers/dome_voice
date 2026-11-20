#!/usr/bin/env python3
# remote.launch.py — the LLM node, on the remote computer (the VM)
# Author: Pito Salas and Claude Code
# Version: 2
# Created: 2026-11-20
# Updated: 2026-11-20
# Open Source Under MIT license
#
# Usage:
#   bl dome_voice remote.launch.py
#   bl dome2 remote.launch.py --options "vi vo"        # via dome2's "voice" subsystem
"""Start `llm_node`: Whisper and Claude for the LLM command path (F14).

It gets the installed `config/llm_persona.md` as its `persona` parameter. To
change the persona, edit that file and rebuild. `ANTHROPIC_API_KEY` comes from
the shell environment, which the node inherits.

Per stack/launch_conventions.md this file starts only dome_voice's own nodes.
"""

from better_launch import BetterLaunch, launch_this


@launch_this(ui=True)
def remote_launch():
    """Start `llm_node` with the installed persona."""
    bl = BetterLaunch()
    params = {"persona": bl.find("dome_voice", "llm_persona.md")}
    bl.node("dome_voice", "llm_node", name="llm_node", params=params)
