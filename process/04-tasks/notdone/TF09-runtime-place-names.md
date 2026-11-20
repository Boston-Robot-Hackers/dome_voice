# TF09 "Go to <place>" with names from the map (Feature F09)

**Date Created:** 2026-11-19

Ordered so you can **say "go to chair" after TF09.1, with names typed into the YAML**, before wiring up dome_semantic.

## TF09.0 — Slice: names from config
**Status**: not done
**Description**: Add `place_names` (list) to config. The grammar is `command_words()` (F03) plus `"go to <name>"` for each. `IntentMapper` maps "go to <name>" to `navigation_go` with `slots.label`. Names with words outside the Vosk model's vocabulary are logged and skipped.
**Test**: the grammar contains each phrase; "go to red chair" → label "red chair"; "go to" alone and unknown names → no intent; empty list gives today's grammar.

## TF09.1 — You try it
**Status**: not done
**Description**: Put `place_names: [chair]` in `voice.yaml`; publish a target labelled "chair" with `dome_mission/tools/nav_intent_check.py`'s setup. Say "hey marvin go to chair". Expected: `navigation_go` with label "chair" on `/intent`; the robot drives there. Record results here. *Manual: robot.*

## TF09.2 — Confirm the live name source
**Status**: not done
**Description**: Confirm the topic and message for target labels (`/semantic/targets`, `SemanticTargetArray` is the candidate) and whether room names exist. Record in F09. *No test: investigation.*

## TF09.3 — Names from dome_semantic
**Status**: not done
**Description**: `VoiceRuntime` takes a names callable (core stays ROS-free); `voice_input` fills it from the topic (same background executor as F04). Config names, if any, are added to the live ones.
**Test**: the callback turns a message into the expected list; the runtime rebuilds the grammar per turn from the callable.
**You try it**: remove `place_names`; let dome_semantic see a chair; say "go to chair".

## TF09.4 — Docs and full test run
**Status**: not done
**Description**: Spec, literate docs, notes. Run `python3 -m pytest test/`.
