#!/usr/bin/env python3
# test_speech_output_node — tests for the announcement-to-speech node
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-20
# Updated: 2026-11-20
# Open Source Under MIT license

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from dome_control.announcement_contract import (
    PRIORITY_CHITCHAT,
    PRIORITY_QUERY_REPLY,
    Announcement,
    make_announcement_msg,
)

from dome_voice.piper_server import SpeechCache
from dome_voice.speech_output_node import (
    Playback,
    aplay_command,
    model_sample_rate,
    scale_pcm,
)


def _make_node():
    with patch("rclpy.node.Node.__init__", return_value=None):
        from dome_voice.speech_output_node import SpeechOutputNode

        node = SpeechOutputNode.__new__(SpeechOutputNode)
        node.get_logger = MagicMock(return_value=MagicMock())
        node.piper_bin = "piper"
        node.piper_model_path = "/tmp/model.onnx"
        node.alsa_device = "hw:1,0"
        node.speech_gain = 0.35
        node.length_scale = 1.25
        node.speak_text = MagicMock()
        node.speaking_pub = MagicMock()
        return SpeechOutputNode, node


def test_parse_announcement_payload_json():
    payload = json.dumps(
        {
            "text": "I see a can",
            "priority": PRIORITY_QUERY_REPLY,
            "source": "behavior_manager",
        }
    )
    parsed = Announcement.from_payload(payload)
    assert parsed == Announcement(
        text="I see a can",
        priority=PRIORITY_QUERY_REPLY,
        source="behavior_manager",
    )


def test_parse_announcement_payload_plain_text():
    parsed = Announcement.from_payload("hello robot")
    assert parsed == Announcement(
        text="hello robot",
        priority=PRIORITY_CHITCHAT,
        source="unknown",
    )


def test_parse_announcement_payload_empty_text():
    parsed = Announcement.from_payload("   ")
    assert parsed.text == ""


def test_on_announcement_calls_speak_text():
    SpeechOutputNode, node = _make_node()
    msg = make_announcement_msg(
        "hello there",
        priority=PRIORITY_QUERY_REPLY,
        source="test",
    )
    SpeechOutputNode.on_announcement(node, msg)
    node.speak_text.assert_called_once_with("hello there")


def test_on_announcement_ignores_empty():
    SpeechOutputNode, node = _make_node()
    msg = make_announcement_msg("   ")
    SpeechOutputNode.on_announcement(node, msg)
    node.speak_text.assert_not_called()


def test_aplay_command_reads_raw_mono_at_model_rate():
    assert aplay_command(22050, "hw:1,0") == [
        "aplay", "-q", "-D", "hw:1,0",
        "-t", "raw", "-f", "S16_LE", "-r", "22050", "-c", "1",
    ]  # fmt: skip


def test_aplay_command_without_device_uses_default():
    assert "-D" not in aplay_command(16000)


def test_model_sample_rate_reads_piper_json(tmp_path):
    model = tmp_path / "voice.onnx"
    (tmp_path / "voice.onnx.json").write_text(
        json.dumps({"audio": {"sample_rate": 22050}})
    )
    assert model_sample_rate(str(model)) == 22050


def test_model_sample_rate_requires_model_path():
    with pytest.raises(RuntimeError, match="DOME_PIPER_MODEL_PATH"):
        model_sample_rate("")


def test_scale_pcm_scales_and_clips():
    pcm = np.array([10000, -10000, 30000], dtype="<i2").tobytes()
    scaled = np.frombuffer(scale_pcm(pcm, 0.35), dtype="<i2").tolist()
    assert scaled == [3500, -3500, 10500]
    loud = np.frombuffer(scale_pcm(pcm, 2.0), dtype="<i2").tolist()
    assert loud == [20000, -20000, 32767]


def recorded_samples(path) -> list[int]:
    return np.frombuffer(path.read_bytes(), dtype="<i2").tolist()


def copying_player(out) -> list[str]:
    """A player stand-in: copies the file it's given (appended last) to `out`."""
    return ["sh", "-c", f'cp "$1" {out}', "sh"]


def test_playback_plays_the_pcm_from_a_file(tmp_path):
    out = tmp_path / "played.raw"
    pcm = np.full(1000, 5000, dtype="<i2").tobytes()
    Playback(pcm, copying_player(out), tmp_path / "s.raw").wait()
    assert recorded_samples(out) == [5000] * 1000


