# I01 Five test-suite regressions found during 2026-08-05 checkpoint

* **What the symptom is**: `python3 -m pytest test/` reports 5 failures,
  37 passed — `02-doc/current.md` claims "42 passing tests (all green)",
  which is stale. Found while running the checkpoint's test step; no
  source changes were made in this repo this session (only `.claude/` and
  `CLAUDE.md`), so these are pre-existing, previously-undetected
  regressions, not something introduced today.
* **What tests have already been done**: ran the full `test/` suite with
  `dome_control` on `PYTHONPATH` (needed for `test_speech_output_node.py`'s
  `dome_control.announcement_contract` import — this repo's tests aren't
  normally run standalone without the ROS workspace sourced or that repo
  on the path).
* **Failures**:
  1. `test_voice_input_node.py::test_process_transcript_known_intent`,
     `test_process_transcript_unknown_intent`,
     `test_process_turn_empty_plays_beep`: all three
     `AttributeError: 'VoiceInputNode' object has no attribute
     'voice_config'` — `_speak_result`/beep path reads `self.voice_config`
     but the node under test never has it set.
  2. `test_voice_runtime.py::test_voice_runtime_next_turn_uses_fake_models`:
     `assert turn.text == "stop"` fails, actual value `"alexa stop"` — the
     wake word doesn't appear to be stripped before the intent-mapper
     step in this test's fake-model path.
  3. `test_voice_runtime_config.py::test_load_voice_runtime_config_env_path`:
     `cfg.source_path` resolves to the repo's real
     `config/voice_config.yaml` instead of the monkeypatched
     `CONTROL_VOICE_TUNE_CONFIG` temp path — the env var override isn't
     taking effect.
* **What the latest theory is**: not investigated beyond reproducing —
  these look like three independent bugs (missing attribute init, wake-word
  stripping order, env var precedence), not one root cause. Needs
  triage/fix in a future session; out of scope for this checkpoint (no
  source changes were otherwise needed here).
