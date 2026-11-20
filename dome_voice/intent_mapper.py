#!/usr/bin/env python3
# intent_mapper — maps Vosk transcripts to structured intent dicts.
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-20
# Updated: 2026-11-20
# Open Source Under MIT license

PHRASE_INTENTS = (
    (("stop",), "stop"),
    (("right",), "turn_right"),
    (("left",), "turn_left"),
    (("explore",), "exploration_start"),
    (("describe",), "describe_scene"),
    (("objects",), "list_objects"),
    (("status",), "get_status"),
    (("help",), "get_help"),
)


def command_words() -> tuple[str, ...]:
    """Every phrase in the command table, in table order: the Vosk grammar."""
    return tuple(phrase for phrases, _ in PHRASE_INTENTS for phrase in phrases)


def contains_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


class IntentMapper:
    """Keyword matcher from transcript text to normalized voice intents."""

    SOURCE = "voice"

    def map_intent(self, text: str) -> dict | None:
        normalized_text = text.lower().strip()
        if not normalized_text or normalized_text == "[unk]":
            return None

        for phrases, name in PHRASE_INTENTS:
            if contains_phrase(normalized_text, phrases):
                return {"name": name, "source": self.SOURCE, "slots": {}}

        return None


DEFAULT_MAPPER = IntentMapper()


def map_intent(text: str) -> dict | None:
    """Compatibility wrapper for existing call sites and tests."""
    return DEFAULT_MAPPER.map_intent(text)
