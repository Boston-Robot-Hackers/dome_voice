#!/usr/bin/env python3
"""
llm_turn.py — ROS-free pieces of the F12 spike's VM node: audio decoding and the chat.

Author: Pito Salas and Claude Code
Open Source Under MIT license

`pcm_to_float` turns a /voice/utterance payload into what faster-whisper
takes. `Conversation` keeps the chat history and asks Claude for a short
spoken reply. The client is passed in, so tests use a fake and this module
needs neither `anthropic` nor ROS.

Each assistant turn is appended as the full `response.content`, not just its
text, because the API expects thinking blocks to be passed back unchanged.
"""

from typing import Any

import numpy as np

RATE = 16000  # Hz, the robot mic rate
MODEL = "claude-haiku-5-5"  # fastest; replies are one or two sentences
MAX_TOKENS = 4000
SYSTEM_PROMPT = (
    "You are the voice of a small indoor robot named Robbie. What you write is "
    "spoken aloud by a text-to-speech engine, so answer in one or two short, "
    "plain sentences. No lists, markdown, emoji, or symbols. The user's words "
    "come from speech recognition and may contain errors; if a request is "
    "unclear, ask a brief question."
)
REFUSAL_REPLY = "I can't help with that one."


def pcm_to_float(payload: bytes) -> np.ndarray:
    """int16 little-endian mono PCM → float32 in [-1, 1), as faster-whisper takes."""
    if len(payload) % 2:
        raise ValueError(f"PCM payload has an odd byte count: {len(payload)}")
    return np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0


def reply_text(response: Any) -> str:
    texts = [block.text for block in response.content if block.type == "text"]
    return " ".join(text.strip() for text in texts).strip()


class Conversation:
    """The chat with Claude: one user message in, one spoken reply out."""

    def __init__(self, client: Any, model: str = MODEL):
        self.client = client
        self.model = model
        self.messages: list[dict[str, Any]] = []

    def ask(self, user_text: str) -> str:
        """Send `user_text` with the history; return the reply to speak.

        The history only grows when a turn succeeds, so a failed or refused
        request leaves it alternating user/assistant. API errors propagate.
        """
        user_message = {"role": "user", "content": user_text}
        response = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low"},
            messages=[*self.messages, user_message],
        )
        if response.stop_reason == "refusal":
            return REFUSAL_REPLY
        text = reply_text(response)
        if not text:
            raise RuntimeError(
                f"Claude returned no text (stop_reason={response.stop_reason})"
            )
        self.messages += [
            user_message,
            {"role": "assistant", "content": response.content},
        ]
        return text