def test_playback_removes_its_file(tmp_path):
    Playback(b"\x00\x00", ["true"], tmp_path / "s.raw").wait()
    assert not (tmp_path / "s.raw").exists()


def test_playback_raises_when_the_player_fails(tmp_path):
    player = ["sh", "-c", "echo no device >&2; exit 3", "sh"]
    playback = Playback(b"\x00\x00", player, tmp_path / "s.raw")
    with pytest.raises(RuntimeError, match=r"aplay failed \(3\): no device"):
        playback.wait()


def test_playback_stop_cuts_it_short(tmp_path):
    playback = Playback(b"\x00\x00", ["sleep", "30"], tmp_path / "s.raw")
    playback.stop()
    assert playback.proc.poll() is not None
    assert not (tmp_path / "s.raw").exists()


class RecordingPlayback:
    """Stands in for Playback and records the order of plays and waits."""

    def __init__(self, events: list, fail_wait: bool = False):
        self.events = events
        self.fail_wait = fail_wait

    def __call__(self, pcm, play_cmd, path):
        self.events.append(("play", pcm))
        playback = MagicMock()
        playback.wait.side_effect = self.waiter(pcm)
        playback.stop.side_effect = lambda: self.events.append(("stop", pcm))
        return playback

    def waiter(self, pcm):
        def wait():
            self.events.append(("wait", pcm))
            if self.fail_wait:
                raise RuntimeError("aplay failed (1): busy")

        return wait


def speaking_node(events: list):
    """A SpeechOutputNode with a recording fake Piper and a real cache, ROS skipped."""
    from dome_voice.speech_output_node import SpeechOutputNode

    node = SpeechOutputNode.__new__(SpeechOutputNode)
    node.alsa_device = "hw:1,0"
    node.speech_gain = 1.0
    node.sample_rate = 22050
    node.piper = MagicMock()

    def synthesize(sentence):
        events.append(("synth", sentence))
        return sentence.encode()[:2].ljust(2, b"\x00")

    node.piper.synthesize.side_effect = synthesize
    node.cache = SpeechCache()
    return SpeechOutputNode, node


def test_speak_text_synthesises_the_next_sentence_while_one_plays():
    events = []
    SpeechOutputNode, node = speaking_node(events)
    with patch("dome_voice.speech_output_node.Playback", RecordingPlayback(events)):
        SpeechOutputNode.speak_text(node, "Why did it cross? To charge.")
    assert events == [
        ("synth", "Why did it cross?"),
        ("play", b"Wh"),
        ("synth", "To charge."),
        ("wait", b"Wh"),
        ("play", b"To"),
        ("wait", b"To"),
    ]


def test_repeated_sentences_are_played_from_the_cache():
    events = []
    SpeechOutputNode, node = speaking_node(events)
    with patch("dome_voice.speech_output_node.Playback", RecordingPlayback(events)):
        SpeechOutputNode.speak_text(node, "linear speed 0.2, angular speed 0.7")
        SpeechOutputNode.speak_text(node, "linear speed 0.2, angular speed 0.7")
    synths = [event for event in events if event[0] == "synth"]
    assert synths == [("synth", "linear speed 0.2, angular speed 0.7")]


def test_speak_text_scales_by_the_gain():
    events = []
    SpeechOutputNode, node = speaking_node(events)
    node.speech_gain = 0.5
    node.piper.synthesize.side_effect = None
    node.piper.synthesize.return_value = np.array([10000], dtype="<i2").tobytes()
    with patch("dome_voice.speech_output_node.Playback", RecordingPlayback(events)):
        SpeechOutputNode.speak_text(node, "hello")
    assert events[0] == ("play", np.array([5000], dtype="<i2").tobytes())


def test_failed_playback_is_stopped_and_raised():
    events = []
    SpeechOutputNode, node = speaking_node(events)
    with (
        patch(
            "dome_voice.speech_output_node.Playback",
            RecordingPlayback(events, fail_wait=True),
        ),
        pytest.raises(RuntimeError, match="aplay failed"),
    ):
        SpeechOutputNode.speak_text(node, "One. Two.")
    assert events[-1][0] == "stop"


def test_destroy_node_stops_piper():
    SpeechOutputNode, node = speaking_node([])
    with patch("rclpy.node.Node.destroy_node"):
        SpeechOutputNode.destroy_node(node)
    node.piper.close.assert_called_once()


