#!/usr/bin/env python3
import json
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from dome_control.announcement_contract import (
    PRIORITY_CHITCHAT,
    PRIORITY_QUERY_REPLY,
    Announcement,
    make_announcement_msg,
)

from dome_voice import speech_output_node
from dome_voice.speech_output_node import (
    aplay_command,
    model_sample_rate,
    piper_command,
    scale_pcm,
    stream_speech,
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


def test_piper_command_streams_raw_audio():
    cmd = piper_command("piper", "/tmp/model.onnx", 1.4)
    assert cmd[:3] == ["piper", "--model", "/tmp/model.onnx"]
    assert "--output_raw" in cmd
    assert "--output_file" not in cmd
    assert cmd[cmd.index("--length_scale") + 1] == "1.4"
    assert "--quiet" in cmd


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


def fake_synth(n_samples: int, value: int) -> list[str]:
    """A synthesizer stand-in: reads all of stdin, writes constant int16 PCM."""
    script = (
        "import sys, struct; sys.stdin.read(); "
        f"sys.stdout.buffer.write(struct.pack('<h', {value}) * {n_samples})"
    )
    return [sys.executable, "-c", script]


def recorded_samples(path) -> list[int]:
    return np.frombuffer(path.read_bytes(), dtype="<i2").tolist()


def test_stream_speech_pipes_scaled_audio_to_player(tmp_path):
    out = tmp_path / "played.raw"
    stream_speech("hello", fake_synth(1000, 10000), ["sh", "-c", f"cat > {out}"], 0.5)
    assert recorded_samples(out) == [5000] * 1000


def test_stream_speech_carries_odd_bytes_across_reads(tmp_path, monkeypatch):
    monkeypatch.setattr(speech_output_node, "PCM_CHUNK_BYTES", 3)
    out = tmp_path / "played.raw"
    stream_speech("hi", fake_synth(50, 1234), ["sh", "-c", f"cat > {out}"], 1.0)
    assert recorded_samples(out) == [1234] * 50


def test_stream_speech_raises_when_player_fails():
    player = ["sh", "-c", "cat > /dev/null; echo no device >&2; exit 3"]
    with pytest.raises(RuntimeError, match=r"aplay failed \(3\): no device"):
        stream_speech("hello", fake_synth(100, 1), player, 1.0)


def test_stream_speech_raises_when_synth_fails():
    synth = ["sh", "-c", "cat > /dev/null; echo bad model >&2; exit 1"]
    with pytest.raises(RuntimeError, match="piper failed"):
        stream_speech("hello", synth, ["sh", "-c", "cat > /dev/null"], 1.0)


def test_stream_speech_cleans_up_when_player_dies_early():
    with pytest.raises((OSError, RuntimeError)):
        stream_speech("hello", fake_synth(200_000, 1), ["false"], 1.0)


@patch("dome_voice.speech_output_node.stream_speech")
def test_speak_text_streams_with_node_settings(mock_stream):
    from dome_voice.speech_output_node import SpeechOutputNode

    node = SpeechOutputNode.__new__(SpeechOutputNode)
    node.piper_bin = "piper"
    node.piper_model_path = "/tmp/model.onnx"
    node.alsa_device = "hw:1,0"
    node.speech_gain = 0.35
    node.length_scale = 1.25
    node.sample_rate = 22050

    SpeechOutputNode.speak_text(node, "hello")

    mock_stream.assert_called_once_with(
        "hello",
        piper_command("piper", "/tmp/model.onnx", 1.25),
        aplay_command(22050, "hw:1,0"),
        0.35,
    )


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
    with patch("rclpy.node.Node.__init__", return_value=None):
        SpeechOutputNode.__init__(node)
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
