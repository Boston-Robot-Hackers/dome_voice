# TF03 One command table, matching the `/intent` contract (Feature F03)

Ordered so you can **try it on the robot after T01**; the rest hardens it.

## T01 — Slice: rename `explore` to `exploration_start`
**Status**: done (2026-11-19)
**Description**: Change the intent name in `PHRASE_INTENTS`. One line; nothing else moves.
**Test**: mapper test for "explore" → `exploration_start`.

## T02 — You try it
**Status**: not done
**Description**: `bl dome2 robot.launch.py` (with dome_mission), say "hey marvin explore", watch `ros2 topic echo /intent`. Expected: `exploration_start`, and the robot starts exploring. Record the result here. *Manual: robot.*

## T03 — Derive the grammar from the command table
**Status**: done (2026-11-19); awaiting your try
**Description**: Add `command_words()` to `intent_mapper.py`; the runtime uses it. Remove `DEFAULT_GRAMMAR`, `StreamSettings.grammar`, the `--grammar` flag, and `grammar` from `voice.yaml`. A YAML that still names `grammar` raises, saying it is now derived.
**Test**: the recognizer's grammar equals `command_words()`; an old YAML with `grammar` raises with that message.
**You try it**: `python3 -m dome_voice.runtime --config config/voice.yaml` prints the derived grammar; `--trials 5` still recognizes every command.

## T04 — Whole-word matching
**Status**: not done
**Description**: Match phrases as whole words in `IntentMapper.map_intent`.
**Test**: "left" matches "turn left"; "leftover" does not.

## T05 — Stop decision
**Status**: not done
**Description**: Record the user's choice on what "stop" emits (F03, "Decision needed"). If (a), note the dome_mission companion change. *No test: a decision.*

## T06 — Contract test
**Status**: not done
**Description**: Assert every emitted intent name is in a fixed list of consumer-handled names copied from dome_control and dome_mission (comment names the source).
**Test**: is the test.

## T07 — Docs and full test run
**Status**: not done
**Description**: Update `process/02-doc/notes.md` ("Grammar constraint"), the `runtime` and `intent_mapper` literate docs. Run `python3 -m pytest test/`.
