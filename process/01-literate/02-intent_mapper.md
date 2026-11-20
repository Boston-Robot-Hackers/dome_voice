---
version: "2.0"
generated: "2026-11-19"
---

# 02 — `intent_mapper.py`: From Words to Intents

## Introduction

The recogniser hands over a string such as `"turn right"` or `"[unk]"`. The rest of the robot wants something structured: *which action, from where, with what arguments*.

`intent_mapper.py` is that translation, in about 40 lines. It has no ROS, no audio and no state, which makes it the easiest module in the package to test.

## The output shape

Every recognised command becomes the same small dict:

```python
{"name": "turn_right", "source": "voice", "slots": {}}
```

- **`name`** is the action, in the stack-wide intent vocabulary that `dome_control` understands.
- **`source`** is always `"voice"`. Consumers can tell spoken commands apart from intents sent by other front ends.
- **`slots`** is empty today. It is the place for arguments such as "turn right *ninety degrees*", if the grammar ever grows them.

## The phrase table

```python
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
```

Each row pairs a tuple of trigger phrases with an intent name. Every tuple has one word today, but the shape allows synonyms: `(("stop", "halt"), "stop")`.

**The table is a tuple of tuples, scanned in order, not a dict.** Order matters, because the first match wins.

## Matching

```python
def map_intent(self, text: str) -> dict | None:
    normalized_text = text.lower().strip()
    if not normalized_text or normalized_text == "[unk]":
        return None
    for phrases, name in PHRASE_INTENTS:
        if contains_phrase(normalized_text, phrases):
            return {"name": name, "source": self.SOURCE, "slots": {}}
    return None
```

- **Empty and `[unk]` mean "no intent"**, and the node plays the failure beep.
- **Matching is substring containment** (`phrase in text`), not whole-word. That's acceptable only because Vosk's grammar limits the input to the table's own words, so "stop" can never arrive inside "stopwatch".
- **The first row wins.** If a transcript had several words, say "stop left", it would map to `stop`. Putting `stop` first is a safe ordering for a robot.

## The grammar comes from this table

```python
def command_words() -> tuple[str, ...]:
    return tuple(phrase for phrases, _ in PHRASE_INTENTS for phrase in phrases)
```

**The Vosk grammar is derived from `PHRASE_INTENTS`** (F03). `VoiceRuntimeConfig.grammar` returns `command_words()`, so there is no second list to keep in step.

That matters because the two failure modes were silent:

- A word in the grammar but not in the table would be **recognised, then rejected**, with a failure beep.
- A word in the table but not in the grammar could **never be heard at all**, because Vosk outputs `[unk]` instead.

Adding a voice command is now one new row here.

## The module-level wrapper

```python
DEFAULT_MAPPER = IntentMapper()


def map_intent(text: str) -> dict | None:
    return DEFAULT_MAPPER.map_intent(text)
```

A free function kept for older call sites and tests, such as `testvoice.py`. `IntentMapper` has no state, so sharing one instance is safe.

## Observations

1. **Substring matching depends on the grammar.** If the grammar is ever loosened, or free transcription is used, "stop" would match "stopping" and "unstoppable". Matching on word boundaries would make the mapper safe on its own.
2. **The class adds little.** It holds a constant and one method. It earns its place only if per-instance tables, say per language, are coming.
