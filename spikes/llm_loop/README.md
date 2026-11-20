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

All in `/home/pitosalas/ros2_ws/src/dome_voice/spikes/llm_loop/` on the robot:

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

**3. The code.** The VM needs only `vm_llm_node.py` and `llm_turn.py`. Get them by cloning the repo once the spike is pushed:

```bash
git clone git@github.com:Boston-Robot-Hackers/dome_voice.git ~/dome_voice
```

or by copying them from the robot:

```bash
mkdir -p ~/dome_voice/spikes/llm_loop
scp pitosalas@dome-R1:/home/pitosalas/ros2_ws/src/dome_voice/spikes/llm_loop/{vm_llm_node.py,llm_turn.py} ~/dome_voice/spikes/llm_loop/
```

If the VM can't resolve `dome-R1`, use the robot's IP address, which was `192.168.4.100` on 2026-11-20.

**4. Python packages.** On Ubuntu 24.04, add `--break-system-packages`:

```bash
pip install --user faster-whisper anthropic
```

**5. The API key.** Get one at console.anthropic.com, then add this to the VM's `~/.bashrc`:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Each run

**Robot, terminal A: speech output.** Stop `robot.launch.py` first if it is running. This starts `speech_output` with the same settings the launch gives it:

```bash
source /home/pitosalas/ros2_ws/install/setup.bash
SPEECH_ALSA_DEVICE=plughw:0,0 SPEECH_GAIN=0.25 PIPER_LENGTH_SCALE=1.0 \
  ros2 run dome_voice speech_output
```

**VM: the LLM node.** The first run downloads the Whisper model (about 150 MB):

```bash
source /opt/ros/kilted/setup.bash
python3 ~/dome_voice/spikes/llm_loop/vm_llm_node.py
```

Wait for `Ready: Whisper 'base.en', Claude 'claude-opus-5-5'`.

**Robot, terminal B: mic and relay.**

```bash
source /home/pitosalas/ros2_ws/install/setup.bash
python3 /home/pitosalas/ros2_ws/src/dome_voice/spikes/llm_loop/robot_mic_pub.py
```

**Talk.** Say "hey marvin", wait for the beep, then ask something.

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
