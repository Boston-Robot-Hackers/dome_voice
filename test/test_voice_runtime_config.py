#!/usr/bin/env python3
# test_voice_runtime_config — voice config: defaults, YAML layering, overrides
# Author: Pito Salas and Claude Code
# Version: 2
# Created: 2026-11-19
# Updated: 2026-11-19
# Open Source Under MIT license
"""The voice config has one set of defaults, and a YAML overrides only its keys."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from dome_voice.intent_mapper import command_words
from dome_voice.runtime import load_voice_runtime_config

REPO = Path(__file__).resolve().parent.parent
ROBOT_YAML = REPO / "config" / "voice.yaml"
BASELINE = Path(__file__).resolve().parent / "fixtures" / "robot_config_baseline.json"


def write_yaml(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "voice.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_no_yaml_gives_the_defaults():
    cfg = load_voice_runtime_config()
    assert cfg.source_path == "defaults"
    assert (cfg.wake_word, cfg.threshold, cfg.wake_hits) == ("alexa", 0.3, 1)
    assert cfg.grammar == command_words()
    assert (cfg.highpass, cfg.lowpass) == (120.0, 4000.0)


def test_empty_yaml_gives_the_defaults(tmp_path):
    from_file = replace(
        load_voice_runtime_config(write_yaml(tmp_path, "")), source_path=""
    )
    defaults = replace(load_voice_runtime_config(), source_path="")
    assert from_file == defaults


def test_partial_yaml_overrides_only_its_keys(tmp_path):
    path = write_yaml(tmp_path, "stream_settings:\n  threshold: 0.5\n")
    cfg = load_voice_runtime_config(path)
    assert cfg.source_path == str(path)
    assert cfg.threshold == 0.5
    assert cfg.wake_hits == 1
    assert cfg.wake_word == "alexa"


def test_reads_all_sections(tmp_path):
    path = write_yaml(
        tmp_path,
        """
capture_card: 2
playback_card: 3
sox_chain: {highpass: 80, lowpass: 3000}
stream_settings: {wake_word: hey_marvin, wake_hits: 2}
beep: {fail_freq: 200}
""",
    )
    cfg = load_voice_runtime_config(path)
    assert (cfg.capture_card, cfg.playback_card) == (2, 3)
    assert (cfg.highpass, cfg.lowpass) == (80.0, 3000.0)
    assert (cfg.wake_word, cfg.wake_hits) == ("hey_marvin", 2)
    assert cfg.beep_fail_freq == 200


@pytest.mark.parametrize(
    "text, misspelled",
    [
        ("stream_settings:\n  treshold: 0.7\n", "treshold"),
        ("beeps:\n  wake_freq: 900\n", "beeps"),
        ("sox_chain:\n  bandpass: 100\n", "bandpass"),
    ],
)
def test_unknown_key_raises_and_names_it(tmp_path, text, misspelled):
    with pytest.raises(ValidationError) as error:
        load_voice_runtime_config(write_yaml(tmp_path, text))
    assert misspelled in str(error.value)


@pytest.mark.parametrize("spelling", ["none", "None", "''"])
def test_none_turns_a_cutoff_off(tmp_path, spelling):
    path = write_yaml(tmp_path, f"sox_chain:\n  highpass: {spelling}\n")
    assert load_voice_runtime_config(path).highpass is None


def test_grammar_key_raises_and_says_it_is_derived(tmp_path):
    path = write_yaml(tmp_path, "stream_settings:\n  grammar: [stop]\n")
    with pytest.raises(ValidationError) as error:
        load_voice_runtime_config(path)
    assert "derived from PHRASE_INTENTS" in str(error.value)


def test_grammar_override_is_unknown():
    with pytest.raises(ValueError):
        load_voice_runtime_config(overrides={"grammar": "stop"})


def test_out_of_range_value_raises(tmp_path):
    path = write_yaml(tmp_path, "stream_settings:\n  threshold: 1.5\n")
    with pytest.raises(ValidationError):
        load_voice_runtime_config(path)


def test_missing_named_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_voice_runtime_config(tmp_path / "missing.yaml")


@pytest.mark.parametrize(
    "name", ["DOME_VOICE_CONFIG", "CONTROL_VOICE_TUNE_CONFIG", "VOICE_TUNE_CONFIG"]
)
def test_environment_does_not_choose_the_file(monkeypatch, tmp_path, name):
    """No config-path env vars (dome2 stack/config_conventions.md)."""
    path = write_yaml(tmp_path, "stream_settings:\n  threshold: 0.4\n")
    monkeypatch.setenv(name, str(path))
    cfg = load_voice_runtime_config()
    assert cfg.source_path == "defaults"
    assert cfg.threshold == 0.3


def test_overrides_beat_the_yaml(tmp_path):
    path = write_yaml(tmp_path, "stream_settings:\n  threshold: 0.5\n  wake_hits: 2\n")
    cfg = load_voice_runtime_config(
        path,
        overrides={
            "threshold": 0.25,
            "wake_hits": None,
            "beep_wake_freq": 1000,
            "highpass": 90,
        },
    )
    assert cfg.threshold == 0.25
    assert cfg.wake_hits == 2
    assert cfg.beep_wake_freq == 1000
    assert cfg.highpass == 90


@pytest.mark.parametrize("key", ["treshold", "wake_freq", "beep_threshold"])
def test_unknown_override_raises(key):
    with pytest.raises(ValueError):
        load_voice_runtime_config(overrides={key: 1})


def test_bad_override_value_raises():
    with pytest.raises(ValidationError):
        load_voice_runtime_config(overrides={"wake_hits": 0})


def test_robot_yaml_matches_the_baseline():
    """config/voice.yaml must give what the robot ran before F02."""
    cfg = load_voice_runtime_config(ROBOT_YAML).to_dict()
    cfg.pop("source_path")
    cfg.pop("vosk_model_path")
    assert cfg == json.loads(BASELINE.read_text())
