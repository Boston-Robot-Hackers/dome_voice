# The LLM command path (F14): setup and running

Spoken request on the robot → transcribed and answered on the VM → an `/intent`, a spoken reply, or both.

This directory began as the F12 spike. **The code now lives in the package**; only `publish_wav.py`, a test tool, is left here.

## How it fits together

```
robot  voice_input    mic → "hey jarvis" → capture → /voice/utterance (UInt8MultiArray, 16 kHz int16 PCM)
VM     llm_node       /voice/utterance or /voice/llm_text → faster-whisper → Claude → /intent, /voice/llm_reply (String)
robot  voice_input    /voice/llm_reply → /announcement (dome_control Announcement)
robot  speech_output  /announcement → Piper → speaker, with /voice/speaking around it
```

- **`command_path: llm`** in `config/voice.yaml` puts `voice_input` on this path, with `wake_word: hey_jarvis`. `command_path: grammar` with `hey_marvin` brings back the fixed grammar.
- **The VM needs only stock ROS 2.** `voice_input` does the relay to `/announcement`, so `dome_control` stays on the robot.

## Files

- `dome_voice/voice_input_node.py` and `dome_voice/utterance_capture.py`: the robot side.
- `dome_voice/llm_node.py` and `dome_voice/llm_turn.py`: the VM side.
- `config/llm_persona.md`: who the robot is, for the system prompt.
- `spikes/llm_loop/publish_wav.py`: publishes a recorded WAV on `/voice/utterance`, to test the VM without the mic.

## One-time VM setup

**1. The network.** The VM must see the robot's DDS traffic. That means **bridged networking, not NAT**, and the same `ROS_DOMAIN_ID` on both machines. The robot leaves it unset, which means 0. Check from the VM, while `voice_input` runs on the robot:

```bash
ros2 topic list | grep /voice/utterance
```

**2. ROS 2.** Use the same distro as the robot (kilted) if you can.

**3. The code.** Clone the repo into the VM's workspace, the same place as on the robot (to update it later, run `git pull` in that directory):

```bash
git clone git@github.com:Boston-Robot-Hackers/dome_voice.git /home/pitosalas/ros2_ws/src/dome_voice
```


**4. Python packages.** On Ubuntu 24.04, add `--break-system-packages`:

```bash
pip install --user faster-whisper anthropic "brotli>=1.2"
```

**The `brotli` upgrade matters.** Ubuntu's apt `brotli` (1.1) is too old for the SDK's HTTP client. Every API reply then fails to decompress, and the SDK reports a misleading `Connection error`. Check what loads with `python3 -c "import brotli; print(brotli.__version__, brotli.__file__)"`. It should be 1.2 or later, from `~/.local`.

**The API account needs credit.** API billing is separate from a Claude.ai subscription. Buy credits at console.anthropic.com → Plans & Billing, or you get `400 ... credit balance is too low`.

**5. The API key.** Get one at console.anthropic.com, then add this to the VM's `~/.bashrc`:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Each run

**VM: the LLM node.** The first run downloads the Whisper model (about 150 MB):

```bash
source /opt/ros/kilted/setup.bash
cd /home/pitosalas/ros2_ws/src/dome_voice && python3 -m dome_voice.llm_node
```

Wait for `Ready: Whisper 'base.en', Claude 'claude-haiku-5-5'`.

**Robot: the normal launch, with the `voice` subsystem.** For example, drivers, control, vision, voice and the gamepad:

```bash
bl dome2 robot.launch.py --options "d c vi vo y"
```

For "what do you see?", add `se` (dome_semantic), which also needs a map name: `--map_name <name>`. Saved maps are in `/home/pitosalas/.dome/slam_maps/`.

`voice_input` logs `Voice input ready — llm path, listening for 'hey_jarvis'`.

**Talk.** Say "hey jarvis", wait for the beep, then ask something.

- The VM logs `Heard (...)` and `Reply (...)`, with the STT and LLM times and the intents.
- `voice_input` logs `Sent ... s of audio to the LLM`, then `LLM reply: ...` when there is something to say.

**Ask by text**, as a program or a gamepad button would:

```bash
ros2 topic pub --once /voice/llm_text std_msgs/String "data: 'tell me a robot joke'"
```

**Volume** is `speech: gain:` in `/home/pitosalas/ros2_ws/src/dome_voice/config/voice.yaml`. The launch reads the installed copy, so run `colcon build --packages-select dome_voice` in `/home/pitosalas/ros2_ws`, then restart.

## Testing the VM without talking

With the VM node running, publish a recorded turn from the robot. `publish_wav.py` applies `stt_gain_db` from the voice YAML, because recordings are saved before gain:

```bash
source /home/pitosalas/ros2_ws/install/setup.bash
python3 /home/pitosalas/ros2_ws/src/dome_voice/spikes/llm_loop/publish_wav.py \
  /home/pitosalas/voice_recordings/20261119-194013-866650.wav
```

## Unit tests

They run on the robot and need neither `anthropic` nor `faster-whisper`:

```bash
python3 -m pytest /home/pitosalas/ros2_ws/src/dome_voice/test/
```

## Notes

- **The robot runs the installed `dome_voice`.** After changing `/home/pitosalas/ros2_ws/src/dome_voice/dome_voice/`, run `colcon build --packages-select dome_voice` in `/home/pitosalas/ros2_ws`.
- **Options:** `llm_node --whisper-model small.en` is slower but more accurate. `--model <id>` picks another Claude model. `--persona FILE` picks the persona (default `config/llm_persona.md`).
- **Each reply is billed** to the API key's account.
