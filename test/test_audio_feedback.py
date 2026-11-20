#!/usr/bin/env python3
# test_audio_feedback — tests for the aplay beep.
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-20
# Updated: 2026-11-20
# Open Source Under MIT license

import subprocess
from unittest.mock import patch

import pytest

from dome_voice.audio_feedback import beep


def completed(returncode: int, stderr: bytes = b"") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(["aplay"], returncode, b"", stderr)


def test_beep_raises_when_aplay_fails():
    failed = completed(1, b"aplay: main: audio open error: Device or resource busy")
    with (
        patch("dome_voice.audio_feedback.subprocess.run", return_value=failed),
        pytest.raises(RuntimeError, match="Device or resource busy"),
    ):
        beep(duration=0.01)


def test_beep_sends_stereo_tone_to_aplay():
    with patch(
        "dome_voice.audio_feedback.subprocess.run", return_value=completed(0)
    ) as run:
        beep(duration=0.01)

    cmd = run.call_args.args[0]
    assert cmd[:2] == ["aplay", "-q"]
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "2"
    assert len(run.call_args.kwargs["input"]) == int(16000 * 0.01) * 4
