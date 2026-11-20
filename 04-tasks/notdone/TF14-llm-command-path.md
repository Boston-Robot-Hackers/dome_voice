# TF14 LLM command path, next to the fixed grammar, for Feature F14

The order follows *try it early*: T01 gives a working slice on the existing spike robot script, and T02 is you trying it on the robot. The hardening comes after that.

Run the tests with `python3 -m pytest /home/pitosalas/ros2_ws/src/dome_voice/test/`.

## T01 — Claude emits intents through tools (VM side)
**Status**: done (2026-11-20: on the VM, text in gave a joke, `exploration_start` and `describe_scene`)
**Description**: Move the spike's `llm_turn.py` and `vm_llm_node.py` into the package, as `dome_voice/llm_turn.py` (ROS-free) and `dome_voice/llm_node.py`.

- **Tools:** one per intent in F14's list. `navigation_go` takes a `label`.
- **One request per turn:** `Conversation.ask` returns the reply text and any intents.
- **Tool results go into the history** at the start of the next user message, so a tool call costs no second request.
- **The system prompt** is the persona read from `config/llm_persona.md` (a placeholder for now, set by the `persona` parameter since T08), then the fixed rules in code. The time starts each user message instead, so the system prompt can be cached.
- **Text in:** the node also subscribes to `/voice/llm_text` and passes each string to `Conversation.ask` as if it were a transcript.
- **The node** publishes each intent on `/intent` (source `llm`), and always publishes one `/voice/llm_reply`, even an empty one.
- **On the VM**, it first ran from the repo root as `python3 -m dome_voice.llm_node`; T08 replaced that with a launch. Importing the package pulls in `runtime.py`, which needs `numpy`, `pyyaml` and `pydantic`. openWakeWord and Vosk are imported only when used.

**Test**: unit tests with a fake client:
- a tool call becomes the right intent dict;
- text-only replies give no intent;
- the history stays valid after a tool call;
- a refusal still gets the fixed reply;
- the persona is in the system prompt, and the time starts the user message;
- a missing persona file raises.

Manual check: `ros2 topic pub --once /voice/llm_text std_msgs/String "data: 'tell me a robot joke'"` gets a spoken joke.

## T02 — Try it on the robot
**Status**: done for the voice side (2026-11-20). Downstream retests are open; see below.
**Description**: Run the new VM node with the spike's `robot_mic_pub.py` (wake word `hey_jarvis`), plus dome_control and dome_mission. Try "go explore", "what do you see?", "turn left", "go to the kitchen", a joke, a general question, and "stop". Also send "give a full update on the robot status" on `/voice/llm_text`.

**Test**: manual. For each request, record the transcript, the intent published (`ros2 topic echo /intent`), and what the robot did.

### Results (2026-11-20)

**Every request came out as the right intent**, in 0.6–1.4 s of LLM time. Every failure was downstream, or was the speaker clash F04 fixes.

| Request | Heard / intent | Result | Cause |
|---|---|---|---|
| turn left | `turn_left` | turned | |
| turn right | `turn_right` | didn't turn | dome_control: `angular_speed` 1.5 was outside `angular_min` -1.0 |
| what can you do | chat | correct list | |
| move forward | no tool | explained what it can do | no forward intent exists |
| describe | `describe_scene` | silent | `/describe_scene` had no server: dome_semantic not running |
| status | `get_status` | spoke | thin: speeds only |
| explore | `exploration_start` | nothing | dome_mission not running |
| go to the kitchen | `navigation_go` (label `kitchen`) | nothing | dome_mission not running; "kitchen" isn't a confirmed semantic target (F09) |
| wake during a reply | n/a | `robot_mic_pub.py` crashed | wake beep's `aplay` got "Device or resource busy" while speech played (F04) |

### Findings

- **Fixed outside this repo:** `angular_speed` set to 1.0 in `~/.dome/config/control.yaml` and in dome_control's `config/control-config.yaml` (not committed there), so both turn directions are inside the limits.
- **dome_control stays silent when `/describe_scene` has no server.** Since Claude is told to let the robot answer, the user hears nothing. dome_control should time out and say so.
- **The spike relays empty replies** to `/announcement`. T03 skips them.

### Retests still open

- Turn right, after a control restart.
- Describe, with dome_semantic running (`--options "d c vi se"`).
- Explore and go-to, with `bl dome_mission mission_explore.launch.py`, going to a detected object rather than a room.
- "Stop" while moving.
- The status question sent on `/voice/llm_text`.

