#!/usr/bin/env python3
# test_voice_input_node — tests for voice_input's publishing, muting and LLM relay
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-20
# Updated: 2026-11-20
# Open Source Under MIT license

import json
from unittest.mock import MagicMock, patch

import pytest


def _make_voice_node():
    with patch("rclpy.node.Node.__init__", return_value=None):
        import dome_voice.voice_input_node as vin

        node = vin.VoiceInputNode.__new__(vin.VoiceInputNode)
        node.intent_pub = MagicMock()
        node.state_pub = MagicMock()
        node.get_logger = MagicMock(return_value=MagicMock())
        return vin, node


def test_publish_intent():
    _, node = _make_voice_node()
    from dome_voice.voice_input_node import VoiceInputNode

    VoiceInputNode.publish_intent(
        node, {"name": "stop", "source": "voice", "slots": {}}
    )
    node.intent_pub.publish.assert_called_once()
    msg = node.intent_pub.publish.call_args[0][0]
    assert json.loads(msg.data) == {"name": "stop", "source": "voice", "slots": {}}


def test_publish_state():
    _, node = _make_voice_node()
    from dome_voice.voice_input_node import VoiceInputNode

    VoiceInputNode.publish_state(node, "LISTENING")
    node.state_pub.publish.assert_called_once()
    msg = node.state_pub.publish.call_args[0][0]
    assert msg.data == "LISTENING"


def test_process_transcript_known_intent():
    _, node = _make_voice_node()
    from dome_voice.voice_input_node import VoiceInputNode

    node.intent_mapper = MagicMock()
    node.intent_mapper.map_intent.return_value = {
        "name": "describe_scene",
        "source": "voice",
        "slots": {},
    }
    node.publish_state = MagicMock()
    node.publish_intent = MagicMock()

    with patch("dome_voice.voice_input_node.beep") as mock_beep:
        VoiceInputNode.process_transcript(node, "describe", device_index=2)

    node.publish_state.assert_any_call("PROCESSING")
    node.publish_state.assert_any_call("SPEAKING")
    node.publish_intent.assert_called_once()
    mock_beep.assert_called_once_with(frequency=330, duration=0.02, device_index=2)


def test_process_transcript_unknown_intent():
    _, node = _make_voice_node()
    from dome_voice.voice_input_node import VoiceInputNode

    node.intent_mapper = MagicMock()
    node.intent_mapper.map_intent.return_value = None
    node.publish_state = MagicMock()
    node.publish_intent = MagicMock()

    with patch("dome_voice.voice_input_node.beep") as mock_beep:
        VoiceInputNode.process_transcript(node, "blah blah")

    node.publish_state.assert_any_call("PROCESSING")
    node.publish_state.assert_any_call("SPEAKING")
    node.publish_intent.assert_not_called()
    mock_beep.assert_called_once_with(frequency=220, duration=0.15, device_index=0)


def test_process_turn_transcript_path():
    _, node = _make_voice_node()
    from dome_voice import VoiceTurn
    from dome_voice.voice_input_node import VoiceInputNode

    node.process_transcript = MagicMock()
    turn = VoiceTurn(text="stop", raw_text="stop", empty=False)

    VoiceInputNode.process_turn(node, turn, device_index=1)

    node.process_transcript.assert_called_once_with("stop", device_index=1)


def test_process_turn_empty_plays_beep():
    _, node = _make_voice_node()
    from dome_voice import VoiceTurn
    from dome_voice.voice_input_node import VoiceInputNode

    node.publish_state = MagicMock()

    with patch("dome_voice.voice_input_node.beep") as mock_beep:
        VoiceInputNode.process_turn(node, VoiceTurn(empty=True))

    node.publish_state.assert_called_once_with("SPEAKING")
    mock_beep.assert_called_once_with(frequency=220, duration=0.15, device_index=0)


def node_with_config_param(value: str):
    import dome_voice.voice_input_node as vin

    node = vin.VoiceInputNode.__new__(vin.VoiceInputNode)
    node.declare_parameter = MagicMock()
    node.get_parameter = MagicMock()
    node.get_parameter.return_value.get_parameter_value.return_value.string_value = (
        value
    )
    return node


def test_config_path_comes_from_the_parameter():
    assert node_with_config_param("/x/voice.yaml").config_path() == "/x/voice.yaml"


def test_empty_config_parameter_is_an_error(monkeypatch, tmp_path):
    """No fallback, not even to a DOME_VOICE_CONFIG left in the shell."""
    monkeypatch.setenv("DOME_VOICE_CONFIG", str(tmp_path / "ignored.yaml"))
    with pytest.raises(RuntimeError):
        node_with_config_param("").config_path()


def test_on_speaking_stores_latest_value():
    _, node = _make_voice_node()
    from std_msgs.msg import Bool

    from dome_voice.voice_input_node import VoiceInputNode

    VoiceInputNode.on_speaking(node, Bool(data=True))
    assert node.is_speaking is True
    VoiceInputNode.on_speaking(node, Bool(data=False))
    assert node.is_speaking is False


def llm_node():
    _, node = _make_voice_node()
    node.utterance_pub = MagicMock()
    node.announce_pub = MagicMock()
    node.play_beep = MagicMock()
    return node


def test_llm_reply_is_announced():
    from std_msgs.msg import String

    from dome_voice.voice_input_node import VoiceInputNode

    node = llm_node()
    VoiceInputNode.on_llm_reply(node, String(data="Hello there."))
    msg = node.announce_pub.publish.call_args[0][0]
    assert (msg.text, msg.source) == ("Hello there.", "llm")


def test_empty_llm_reply_is_not_announced():
    from std_msgs.msg import String

    from dome_voice.voice_input_node import VoiceInputNode

    node = llm_node()
    VoiceInputNode.on_llm_reply(node, String(data=""))
    node.announce_pub.publish.assert_not_called()


def test_utterance_is_published_as_pcm_bytes():
    import numpy as np

    from dome_voice.utterance_capture import VoiceUtterance
    from dome_voice.voice_input_node import VoiceInputNode

    node = llm_node()
    pcm = np.array([1, -2, 300], dtype=np.int16)
    VoiceInputNode.process_utterance(node, VoiceUtterance(True, pcm, {}), 0)
    msg = node.utterance_pub.publish.call_args[0][0]
    assert bytes(msg.data) == pcm.tobytes()
    node.play_beep.assert_not_called()


def test_utterance_without_speech_beeps_fail_and_publishes_nothing():
    from dome_voice.utterance_capture import VoiceUtterance
    from dome_voice.voice_input_node import VoiceInputNode

    node = llm_node()
    VoiceInputNode.process_utterance(node, VoiceUtterance(True, None, {}), 0)
    node.utterance_pub.publish.assert_not_called()
    node.play_beep.assert_called_once_with("fail", 0)
