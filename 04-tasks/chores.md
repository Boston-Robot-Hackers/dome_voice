# Chores

Bug fixes and refactors with no spec or behaviour change. Each bug fix gets a regression test.

- [ ] Fix I01's last three failures: `test_voice_input_node.py` builds the node with `__new__`, so `voice_config` is never set. Fix in the tests, not the node.
- [ ] `voice_input` exits silently when `arecord` ends: `next_turn` returns "no wake" and the loop breaks. Log an error and exit non-zero (spec: Listening). Regression test with a stream that hits EOF.
- [ ] F01 looks already built: "objects" is in `PHRASE_INTENTS` and the grammar. Check its tests, then close F01 and TF01.
- [ ] Style guide: drop leading underscores (`_ensure_ready`, `_suppress_fd2`, `_restore_fd2`, `_terminate_process`, `_resolve_oww_model`, `_arecord_process`).
- [x] Style guide: `audio_feedback.py` has a broad `except`, prints to stderr, and imports inside the function. Raise or log instead. Also, `subprocess.run(check=False, capture_output=True)` hides aplay failures (busy or missing device): raise on a non-zero exit. Regression test with a failing aplay.
- [ ] `beep()` limits the tone to 7% of full scale (`amplitude = 0.07 * volume`), about −23 dBFS, so beeps are barely audible even at mixer 0 dB. Raise the limit and let `volume` in `voice.yaml` set loudness.
- [ ] `provision_dome`: set the Seeed HAT mixer (`PCM` 127, `HP DAC` / `Line DAC` / `HPCOM DAC` 118, `PGA` 60, `ADC HPF Cut-off` 0.0045xFs on both channels) and run `alsactl store`. With the ADC HPF disabled, the input's DC offset swings rail to rail for seconds after opening and saturates the ADC. The defaults (−20 dB PCM, −23.5 dB DAC) made output almost silent (found 2026-11-19).
- [x] `read_mono_chunk` subtracts each chunk's own mean, so the signal jumps at every 80 ms chunk boundary and the highpass passes the jump through as a click (`mic_diag.wav`: median boundary jump 1078 vs 53 mid-chunk). Drop it; the live highpass already removes DC. Regression test: a continuous signal split into chunks has no boundary jump (I02).
- [x] I02: speech reaches Vosk at −30 to −40 dBFS, too quiet for the small model, and the PGA can't go above 30 dB without muting. Add `stt_gain_db` (robot: 10), applied to Vosk's input only. Replay of 7 recorded turns: 3/7 → 7/7 with the beep skip. Regression test.
- [x] I02: the wake beep is in the first ~0.4 s of the command capture, sets `command_started`, and hurts recognition. Skip the beep's duration (`beep_wake_duration`) plus start-up latency before capture. Regression test.
- [ ] Split `runtime.py` (755 lines): config models, audio input, and the turn loop into separate modules. Keep the public API in `__init__.py`.
- [x] `speech_output`: replace the per-sample `struct` gain loop with numpy. Done as part of the streaming change below.
- [ ] `__pycache__/*.pyc` files are tracked in git, so every test run dirties the tree. `git rm -r --cached` them; `.gitignore` (or the global one) should cover `__pycache__/`.
- [x] `speech_output`'s announcement callback caught bare `Exception`. Narrowed to the errors `speak_text` raises (RuntimeError, ValueError, OSError, CalledProcessError).
- [x] `ruff format` rewrote Python excerpts in `01-literate/*.md` and changed one's meaning. Added `ruff.toml` excluding `01-literate/`.
- [ ] `beep()` now raises on aplay failure, and `voice_input` calls it with no handler, so a busy device (an announcement on `plughw:0,0` at the same moment) stops the voice loop. Catch `RuntimeError` at the node's beep calls (one helper for all four) and log it. Regression test.
- [x] `speech_output` streams Piper's raw output into `aplay` instead of rendering a whole WAV first, so speech starts after the first sentence. Measured on a two-sentence reply: first audio at 1.3 s, where the WAV path took about 2.2 s. Most of what's left is Piper loading its model on each reply. Tests use real subprocesses: scaling, odd-byte carry, and failure of either process (found in the F12 spike, 2026-11-20).
- [ ] `speech_output`: keep one Piper process running instead of starting one per announcement, saving about 1 s of model load each time. This needs a way to tell where one utterance's raw audio ends.
- [ ] `beep()` still reads `SPEECH_ALSA_DEVICE`, which nothing sets any more: F13 moved speech's device into `voice.yaml` and removed it from the launch. So beeps play on ALSA's default device. Give `beep()` its device from the YAML (TF08 plans `playback_card`).
- [ ] Fix `.githooks/pre-commit` so it stamps Version/Updated in files whose header is a docstring, not only `# Author:` comment headers; it silently skips those today.
- [ ] Stop tracking `__pycache__/*.pyc` in git (`git rm --cached`, add to `.gitignore`); every test run shows them as modified.