## T03 — `voice_input` runs the LLM path, chosen in `voice.yaml`
**Status**: done (2026-11-20): on the robot, `robot.launch.py` alone ran the LLM path with "hey jarvis"; "hey marvin" did nothing. Leftover spike processes holding the mic and a second `speech_output` caused `Broken pipe` until stopped.
**Description**:
- **Config:** `command_path: grammar | llm` at the top of `voice.yaml` (default `grammar`). The robot's YAML sets `llm` and `wake_word: hey_jarvis`.
- **Capture:** the spike's capture-until-silence moves into a new ROS-free module, `dome_voice/utterance_capture.py`, because `runtime.py` is already long. `secs_to_chunks` goes into `runtime.py`, and `capture_command` uses it too.
- **Runtime:** `VoiceRuntime.wake_up` is the wake step, shared by `next_turn` and by `next_utterance` in `utterance_capture.py`, which returns the captured PCM. Vosk isn't loaded on the `llm` path.
- **Node:** on the `llm` path, `voice_input`:
  - publishes the PCM on `/voice/utterance`;
  - relays each non-empty `/voice/llm_reply` to `/announcement`;
  - beeps on wake, and on no speech, as the grammar path does.
- **Retire the spike's `robot_mic_pub.py` and `spike_capture.py`.** Their tests move to `test/`. `publish_wav.py` stays as a test tool.

**Test**:
- `command_path` loads, defaults to `grammar`, and rejects other values;
- the capture tests, moved from the spike;
- `next_utterance` returns PCM after a wake, and never loads Vosk;
- the node publishes the utterance and skips empty replies.

## T04 — Offline: say so instead of going quiet
**Status**: not done
**Description**: After publishing an utterance, `voice_input` waits up to `llm_timeout_secs` for a reply. On timeout it announces that the LLM path is offline. A reply that arrives after the timeout is still spoken.

**Test**: unit test with a fake clock, covering a reply in time, a timeout, and a late reply.

## T05 — Train a "hey robbie" wake model
**Status**: not done
**Description**: openWakeWord ships no "hey robbie" model. Train one with its training notebook (synthetic Piper clips, on a free Colab GPU). Put the `.onnx` on the robot, and set its absolute path as `wake_word`.

**Test**: manual. Record the hit rate on "hey robbie", and false wakes on ordinary talk and on "hey marvin", next to `hey_jarvis` under the same conditions.

## T06 — Tests and measurements
**Status**: not done
**Description**: Fill the test gaps T01–T04 left, then run F14's demo on the robot with the motors running.
- **Measure the latency end to end, from the end of the spoken question to the first spoken word of the answer.** Break it into the silence cutoff, transfer, Whisper, Claude, and Piper's start, so the largest part is known before tuning any of it.
- Check self-hearing with long replies.
- Check that "hey marvin" turns are unaffected.

**Test**: the full suite passes, apart from I01's known failures. The manual results go into F14.

## T07 — Docs
**Status**: not done
**Description**:
- Update `spec.md`: the pipeline diagram, the config section, and the planned marks.
- Regenerate the literate docs for `runtime.py`, `voice_input_node.py`, `llm_turn.py` and `llm_node.py`.
- Add the VM setup (from the spike README) to `02-doc/`.

**Test**: none, since this is documentation.

## T08 — Launch the VM side from `remote.launch.py`
**Status**: code done, 2 launch tests passing; the check on the VM is still to do
**Description**: Start `llm_node` the way the rest of the stack starts, so the VM runs `bl dome2 remote.launch.py --options "vi vo"` instead of a hand-typed command.
- **dome_voice:** a `llm_node` entry point, `launch/remote.launch.py` starting it, and `config/llm_persona.md` installed.
- **`llm_node` takes ROS parameters** (`persona`, `whisper_model`, `model`) instead of argparse flags, so a launch can set them. `persona` is required; the launch passes the installed file.
- **dome2:** `remote.launch.py` gets a `voice` subsystem. **`v` becomes ambiguous** between `viz` and `voice`; use `vi` and `vo`.
- **The VM now builds dome_voice** (`colcon build --packages-select dome_voice`), since a launch finds only installed packages.

**Test**: a launch test like `test_launch.py`: one node, `llm_node`, given the installed persona. Manual: start it on the VM with `bl dome2 remote.launch.py --options "vi vo"` and ask a question.
