# dome_voice — Current Session Handoff

## Open

### Pick up here (2026-11-20)

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
