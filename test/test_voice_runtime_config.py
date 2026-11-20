#!/usr/bin/env python3
# test_voice_runtime_config — voice config: defaults, YAML layering, overrides
# Author: Pito Salas and Claude Code
# Version: 4
# Created: 2026-11-19
# Updated: 2026-11-20
# Open Source Under MIT license
"""The voice config has one set of defaults, and a YAML overrides only its keys."""

from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from dome_voice.intent_mapper import command_words
from dome_voice.runtime import load_speech_settings, load_voice_runtime_config

REPO = Path(__file__).resolve().parent.parent
ROBOT_YAML = REPO / "config" / "voice.yaml"


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


def test_robot_yaml_is_valid():
    """The robot's voice settings load; their values are tuning, not tested."""
    load_voice_runtime_config(ROBOT_YAML)


def test_robot_yaml_does_not_record_turns():
    """Recording is switched on by hand for a session; it must not be committed."""
    assert load_voice_runtime_config(ROBOT_YAML).record_dir is None


def test_speech_defaults_with_an_empty_yaml(tmp_path):
    speech = load_speech_settings(write_yaml(tmp_path, ""))
    assert (speech.gain, speech.length_scale, speech.alsa_device) == (
        0.25,
        1.0,
        "plughw:0,0",
    )


def test_partial_speech_section_overrides_only_its_keys(tmp_path):
    speech = load_speech_settings(write_yaml(tmp_path, "speech:\n  gain: 0.7\n"))
    assert (speech.gain, speech.length_scale) == (0.7, 1.0)


def test_empty_alsa_device_means_alsa_default(tmp_path):
    path = write_yaml(tmp_path, 'speech:\n  alsa_device: ""\n')
    assert load_speech_settings(path).alsa_device == ""


@pytest.mark.parametrize("key, value", [("gain", "0"), ("length_scale", "-1")])
def test_speech_values_must_be_positive(tmp_path, key, value):
    path = write_yaml(tmp_path, f"speech:\n  {key}: {value}\n")
    with pytest.raises(ValueError, match=key):
        load_speech_settings(path)


def test_unknown_speech_key_raises(tmp_path):
    with pytest.raises(ValueError, match="volume"):
        load_speech_settings(write_yaml(tmp_path, "speech:\n  volume: 1\n"))


def test_speech_loader_rejects_bad_keys_elsewhere_in_the_file(tmp_path):
    path = write_yaml(tmp_path, "stream_settings:\n  treshold: 0.4\n")
    with pytest.raises(ValueError, match="treshold"):
        load_speech_settings(path)


def test_speech_loader_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_speech_settings(tmp_path / "missing.yaml")


def test_speech_does_not_change_the_voice_input_config(tmp_path):
    path = write_yaml(tmp_path, "speech:\n  gain: 0.9\n")
    assert load_voice_runtime_config(path) == replace(
        load_voice_runtime_config(), source_path=str(path)
    )


def test_robot_yaml_speech_section_is_valid():
    """The robot's speech settings load; their values are tuning, not tested."""
    load_speech_settings(ROBOT_YAML)
