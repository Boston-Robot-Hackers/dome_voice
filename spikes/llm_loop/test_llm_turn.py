#!/usr/bin/env python3
"""
test_llm_turn.py — tests for the F12 spike's audio decoding and Claude conversation.

Author: Pito Salas and Claude Code
Open Source Under MIT license

Run with `python3 -m pytest spikes/llm_loop/`.
"""

from types import SimpleNamespace

import numpy as np
import pytest
from llm_turn import REFUSAL_REPLY, Conversation, pcm_to_float


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def fake_client(*responses):
    messages = FakeMessages(responses)
    return SimpleNamespace(messages=messages), messages


def response(text: str, stop_reason: str = "end_turn"):
    blocks = [SimpleNamespace(type="thinking", thinking="")]
    if text:
        blocks.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(content=blocks, stop_reason=stop_reason)


def test_pcm_to_float_scales_int16():
    payload = np.array([0, 16384, -32768], dtype="<i2").tobytes()
    assert pcm_to_float(payload).tolist() == [0.0, 0.5, -1.0]


def test_pcm_to_float_rejects_odd_length():
    with pytest.raises(ValueError):
        pcm_to_float(b"\x00\x01\x02")


def test_ask_returns_text_and_keeps_full_content_in_history():
    client, messages = fake_client(response(" Hello there. "))
    conversation = Conversation(client)
    assert conversation.ask("hi") == "Hello there."
    assert conversation.messages[0] == {"role": "user", "content": "hi"}
    assert conversation.messages[1]["content"][0].type == "thinking"
    assert messages.calls[0]["model"] == "claude-haiku-5-5"
    assert messages.calls[0]["output_config"] == {"effort": "low"}


def test_second_turn_sends_history():
    client, messages = fake_client(response("One."), response("Two."))
    conversation = Conversation(client)
    conversation.ask("first")
    conversation.ask("second")
    roles = [message["role"] for message in messages.calls[1]["messages"]]
    assert roles == ["user", "assistant", "user"]


def test_failed_request_leaves_history_unchanged():
    client, _ = fake_client(RuntimeError("boom"), response("Ok."))
    conversation = Conversation(client)
    with pytest.raises(RuntimeError):
        conversation.ask("first")
    assert conversation.messages == []
    conversation.ask("again")
    assert [m["role"] for m in conversation.messages] == ["user", "assistant"]


def test_refusal_gives_fixed_reply_and_no_history():
    client, _ = fake_client(response("", stop_reason="refusal"))
    conversation = Conversation(client)
    assert conversation.ask("bad") == REFUSAL_REPLY
    assert conversation.messages == []


def test_reply_with_no_text_raises():
    client, _ = fake_client(response("", stop_reason="max_tokens"))
    with pytest.raises(RuntimeError, match="max_tokens"):
        Conversation(client).ask("hi")
