# F03 — One command table, matching the `/intent` contract

**Date Created:** 2026-11-19
**Priority**: High
**Done:** no
**Tasks File Created:** yes
**Tests Written:** no
**Test Passing:** no

## Description

Make the command table in `intent_mapper.py` **the only place voice commands are written**, and make every intent it emits one that some package actually handles.

### The problem today

- **"explore" does nothing.** Voice emits `explore`. dome_mission only accepts `exploration_start`, and dome_control's `behavior_manager` logs `Unhandled intent: explore`.
- **The command list is written four times**: `PHRASE_INTENTS`, `DEFAULT_GRAMMAR`, `config/voice.yaml`'s `grammar`, and `behavior_manager`'s help text (which leaves out "objects").
- **Matching is by substring.** "don't stop" maps to `stop`; the first entry in the table wins when two words appear.

### Scope

- **Derive the grammar** from `PHRASE_INTENTS`. Remove `DEFAULT_GRAMMAR` and the `grammar` key from `voice.yaml`. *Persisted-format change:* a YAML that still names `grammar` raises with a message saying it is now derived.
- **Rename emitted intents** to the consumers' contract. `explore` → `exploration_start`. The others already match dome_control.
- **Whole-word matching.** The phrase must appear as whole words in the transcript.
- **Expose the command words** (a function returning them) so `behavior_manager` can build its help text from it.

### Decision needed

**What should "stop" emit?** Today `stop` reaches dome_control's motion behaviour only; it does not end an exploration or cancel a navigation in dome_mission. Options:

- **(a)** dome_voice emits `stop`, and dome_mission also treats `stop` as `EXPLORE_STOP` + `CANCEL`. One meaning of stop, owned by the consumers. *Recommended.*
- **(b)** dome_voice emits several intents for one "stop".

### Out of scope

- The dome_mission and dome_control changes (option (a), help text from the table). They are **companion features in those packages**; this feature only provides what they need.
- Runtime place/object names (F09).

## How to Demo
**Setup**: voice stack and dome_mission running.

**Steps**:
1. Say "hey marvin explore".
2. `ros2 topic echo /intent`.

**Expected output**: `{"name": "exploration_start", ...}` is published and dome_mission starts exploring. `python3 -m dome_voice.runtime` (no trials) prints a grammar equal to the command table's words.
