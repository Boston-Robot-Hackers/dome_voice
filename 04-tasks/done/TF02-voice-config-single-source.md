# TF02 Voice config: defaults once in code, YAML layered on top (F02)

**Date Created:** 2026-11-19

Each step has a test where feasible.

## TF02.0 — Seal the tests off from the shell

**Status**: done (2026-11-19)

**Description**: Add an autouse fixture in `test/conftest.py` that unsets `DOME_VOICE_CONFIG`, `CONTROL_VOICE_TUNE_CONFIG` and `VOICE_TUNE_CONFIG`.

**Test**: The suite gives the same result with and without `DOME_VOICE_CONFIG` exported. The two env-leak failures in I01 (`test_voice_runtime_next_turn_uses_fake_models`, `test_load_voice_runtime_config_env_path`) pass. Update I01 to say so.

## TF02.1 — Record the robot's current effective config

**Status**: done (2026-11-19)

**Description**: Before changing anything, capture `python3 -m dome_voice.runtime`'s output on the robot as the baseline. Save it as `test/fixtures/robot_config_baseline.json`.

Also record the old `TUNED_VOICE_PARAMETERS` values here, as the starting point for a later `hey_marvin` re-tune:

- `threshold` 0.7, `wake_hits` 3, `wake_word` `alexa`
- everything else in it equals today's defaults

**Test**: none, because this step only records data. TF02.4 uses the file.

**Result:** captured on the robot, minus the two machine-specific paths (`source_path`, `vosk_model_path`). It confirms `wake_word` hey_marvin, `threshold` 0.3 and `wake_hits` 1. With no YAML, the old code gave `alexa`, 0.7 and 3.

## TF02.2 — The pydantic model

**Status**: done (2026-11-19)

**Description**: Replace `VoiceRuntimeConfig` and `config_from_tune_mapping` with a strict pydantic model (`extra="forbid"`), nested as the YAML is: `stream_settings`, `sox_chain`, `beep`, plus the two cards. Keep the flat attribute names the runtime and node read, as properties or by mapping in the loader, so `runtime.py`'s and `voice_input_node.py`'s call sites don't change.

- Defaults: today's effective values, once.
- `highpass`/`lowpass` keep accepting `none` for "off".
- The grammar accepts a list or a comma-separated string. An empty grammar **raises**, instead of silently becoming the default.
- Delete `TUNED_VOICE_PARAMETERS` and the `_as_*` / `_optional_float` / `_as_bool` helpers.

**Test**: Unit tests for: an empty YAML gives the defaults; a partial YAML overrides only its keys; an unknown key raises and names it; `none` cutoffs; the grammar from a string, a list, and empty (raises).

## TF02.3 — The loader and overrides

**Status**: done (2026-11-19)

**Description**: `load_voice_runtime_config(path, overrides)` keeps its signature and source order (path, then the three env vars, then the defaults). With no YAML, `source_path` reads `defaults`. `apply_config_overrides` validates through the model, so a bad CLI value raises too.

**Test**: Existing `test_voice_runtime_config.py` cases, updated. Also: an override with an unknown key raises, and a `None` override is skipped.

## TF02.4 — Write the robot's values into the YAML

**Status**: done (2026-11-19)

**Description**: Put every value the robot runs with into `config/voice_config.yaml` explicitly, with comments, including `threshold: 0.3` and `wake_hits: 1`. Then the file says what the robot does.

**Test**: Loading `config/voice_config.yaml` gives exactly TF02.1's baseline.

## TF02.5 — Declare the dependency, update the docs

**Status**: done (2026-11-19)

**Description**: Add `pydantic` to `package.xml`. Update `02-doc/notes.md`'s "Tuned parameters" section: tune results now go into the YAML. Update the literate `01-runtime.md` at checkpoint, per the process.

**Test**: none, because these are docs and metadata. `colcon build --packages-select dome_voice` passes.

## TF02.6 — Feature test suite and robot check

**Status**: done (2026-11-19)

**Description**: Run the full suite, with and without `DOME_VOICE_CONFIG`. On the robot, compare `python3 -m dome_voice.runtime`'s output with TF02.1's baseline, and run the demo's misspelled-key step.

**Test**: The demo in F02. The remaining I01 failures (the three `VoiceInputNode.__new__` tests) are expected and out of scope.

**Result (robot):** 66 passed and 3 failed (I01's `__new__` tests), the same with and without `DOME_VOICE_CONFIG`. `python3 -m dome_voice.runtime` matches the baseline exactly. A copy of the YAML with `treshold: 0.7` fails with `stream_settings.treshold — Extra inputs are not permitted`. `colcon build` passes.

**Beyond the plan:**

- `VoiceRuntimeConfig` stayed a flat frozen dataclass with no defaults, built by the new `VoiceConfigFile` model. The runtime's and node's call sites, and tests using `dataclasses.replace`, didn't change.
- A named config file that doesn't exist now **raises**, instead of silently running on the defaults.
- `highpass`/`lowpass` are read only from `sox_chain`, no longer also from `stream_settings`. No YAML used the latter.
- `python3-numpy` and `python3-yaml` were declared along with `python3-pydantic`. Neither was declared before.
