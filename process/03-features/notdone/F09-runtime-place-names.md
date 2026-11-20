# F09 — "Go to <place>" with names from the map

**Date Created:** 2026-11-19
**Priority**: Medium
**Done:** no
**Tasks File Created:** yes
**Tests Written:** no
**Test Passing:** no

## Description

dome_mission already accepts `navigation_go` with `slots.label`, and dome_semantic already knows object labels. **Voice can't say any of them** because the grammar is fixed.

The usual answer is open-vocabulary speech-to-text plus an LLM. But **Vosk accepts a new grammar every time it starts a recognizer**, so the names can be added at runtime. That keeps Vosk's accuracy on a short list, which matters in a noisy room, and needs no new model.

### Scope

- **A name source**: `VoiceRuntime` takes a callable returning the current list of names. The core stays ROS-free.
- **`voice_input` supplies it** from dome_semantic's targets topic (the one `nav_intent_check.py` publishes). The exact topic and message are confirmed in T01.
- **Grammar = command words + "go to" + each name.** Multi-word names ("red chair") are full phrases in the grammar.
- **"go to <name>"** maps to `navigation_go` with `slots.label = <name>`.
- An empty name list behaves exactly as today.

### Out of scope

- Free-form speech and LLM intent ("take me somewhere I can sit"). Listed in the spec's Direction section.
- Naming rooms by voice.

## How to Demo
**Setup**: dome_semantic publishing a target labelled "chair"; dome_mission running.

**Steps**:
1. Say "hey marvin go to chair".

**Expected output**: `{"name": "navigation_go", "slots": {"label": "chair"}}` on `/intent`, and the robot drives to it.
