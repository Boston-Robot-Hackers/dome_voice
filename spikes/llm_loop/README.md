# LLM loop spike (F12)

Spoken question on the robot → transcribed and answered on the VM → spoken by the robot.

## How it fits together

```
robot  robot_mic_pub.py   mic → wake word → capture → /voice/utterance (UInt8MultiArray, 16 kHz int16 PCM)
VM     vm_llm_node.py     /voice/utterance → faster-whisper → Claude → /voice/llm_reply (String)
robot  robot_mic_pub.py   /voice/llm_reply → /announcement (dome_control Announcement)
robot  speech_output      /announcement → Piper → speaker
```

**The VM needs only stock ROS 2.** The robot script does the relay to `/announcement`, so `dome_control` stays on the robot.

## Files

All in `/home/pitosalas/ros2_ws/src/dome_voice/spikes/llm_loop/`, which is the same path on the robot and the VM:

- `robot_mic_pub.py`: the robot side (mic and relay).
- `spike_capture.py`: captures until silence; used by `robot_mic_pub.py`.
- `vm_llm_node.py`: the VM side (Whisper and Claude).
- `llm_turn.py`: PCM decoding and the Claude conversation; used by `vm_llm_node.py`.
- `publish_wav.py`: publishes a recorded WAV on `/voice/utterance`, to test the VM without the mic.
- `test_spike_capture.py`, `test_llm_turn.py`: unit tests.

## One-time VM setup

**1. The network.** The VM must see the robot's DDS traffic. That means **bridged networking, not NAT**, and the same `ROS_DOMAIN_ID` on both machines. The robot leaves it unset, which means 0. Check from the VM, while `robot_mic_pub.py` runs on the robot:

```bash
ros2 topic list | grep /voice/utterance
```

**2. ROS 2.** Use the same distro as the robot (kilted) if you can.

**3. The code.** The VM needs only `vm_llm_node.py` and `llm_turn.py`. Clone the repo into the VM's workspace, the same place as on the robot (to update it later, run `git pull` in that directory):

```bash
git clone git@github.com:Boston-Robot-Hackers/dome_voice.git /home/pitosalas/ros2_ws/src/dome_voice
```

or by copying them from the robot:

```bash
mkdir -p /home/pitosalas/ros2_ws/src/dome_voice/spikes/llm_loop
scp pitosalas@dome-R1:/home/pitosalas/ros2_ws/src/dome_voice/spikes/llm_loop/{vm_llm_node.py,llm_turn.py} /home/pitosalas/ros2_ws/src/dome_voice/spikes/llm_loop/
```

If the VM can't resolve `dome-R1`, use the robot's IP address, which was `192.168.4.100` on 2026-11-20.

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

**Robot, terminal A: speech output.** Stop `robot.launch.py` first if it is running. This starts `speech_output` alone, with the same installed `voice.yaml` the launch gives it. The volume is `speech: gain:` in that file (F13):

```bash
source /home/pitosalas/ros2_ws/install/setup.bash
ros2 run dome_voice speech_output --ros-args \
  -p config:=/home/pitosalas/ros2_ws/install/dome_voice/share/dome_voice/config/voice.yaml
```

To change the volume, edit `/home/pitosalas/ros2_ws/src/dome_voice/config/voice.yaml`, run `colcon build --packages-select dome_voice` in `/home/pitosalas/ros2_ws`, and restart this node.

**VM: the LLM node.** The first run downloads the Whisper model (about 150 MB):

```bash
source /opt/ros/kilted/setup.bash
python3 /home/pitosalas/ros2_ws/src/dome_voice/spikes/llm_loop/vm_llm_node.py
```

Wait for `Ready: Whisper 'base.en', Claude 'claude-haiku-5-5'`.

**Robot, terminal B: mic and relay.**

```bash
source /home/pitosalas/ros2_ws/install/setup.bash
python3 /home/pitosalas/ros2_ws/src/dome_voice/spikes/llm_loop/robot_mic_pub.py
```

**Talk.** Say "hey jarvis", wait for the beep, then ask something.

- The spike has its own wake word, so it never answers "hey marvin". `--wake-word` takes an openWakeWord model name or an absolute `.onnx` path; the default `hey_jarvis` stands in until a "hey robbie" model exists.

- The VM logs `Heard (...)` and `Reply (...)`, with the STT and LLM times.
- Robot terminal B logs `Speaking reply: ...`, and the robot speaks.

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
python3 -m pytest /home/pitosalas/ros2_ws/src/dome_voice/spikes/llm_loop/
```

## Notes

- **The robot scripts use the installed `dome_voice`.** After changing `/home/pitosalas/ros2_ws/src/dome_voice/dome_voice/`, run `colcon build --packages-select dome_voice` in `/home/pitosalas/ros2_ws`.
- **Options:** `vm_llm_node.py --whisper-model small.en` is slower but more accurate. `--model <id>` picks another Claude model.
- **Each reply is billed** to the API key's account.
