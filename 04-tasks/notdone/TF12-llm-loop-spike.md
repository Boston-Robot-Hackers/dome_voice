# TF12 LLM conversation loop (spike) for Feature F12

This is a spike, so tests are light. Pure helpers get unit tests. The ROS and API wiring is checked by hand on the robot and the VM, and each check is noted in its task.

Run the tests with `python3 -m pytest /home/pitosalas/ros2_ws/src/dome_voice/spikes/llm_loop/`.

## T01 — Robot side: wake, capture, publish
**Status**: done
**Description**: `spikes/llm_loop/robot_mic_pub.py` opens the mic with the existing `voice.yaml` settings and waits for the wake word with `wait_for_wake`. `spike_capture.py` captures until silence, using the same rules as `capture_command` and a max of `max_command_secs`. The script publishes the PCM on `/voice/utterance`.

**Test**: `test_spike_capture.py` has 5 unit tests. Manual check, 2026-11-20: two utterances, 1.8 s and 2.6 s, arrived on `/voice/utterance`.

## T02 — VM side: transcribe and reply; robot relays the reply
**Status**: code done and unit tests passing; the manual check on the VM is still to do
**Description**: `spikes/llm_loop/vm_llm_node.py` subscribes to `/voice/utterance` and transcribes with faster-whisper. It sends the transcript, with the conversation history, to Claude (`llm_turn.Conversation`), and publishes the reply as a `String` on `/voice/llm_reply`. It logs the transcript, the reply, and the STT and LLM times. `robot_mic_pub.py` relays `/voice/llm_reply` to `/announcement` as an `Announcement` with source `llm_spike`. `publish_wav.py` replays a recorded WAV on `/voice/utterance`.

**Test**: `test_llm_turn.py` has 7 unit tests: PCM decoding, the history, failure and refusal handling. Checked on the robot, 2026-11-20: `publish_wav.py` delivered a 6.2 s recording, and a string on `/voice/llm_reply` came out on `/announcement`. Manual check still to do: run the VM node and replay a WAV to it.

## T03 — Setup notes
**Status**: done
**Description**: `spikes/llm_loop/README.md` covers VM networking, the pip installs, the API key, which robot nodes to run, and the run commands, with full paths.

**Test**: none, since this is documentation.

## T04 — Try it and record findings
**Status**: not done
**Description**: Run about 10 real exchanges. Record the end-to-end latency, the STT and LLM times, transcript errors, and whether the robot heard its own reply. Write the findings and a go/no-go recommendation at the bottom of F12.

**Test**: manual. The findings are the result.
