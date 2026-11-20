# TF14 LLM command path, next to the fixed grammar, for Feature F14

The order follows *try it early*: T01 gives a working slice on the existing spike robot script, and T02 is you trying it on the robot. The hardening comes after that.

Run the tests with `python3 -m pytest /home/pitosalas/ros2_ws/src/dome_voice/test/`.

## T01 — Claude emits intents through tools (VM side)
**Status**: code done, 13 unit tests passing; the manual check on the VM is still to do
**Description**: Move the spike's `llm_turn.py` and `vm_llm_node.py` into the package, as `dome_voice/llm_turn.py` (ROS-free) and `dome_voice/llm_node.py`.

- **Tools:** one per intent in F14's list. `navigation_go` takes a `label`.
- **One request per turn:** `Conversation.ask` returns the reply text and any intents.
- **Tool results go into the history** at the start of the next user message, so a tool call costs no second request.
- **The system prompt** is the persona read from `config/llm_persona.md` (a placeholder for now, set with `--persona`), then the fixed rules in code. The time starts each user message instead, so the system prompt can be cached.
- **Text in:** the node also subscribes to `/voice/llm_text` and passes each string to `Conversation.ask` as if it were a transcript.
- **The node** publishes each intent on `/intent` (source `llm`), and always publishes one `/voice/llm_reply`, even an empty one.
- **On the VM**, it runs from the repo root as `python3 -m dome_voice.llm_node`, so it needs no `colcon build` there. Importing the package pulls in `runtime.py`, which needs `numpy`, `pyyaml` and `pydantic`. openWakeWord and Vosk are imported only when used.

**Test**: unit tests with a fake client:
- a tool call becomes the right intent dict;
- text-only replies give no intent;
- the history stays valid after a tool call;
- a refusal still gets the fixed reply;
- the persona is in the system prompt, and the time starts the user message;
- a missing persona file raises.

Manual check: `ros2 topic pub --once /voice/llm_text std_msgs/String "data: 'tell me a robot joke'"` gets a spoken joke.

## T02 — Try it on the robot
**Status**: not done
**Description**: Run the new VM node with the spike's `robot_mic_pub.py` (wake word `hey_jarvis`), plus dome_control and dome_mission. Try "go explore", "what do you see?", "turn left", "go to the kitchen", a joke, a general question, and "stop". Also send "give a full update on the robot status" on `/voice/llm_text`.

**Test**: manual. For each request, record the transcript, the intent published (`ros2 topic echo /intent`), and what the robot did.

## T03 — `voice_input` listens for both wake words
**Status**: not done
**Description**:
- **Config:** add `llm_wake_word` (default `none`) and `llm_timeout_secs` to `voice.yaml` and `VoiceConfigFile`.
- **Wake models:** `load_wake_model` loads both models into one openWakeWord instance, and `wait_for_wake` reports which one fired.
- **Routing:** a turn on the LLM wake word is captured with the spike's capture rules (moved into the runtime) and published on `/voice/utterance`, skipping Vosk.
- **Relay:** `voice_input` relays `/voice/llm_reply` to `/announcement`, and skips empty replies.
- **Retire the spike's robot script.**

**Test**:
- the YAML loads with the key unset and with it set;
- the right wake key is reported when either model fires (fake model);
- an LLM turn is published and doesn't reach Vosk;
- an empty reply isn't announced.

## T04 — Offline: say so instead of going quiet
**Status**: not done
**Description**: After publishing an utterance, `voice_input` waits up to `llm_timeout_secs` for a reply. On timeout it announces that the LLM path is offline. A reply that arrives after the timeout is still spoken.

**Test**: unit test with a fake clock, covering a reply in time, a timeout, and a late reply.

## T05 — Train a "hey robbie" wake model
**Status**: not done
**Description**: openWakeWord ships no "hey robbie" model. Train one with its training notebook (synthetic Piper clips, on a free Colab GPU). Put the `.onnx` on the robot, and set its absolute path as `llm_wake_word`.

**Test**: manual. Record the hit rate on "hey robbie", and false wakes on ordinary talk and on "hey marvin", next to `hey_jarvis` under the same conditions.

## T06 — Tests and measurements
**Status**: not done
**Description**: Fill the test gaps T01–T04 left, then run F14's demo on the robot with the motors running.
- Measure the latency end to end, from end of speech to first word.
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
