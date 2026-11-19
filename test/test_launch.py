#!/usr/bin/env python3
# test_launch — robot.launch.py's environment precedence for speech_output
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-19
# Updated: 2026-11-19
# Open Source Under MIT license
"""Checks which value each speech setting gets: argument, shell, or fallback.

`@launch_this` runs the launch when the file is imported, so the decorator is
stripped before the source is executed, and `BetterLaunch` is a mock. Nothing
starts.
"""

import importlib.util
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

LAUNCH_FILE = Path(__file__).resolve().parent.parent / "launch" / "robot.launch.py"


def load_launch_module(better_launch: MagicMock):
    """Exec robot.launch.py without its decorator, with BetterLaunch mocked."""
    source = LAUNCH_FILE.read_text().replace("@launch_this(ui=True)", "")
    spec = importlib.util.spec_from_loader("robot_launch_under_test", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(compile(source, str(LAUNCH_FILE), "exec"), module.__dict__)  # noqa: S102
    module.BetterLaunch = better_launch
    return module


def speech_output_env(monkeypatch, shell_env: dict, **arguments) -> dict:
    """Run the launch function and return the env it gives `speech_output`."""
    better_launch = MagicMock()
    module = load_launch_module(better_launch)
    for variable, _fallback in module.ENV_FALLBACKS.values():
        monkeypatch.delenv(variable, raising=False)
    for variable, value in shell_env.items():
        monkeypatch.setenv(variable, value)
    module.robot_launch(**arguments)
    calls = better_launch.return_value.node.call_args_list
    (speech,) = [c for c in calls if c.args[1] == "speech_output"]
    return speech.kwargs["env"]


def test_defaults_are_literals():
    better_launch = MagicMock()
    signature = inspect.signature(load_launch_module(better_launch).robot_launch)
    assert {p.default for p in signature.parameters.values()} == {""}


def test_fallbacks_when_nothing_is_set(monkeypatch):
    env = speech_output_env(monkeypatch, {})
    assert env == {
        "DOME_PIPER_BIN": "piper",
        "DOME_PIPER_MODEL_PATH": "",
        "PIPER_LENGTH_SCALE": "1.0",
        "SPEECH_GAIN": "0.25",
        "SPEECH_ALSA_DEVICE": "plughw:0,0",
    }


def test_shell_variable_beats_fallback(monkeypatch):
    env = speech_output_env(monkeypatch, {"SPEECH_GAIN": "0.6"})
    assert env["SPEECH_GAIN"] == "0.6"


@pytest.mark.parametrize("shell_env", [{}, {"SPEECH_GAIN": "0.6"}])
def test_argument_beats_shell_and_fallback(monkeypatch, shell_env):
    env = speech_output_env(monkeypatch, shell_env, speech_gain="0.4")
    assert env["SPEECH_GAIN"] == "0.4"


def test_voice_input_gets_the_installed_config():
    better_launch = MagicMock()
    better_launch.return_value.find.return_value = "/install/share/voice.yaml"
    load_launch_module(better_launch).robot_launch()
    better_launch.return_value.find.assert_called_once_with("dome_voice", "voice.yaml")
    calls = better_launch.return_value.node.call_args_list
    (voice_input,) = [c for c in calls if c.args[1] == "voice_input"]
    assert voice_input.kwargs["params"] == {"config": "/install/share/voice.yaml"}


def test_starts_both_voice_nodes(monkeypatch):
    better_launch = MagicMock()
    load_launch_module(better_launch).robot_launch()
    started = [c.args[1] for c in better_launch.return_value.node.call_args_list]
    assert started == ["voice_input", "speech_output"]
