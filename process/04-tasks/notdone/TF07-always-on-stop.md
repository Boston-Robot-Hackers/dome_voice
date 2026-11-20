# TF07 An always-on stop phrase (Feature F07)

Ordered so you can **try the whole stop path after T03, with a stand-in model**, before training the real one.

## T01 — Config
**Status**: not done
**Description**: Add `stop_word` (model name or `.onnx` path) and `stop_threshold` to `StreamSettings`. Empty `stop_word` means none.
**Test**: config loads both; threshold bounds validated.

## T02 — Score both models; report a stop
**Status**: not done
**Description**: Load wake and stop models into one openWakeWord instance. `wait_for_wake` and `capture_command` check the stop score on every chunk and end the turn with `VoiceTurn.is_stop = True`. `voice_input` publishes the stop intent at once, before any beep, also while muted (F04).
**Test**: a fake model firing the stop key, during wake-wait and during capture, gives a stop turn at once; `process_turn` publishes before calling `beep`.

## T03 — You try it with a stand-in
**Status**: not done
**Description**: Set `stop_word` to one of openWakeWord's pre-trained models (e.g. `hey_jarvis`). Drive the robot; say the stand-in phrase without the wake word. Expected: `stop` on `/intent` almost immediately, and the robot stops. Record results here. *Manual: robot.*

## T04 — Choose the phrase and train it
**Status**: not done
**Description**: Get the user's choice (recommended "marvin stop"). Train with openWakeWord's notebook off the robot. Record settings and model location in notes. *Manual: off-robot training.*

## T05 — You try the real phrase
**Status**: not done
**Description**: Point `stop_word` at the trained model; repeat T03. If F05 exists, replay driving noise and about 30 stop phrases; record detection rate, false stops per hour, latency; tune `stop_threshold`. *Manual: real audio.*

## T06 — Docs and full test run
**Status**: not done
**Description**: Runtime literate doc; spec's Safety section. Run `python3 -m pytest test/`.
