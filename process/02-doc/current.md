# dome_voice — Current Session Handoff

## Open

### Pick up here (2026-11-22): moving to the Pi, F15 to test there

**F15 (speech starts sooner) is coded, committed and unit-tested, but has
not run on the robot.** Written on the Mac; the session moves to the Pi now.

- **What changed:** `speech_output` keeps one `piper --json-input` process
  running (`dome_voice/piper_server.py`), speaks a sentence at a time with
  the next synthesised while one plays, and caches recent sentences. See
  TF15.1 and literate chapters 04 and 07.
- **Why:** TF15.0 on the Pi: ~0.6 s of every announcement was Piper loading
  its model, ~0.9 s synthesis; dome_pad press → `/announcement` is ~10 ms.
- **On the Pi, first:**
  1. `cd ~/ros2_ws/src/dome_voice && git pull`, then
     `cd ~/ros2_ws && colcon build --packages-select dome_voice`.
  2. Run the unit tests with real ROS:
     `cd ~/ros2_ws/src/dome_voice && /usr/bin/python3 -m pytest test/test_piper_server.py test/test_speech_output_node.py`
     (they passed on the Mac with ROS faked; 41 tests).
  3. `bl dome2 robot.launch.py --options "d c vo p"`; on the VM
     `bl dome2 remote.launch.py --options "vo p"`.
  4. **TF15.2:** press dome_pad's Status 5 times; time press → first sound
     (expect ~1.0 s on the first press, ~0.1 s on repeats from the cache;
     it was ~2 s). Send a joke (Joke key) and check it starts after its
     first sentence. Record the numbers in TF15.2.
  5. `ps -o rss=,cmd= -C piper`: Piper's resident memory, now held all
     the time (guessed 100-150 MB, not measured).
- **Watch for:** the EKF's "Failed to meet update rate" errors (30 Hz,
  updates took 40-300 ms on 2026-11-22, with the old speech code). Check
  with `top` whether they line up with Piper synthesising. If so, run
  Piper under `nice` (literate 04, observation 3).
- **Also new:** I03, the LLM giving up on repeated status questions
  (found via dome_pad; dome_pad now sends `get_status` itself).

### Before that (2026-11-20)

- **F14 (LLM command path) is in progress.** Done: TF14.0 (the VM node with intent tools), TF14.1 (the on-robot trial), TF14.2 (`voice_input` on the LLM path) and TF14.7 (`bl dome2 remote.launch.py --options "vi vo"` on the VM).
- **The robot runs `command_path: llm` with `hey_jarvis`.** "hey marvin" and the fixed grammar are off but kept; `command_path: grammar` brings them back.
- **Next: TF14.3**, say "offline" when the VM doesn't answer. **Later, TF14.5:** measure the end of the question to the start of the answer, by stage.
- **`.claude/` is synced from j3** (2026-11-20), and the docs moved into `process/`. Task steps are now `TFNN.N`, so old notes saying "T04" mean `TFNN.3`.

### Next

- **F14:** TF14.3 offline message, TF14.4 train "hey robbie", TF14.5 tests and latency, TF14.6 docs.
- **Then, suggested order:** F03 → F05 → F07 → F11 → F10 → F06 → F09 → F08.

### Paused

- **F05 (record and replay):** TF05.1 is mostly done (16 turns in `~/voice_recordings`; left: once with motors running). Next code task: TF05.3, the replay tool, which should record about 2 s past the turn's end.
- **F03 (one command table):** next is TF03.3, whole-word matching.

### Decisions pending

- **F03:** what "stop" emits (F03's "Decision needed", TF03.4).

### Open issues

- **I02 (voice runtime and mic):** add the saved mixer state to `provision_dome` (a chore); find the source of the mic-level wander; nothing is tested with motors running yet. Close once the mixer is provisioned and the wander is found or ruled out.
- **I01:** 3 `voice_input_node` tests fail because the node under test has no `voice_config`.

### Parked

- **The XVF3800 USB mic array (F08)** would replace the HAT for echo cancellation. Before buying: find the wander's source, and try any USB mic with `mic_diag`.

### Outside this repo

- **dome_control:** `angular_speed: 1.0` in `config/control-config.yaml` is not committed (also set in `~/.dome/config/control.yaml`). It should speak an error when `/describe_scene` has no server.
- **dome2:** `TF05-launch-file-cleanup.md` still describes the old speech environment variables.
- **provision_dome:** `manifest/pip.txt`, `manifest/bashrc` and `scripts/install-optional-deps.sh` are changed and not committed. `~/.bashrc`'s `DOME_PIPER_*` paths changed.

### Chores

- Open ones are in `process/04-tasks/chores.md`.
