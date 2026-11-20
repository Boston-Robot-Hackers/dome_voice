#!/usr/bin/env python3
# test_launch — the launch files start the right nodes with the installed config
# Author: Pito Salas and Claude Code
# Version: 3
# Created: 2026-11-19
# Updated: 2026-11-20
# Open Source Under MIT license
"""Checks which nodes robot.launch.py starts and the config each one gets.

`@launch_this` runs the launch when the file is imported, so the decorator is
stripped before the source is executed, and `BetterLaunch` is a mock. Nothing
starts.
"""

import importlib.util
import inspect
from pathlib import Path
from unittest.mock import MagicMock

LAUNCH_FILE = Path(__file__).resolve().parent.parent / "launch" / "robot.launch.py"
INSTALLED_YAML = "/install/share/voice.yaml"


def load_launch_module(launch_file: Path, better_launch: MagicMock):
    """Exec a launch file without its decorator, with BetterLaunch mocked."""
    source = launch_file.read_text().replace("@launch_this(ui=True)", "")
    spec = importlib.util.spec_from_loader("launch_under_test", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(compile(source, str(launch_file), "exec"), module.__dict__)  # noqa: S102
    module.BetterLaunch = better_launch
    return module


def launched_nodes() -> tuple[MagicMock, dict]:
    """Run the launch function; return the BetterLaunch mock and nodes by name."""
    better_launch = MagicMock()
    better_launch.return_value.find.return_value = INSTALLED_YAML
    load_launch_module(LAUNCH_FILE, better_launch).robot_launch()
    calls = better_launch.return_value.node.call_args_list
    return better_launch, {call.args[1]: call for call in calls}


def test_starts_both_voice_nodes():
    _, nodes = launched_nodes()
    assert list(nodes) == ["voice_input", "speech_output"]


def test_both_nodes_get_the_installed_config():
    better_launch, nodes = launched_nodes()
    better_launch.return_value.find.assert_called_once_with("dome_voice", "voice.yaml")
    for call in nodes.values():
        assert call.kwargs["params"] == {"config": INSTALLED_YAML}


def test_speech_output_gets_no_environment_overrides():
    """Speech settings come from the YAML; Piper paths are inherited (F13)."""
    _, nodes = launched_nodes()
    assert "env" not in nodes["speech_output"].kwargs


def test_launch_has_no_speech_arguments():
    module = load_launch_module(LAUNCH_FILE, MagicMock())
    assert inspect.signature(module.robot_launch).parameters == {}


REMOTE_LAUNCH_FILE = LAUNCH_FILE.parent / "remote.launch.py"
INSTALLED_PERSONA = "/install/share/llm_persona.md"


def remote_launched_nodes() -> tuple[MagicMock, dict]:
    """Run remote.launch.py with BetterLaunch mocked; return it and nodes by name."""
    better_launch = MagicMock()
    better_launch.return_value.find.return_value = INSTALLED_PERSONA
    load_launch_module(REMOTE_LAUNCH_FILE, better_launch).remote_launch()
    calls = better_launch.return_value.node.call_args_list
    return better_launch, {call.args[1]: call for call in calls}


def test_remote_starts_only_the_llm_node():
    _, nodes = remote_launched_nodes()
    assert list(nodes) == ["llm_node"]


def test_llm_node_gets_the_installed_persona():
    better_launch, nodes = remote_launched_nodes()
    better_launch.return_value.find.assert_called_once_with(
        "dome_voice", "llm_persona.md"
    )
    assert nodes["llm_node"].kwargs["params"] == {"persona": INSTALLED_PERSONA}
