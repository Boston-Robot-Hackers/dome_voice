# F02 — Voice config: defaults once in code, YAML layered on top

**Date Created:** 2026-11-19
**Priority**: Medium
**Done:** yes
**Tasks File Created:** yes
**Tests Written:** yes
**Test Passing:** yes

## Description

Make dome_voice load its config **the way the other DOME packages do**: a pydantic model holds every default once, and the YAML is loaded onto it. dome_vision's `AppConfig`, dome_semantic's `WorldTrackerConfig` and dome_control's `SpinSurveyConfig` already work this way.

### The problem today

- **Defaults are written three times**, and the copies disagree: `VoiceRuntimeConfig`'s fields, `config_from_tune_mapping`'s fallbacks, and `TUNED_VOICE_PARAMETERS`.
- **A YAML replaces `TUNED_VOICE_PARAMETERS` entirely**, instead of overriding it. The robot's `voice_config.yaml` sets only `wake_word` and the beeps. So the robot runs at `threshold` 0.3 and `wake_hits` 1, while the "tuned" table says 0.7 and 3.
- **Unknown YAML keys are silently ignored.** A typo such as `treshold: 0.7` does nothing. dome_vision forbids extra keys for exactly this reason.
- **The tests pick up the shell's `DOME_VOICE_CONFIG`.** That causes 2 of I01's 5 failures.

### The rule this feature adopts

| Layer | Holds |
|---|---|
| The pydantic model | every default, once |
| `config/voice_config.yaml` | what differs on this robot, including tuned values |
| CLI flags (`runtime.py --threshold ...`) | a one-run override |

### Scope

- **A strict pydantic model** (`extra="forbid"`) with the YAML's nested shape: `capture_card`, `playback_card`, `stream_settings`, `sox_chain` and `beep`. A misspelled key raises with its name.
- **Delete** `TUNED_VOICE_PARAMETERS`, the fallbacks in `config_from_tune_mapping`, and the `_as_*` coercion helpers that pydantic replaces.
- **Behaviour unchanged on the robot.** `voice_config.yaml` gets the values the robot runs with today, written out explicitly (`threshold: 0.3`, `wake_hits: 1`, and so on). **Re-tuning for `hey_marvin` is out of scope.** The old table's values (0.7, 3) are recorded in the task file as a starting point.
- **`~/tune` results are pasted into the YAML**, not into code. The notes and the literate doc say so.
- **The public API stays**: `load_voice_runtime_config(path, overrides)`, the `VoiceRuntimeConfig` attribute names the runtime and node read, `vosk_model_path` and `to_dict()`.
- **Tests clear `DOME_VOICE_CONFIG`, `CONTROL_VOICE_TUNE_CONFIG` and `VOICE_TUNE_CONFIG`** in a fixture, so the shell can't leak in.
- `pydantic` is declared in `package.xml`.

### Out of scope

- The other three I01 failures (tests that bypass `VoiceInputNode.__init__`).
- `speech_output`'s environment-variable settings. They are configured by the launch file (dome2 F05), not by this YAML.

## How to Demo

**Setup**: robot, `$DOME_VOICE_CONFIG` pointing at `config/voice_config.yaml`.

**Steps**:

1. `python3 -m dome_voice.runtime` before and after the change.
2. Add `treshold: 0.7` under `stream_settings` in a copy of the YAML, then run `python3 -m dome_voice.runtime --config <copy>`.
3. Run the test suite with and without `DOME_VOICE_CONFIG` set.

**Expected output**:

1. The printed config is identical before and after.
2. Step 2 fails with an error naming `treshold`.
3. Step 3 gives the same result both ways, with the two env-leak failures from I01 gone.