def init_node(monkeypatch, tmp_path, yaml_text: str, config_param: str | None = None):
    """Run SpeechOutputNode.__init__ with ROS mocked; return the node."""
    from dome_voice.speech_output_node import SpeechOutputNode

    config = tmp_path / "voice.yaml"
    config.write_text(yaml_text)
    model = tmp_path / "voice.onnx"
    (tmp_path / "voice.onnx.json").write_text('{"audio": {"sample_rate": 22050}}')
    monkeypatch.setenv("DOME_PIPER_MODEL_PATH", str(model))
    node = SpeechOutputNode.__new__(SpeechOutputNode)
    node.create_subscription = MagicMock()
    node.create_publisher = MagicMock()
    node.get_logger = MagicMock()
    node.declare_parameter = MagicMock()
    node.get_parameter = MagicMock()
    param = node.get_parameter.return_value.get_parameter_value.return_value
    param.string_value = str(config) if config_param is None else config_param
    with (
        patch("rclpy.node.Node.__init__", return_value=None),
        patch("dome_voice.speech_output_node.PiperServer") as piper_server,
    ):
        SpeechOutputNode.__init__(node)
    node.piper_server_class = piper_server
    return node


def test_node_reads_speech_settings_from_the_yaml(monkeypatch, tmp_path):
    yaml_text = "speech:\n  gain: 0.6\n  length_scale: 1.2\n  alsa_device: hw:2,0\n"
    node = init_node(monkeypatch, tmp_path, yaml_text)
    assert (node.speech_gain, node.length_scale, node.alsa_device) == (
        0.6,
        1.2,
        "hw:2,0",
    )
    assert node.sample_rate == 22050


def test_node_starts_one_piper_at_startup(monkeypatch, tmp_path):
    node = init_node(monkeypatch, tmp_path, "speech:\n  length_scale: 1.2\n")
    node.piper_server_class.assert_called_once()
    command, sample_rate, _out_dir = node.piper_server_class.call_args.args
    assert "--json-input" in command
    assert command[command.index("--length_scale") + 1] == "1.2"
    assert sample_rate == 22050


def test_node_ignores_the_old_environment_variables(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEECH_GAIN", "0.9")
    monkeypatch.setenv("PIPER_LENGTH_SCALE", "2.0")
    monkeypatch.setenv("SPEECH_ALSA_DEVICE", "hw:9,0")
    node = init_node(monkeypatch, tmp_path, "")
    assert (node.speech_gain, node.length_scale, node.alsa_device) == (
        0.25,
        1.0,
        "plughw:0,0",
    )


def test_node_without_config_parameter_raises(monkeypatch, tmp_path):
    with pytest.raises(RuntimeError, match="config"):
        init_node(monkeypatch, tmp_path, "", config_param="")


def test_node_with_bad_speech_value_fails_to_start(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="gain"):
        init_node(monkeypatch, tmp_path, "speech:\n  gain: 0\n")


def speaking_states(node) -> list[bool]:
    return [call.args[0].data for call in node.speaking_pub.publish.call_args_list]


def test_on_announcement_publishes_speaking_around_speech():
    SpeechOutputNode, node = _make_node()
    states_at_speech = []
    node.speak_text.side_effect = lambda _text: states_at_speech.append(
        speaking_states(node)
    )
    msg = make_announcement_msg("hello", priority=PRIORITY_QUERY_REPLY, source="t")
    SpeechOutputNode.on_announcement(node, msg)
    assert states_at_speech == [[True]]
    assert speaking_states(node) == [True, False]


def test_on_announcement_clears_speaking_when_speech_fails():
    SpeechOutputNode, node = _make_node()
    node.speak_text.side_effect = RuntimeError("aplay failed")
    msg = make_announcement_msg("hello", priority=PRIORITY_QUERY_REPLY, source="t")
    SpeechOutputNode.on_announcement(node, msg)
    assert speaking_states(node) == [True, False]


def test_empty_announcement_publishes_no_speaking():
    SpeechOutputNode, node = _make_node()
    msg = make_announcement_msg("  ", priority=PRIORITY_QUERY_REPLY, source="t")
    SpeechOutputNode.on_announcement(node, msg)
    assert speaking_states(node) == []
