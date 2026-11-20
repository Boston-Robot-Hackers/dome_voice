#!/usr/bin/env python3
# test_llm_turn — tests for the LLM path's audio decoding, tools and conversation
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-20
# Updated: 2026-11-20
# Open Source Under MIT license

from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pytest

from dome_voice.llm_turn import (
    INTENT_TOOLS,
    REFUSAL_REPLY,
    Conversation,
    LlmTurn,
    intent_tools,
    load_persona,
    pcm_to_float,
)

PERSONA = "You are Robbie, a test robot."
NOW = datetime(2026, 11, 20, 14, 5)


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


def conversation_with(*responses):
    messages = FakeMessages(responses)
    return Conversation(SimpleNamespace(messages=messages), PERSONA), messages


def response(text: str = "", tool_calls=(), stop_reason: str = "end_turn"):
    blocks = [SimpleNamespace(type="thinking", thinking="")]
    if text:
        blocks.append(SimpleNamespace(type="text", text=text))
    for i, (name, tool_input) in enumerate(tool_calls):
        blocks.append(
            SimpleNamespace(
                type="tool_use", id=f"toolu_{i}", name=name, input=tool_input
            )
        )
    return SimpleNamespace(content=blocks, stop_reason=stop_reason)


def test_pcm_to_float_scales_int16():
    payload = np.array([0, 16384, -32768], dtype="<i2").tobytes()
    assert pcm_to_float(payload).tolist() == [0.0, 0.5, -1.0]


def test_pcm_to_float_rejects_odd_length():
    with pytest.raises(ValueError):
        pcm_to_float(b"\x00\x01\x02")


def test_load_persona_strips_text(tmp_path):
    path = tmp_path / "persona.md"
    path.write_text("\n  You are Robbie.  \n")
    assert load_persona(path) == "You are Robbie."


def test_load_persona_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_persona(tmp_path / "nope.md")


def test_load_persona_empty_file_raises(tmp_path):
    path = tmp_path / "persona.md"
    path.write_text("  \n")
    with pytest.raises(ValueError, match="empty"):
        load_persona(path)


def test_intent_tools_cover_every_intent_strictly():
    tools = {tool["name"]: tool for tool in intent_tools()}
    assert set(tools) == set(INTENT_TOOLS)
    assert all(tool["strict"] for tool in tools.values())
    assert tools["navigation_go"]["input_schema"]["required"] == ["label"]
    assert tools["stop"]["input_schema"]["properties"] == {}


def test_text_reply_has_no_intents_and_sends_persona_tools_and_time():
    conversation, messages = conversation_with(response(" Hello there. "))
    assert conversation.ask("hi", NOW) == LlmTurn("Hello there.", [])
    call = messages.calls[0]
    assert call["system"].startswith(PERSONA)
    assert len(call["tools"]) == len(INTENT_TOOLS)
    assert call["output_config"] == {"effort": "low"}
    assert call["messages"][-1]["content"] == [
        {"type": "text", "text": "[Friday 14:05] hi"}
    ]


def test_tool_call_becomes_intent():
    conversation, _ = conversation_with(
        response("Heading there.", [("navigation_go", {"label": "kitchen"})])
    )
    turn = conversation.ask("go to the kitchen", NOW)
    assert turn.reply == "Heading there."
    assert turn.intents == [
        {"name": "navigation_go", "source": "llm", "slots": {"label": "kitchen"}}
    ]


def test_tool_call_alone_gives_empty_reply():
    conversation, _ = conversation_with(response(tool_calls=[("describe_scene", {})]))
    turn = conversation.ask("what do you see", NOW)
    assert turn == LlmTurn(
        "", [{"name": "describe_scene", "source": "llm", "slots": {}}]
    )


def test_tool_results_lead_the_next_user_message():
    conversation, messages = conversation_with(
        response(tool_calls=[("turn_left", {}), ("exploration_start", {})]),
        response("Sure."),
    )
    conversation.ask("turn left and explore", NOW)
    conversation.ask("thanks", NOW)
    roles = [message["role"] for message in messages.calls[1]["messages"]]
    assert roles == ["user", "assistant", "user"]
    content = messages.calls[1]["messages"][-1]["content"]
    assert [block["type"] for block in content] == [
        "tool_result",
        "tool_result",
        "text",
    ]
    assert [block["tool_use_id"] for block in content[:2]] == ["toolu_0", "toolu_1"]
    assert conversation.pending_results == []


def test_failed_request_keeps_history_and_pending_results():
    conversation, messages = conversation_with(
        response(tool_calls=[("stop", {})]), RuntimeError("boom"), response("Ok.")
    )
    conversation.ask("stop", NOW)
    with pytest.raises(RuntimeError):
        conversation.ask("next", NOW)
    assert len(conversation.messages) == 2
    conversation.ask("again", NOW)
    assert messages.calls[2]["messages"][-1]["content"][0]["type"] == "tool_result"


def test_refusal_gives_fixed_reply_and_no_history():
    conversation, _ = conversation_with(response(stop_reason="refusal"))
    assert conversation.ask("bad", NOW) == LlmTurn(REFUSAL_REPLY, [])
    assert conversation.messages == []


def test_no_text_and_no_tool_raises():
    conversation, _ = conversation_with(response(stop_reason="max_tokens"))
    with pytest.raises(RuntimeError, match="max_tokens"):
        conversation.ask("hi", NOW)
