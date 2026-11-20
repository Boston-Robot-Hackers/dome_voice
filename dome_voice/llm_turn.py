#!/usr/bin/env python3
# llm_turn — ROS-free core of the LLM path: audio decoding and the chat with Claude
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-20
# Updated: 2026-11-20
# Open Source Under MIT license
"""`Conversation.ask` takes one transcript (or text a program sent) and returns
an `LlmTurn`: the text to speak, possibly empty, and the `/intent` dicts that
Claude chose through tools. The client is passed in, so tests use a fake and
this module needs neither `anthropic` nor ROS.

Design points:
- **One tool per `/intent` that a consumer handles** (dome_control, dome_mission).
  Calling a tool *is* publishing the intent; the node does that.
- **One request per turn.** A tool call is not followed by a second request.
  Its `tool_result` is held and sent at the start of the next user message, so
  the history stays valid (every `tool_use` answered) at no extra latency.
- **The full `response.content` goes into the history**, because the API
  expects thinking blocks to be passed back unchanged.
- **The system prompt is fixed rules + the persona**, and stays the same across
  turns so it can be cached. The time changes every turn, so it goes at the
  start of each user message instead.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

MODEL = "claude-haiku-5-5"  # fastest; replies are one or two sentences
MAX_TOKENS = 4000
SOURCE = "llm"
REFUSAL_REPLY = "I can't help with that one."
TOOL_RESULT_TEXT = "Sent to the robot."
RULES = (
    "What you write is spoken aloud by a text-to-speech engine, so answer in one "
    "or two short, plain sentences. No lists, markdown, emoji, or symbols. The "
    "user's words come from speech recognition and may contain errors; if a "
    "request is unclear, ask a brief question. Each user message starts with the "
    "current time in brackets.\n\n"
    "When the user asks the robot to do something, call the matching tool. You "
    "may say one short sentence as you do. For describe_scene, list_objects and "
    "get_status, say nothing: the robot speaks the answer itself. If no tool "
    "fits a request to act, say so instead of guessing. Questions and chat need "
    "no tool."
)
INTENT_TOOLS = {
    "stop": "Stop the robot's motion right away.",
    "turn_left": "Turn the robot 90 degrees to the left, in place.",
    "turn_right": "Turn the robot 90 degrees to the right, in place.",
    "exploration_start": "Start exploring and mapping the surroundings.",
    "exploration_stop": "Stop exploring.",
    "navigation_go": "Drive to a named place, such as the kitchen.",
    "navigation_cancel": "Cancel the current drive to a place.",
    "describe_scene": "Describe what the robot's camera sees right now.",
    "list_objects": "List the objects the robot has seen.",
    "get_status": "Report the robot's status.",
}
TOOL_SLOTS = {
    "navigation_go": {"label": {"type": "string", "description": "The place name."}},
}


@dataclass(frozen=True)
class LlmTurn:
    reply: str  # text to speak; empty when an intent's consumer does the talking
    intents: list[dict[str, Any]]


def pcm_to_float(payload: bytes) -> np.ndarray:
    """int16 little-endian mono PCM → float32 in [-1, 1), as faster-whisper takes."""
    if len(payload) % 2:
        raise ValueError(f"PCM payload has an odd byte count: {len(payload)}")
    return np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0


def load_persona(path: Path) -> str:
    persona = path.read_text().strip()
    if not persona:
        raise ValueError(f"Persona file is empty: {path}")
    return persona


def intent_tools() -> list[dict[str, Any]]:
    """The tool definitions: one per intent, with its slots as strict inputs."""
    tools = []
    for name, description in INTENT_TOOLS.items():
        slots = TOOL_SLOTS.get(name, {})
        tools.append(
            {
                "name": name,
                "description": description,
                "strict": True,
                "input_schema": {
                    "type": "object",
                    "properties": slots,
                    "required": list(slots),
                    "additionalProperties": False,
                },
            }
        )
    return tools


def reply_text(response: Any) -> str:
    texts = [block.text for block in response.content if block.type == "text"]
    return " ".join(text.strip() for text in texts).strip()


class Conversation:
    """The chat with Claude: one user message in, an `LlmTurn` out."""

    def __init__(self, client: Any, persona: str, model: str = MODEL):
        self.client = client
        self.model = model
        self.system = f"{persona}\n\n{RULES}"
        self.tools = intent_tools()
        self.messages: list[dict[str, Any]] = []
        self.pending_results: list[dict[str, Any]] = []

    def ask(self, user_text: str, now: datetime) -> LlmTurn:
        """Send `user_text` with the history; return what to speak and publish.

        The history only grows when a turn succeeds, so a failed or refused
        request leaves it as it was. API errors propagate.
        """
        stamped = f"[{now:%A %H:%M}] {user_text}"
        content = [*self.pending_results, {"type": "text", "text": stamped}]
        user_message = {"role": "user", "content": content}
        response = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=self.system,
            tools=self.tools,
            output_config={"effort": "low"},
            messages=[*self.messages, user_message],
        )
        if response.stop_reason == "refusal":
            return LlmTurn(REFUSAL_REPLY, [])
        calls = [block for block in response.content if block.type == "tool_use"]
        turn = LlmTurn(reply_text(response), [self.intent(call) for call in calls])
        if not turn.reply and not turn.intents:
            raise RuntimeError(
                f"Claude returned no text and no tool call "
                f"(stop_reason={response.stop_reason})"
            )
        self.messages += [
            user_message,
            {"role": "assistant", "content": response.content},
        ]
        self.pending_results = [
            {"type": "tool_result", "tool_use_id": call.id, "content": TOOL_RESULT_TEXT}
            for call in calls
        ]
        return turn

    def intent(self, call: Any) -> dict[str, Any]:
        return {"name": call.name, "source": SOURCE, "slots": dict(call.input)}
