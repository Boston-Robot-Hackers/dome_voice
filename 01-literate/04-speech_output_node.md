---
version: "2.0"
generated: "2026-11-19"
---

# 04 — `speech_output_node.py`: Giving the Robot a Voice

## Introduction

`speech_output_node` subscribes to `/announcement` and speaks each message aloud. It is the only node in the stack that produces speech. Anything that wants the robot to talk publishes an announcement and leaves the rest to this node.

Each announcement goes through three external steps:

```mermaid
flowchart LR
    A["/announcement"] --> B[Announcement.from_msg]
    B --> C["piper<br/>text → WAV"]
    C --> D["apply_wav_gain<br/>(if gain ≠ 1)"]
    D --> E["aplay<br/>WAV → speaker"]
```

## The announcement contract

The message type and the `Announcement` dataclass both come from `dome_control.announcement_contract`. An announcement has `text`, `priority`, `stamp`, `source` and `dedup_key`.

This node uses only `text`, plus `priority` and `source` for the log line. **Priorities and dedup keys are carried but not acted on yet.** There is no queue, no pre-emption and no dropping of repeats. A safety announcement waits behind chit-chat.

## Configuration by environment

All settings are read once, in `__init__`, from environment variables:

| Variable | Default here | Meaning |
|---|---|---|
| `DOME_PIPER_BIN` | `piper` | the piper executable |
| `DOME_PIPER_MODEL_PATH` | *(none, required)* | the `.onnx` voice model |
| `SPEECH_ALSA_DEVICE` | `""` (ALSA default) | playback device for `aplay -D` |
| `SPEECH_TMP_DIR` | system temp dir | where WAV files are written |
| `SPEECH_GAIN` | `0.35` | output volume multiplier |
| `PIPER_LENGTH_SCALE` | `1.25` | speech tempo; above 1.0 is slower |

**On the robot, the launch file supplies these** (chapter 05), with its own fallbacks: gain 0.25, length scale 1.0 and device `plughw:0,0`. So the defaults in this table apply only when the node is run by hand.

Gain and length scale are **validated at startup**: a non-number or a value ≤ 0 raises, and the node fails to start. That is the right place to fail, because a bad value would otherwise surface on the first announcement, possibly much later.

## Speaking one message

### Synthesis

```python
cmd = [piper_bin, "--model", model_path, "--output_file", wav_path,
       "--length_scale", str(length_scale), "--quiet"]
subprocess.run(cmd, input=text.encode("utf-8"), check=True, capture_output=True)
```

Piper reads the text on stdin and writes a WAV. It is a neural TTS that runs comfortably on a Pi. Running it as a **subprocess** keeps its native libraries out of the ROS process. Starting it per message costs a model load each time, but announcements are rare.

### Gain, in pure Python

Piper's output is often too loud for a small speaker, so the node scales every sample:

```python
def scale_pcm_frames(frames: bytes, sample_width: int, gain: float) -> bytes:
    max_value = (1 << (sample_width * 8 - 1)) - 1
    min_value = -(1 << (sample_width * 8 - 1))
    ...
    for offset in range(0, len(frames), sample_width):
        sample = struct.unpack_from(fmt, frames, offset)[0]
        adjusted = int(sample * gain)
        adjusted = max(min(adjusted, max_value), min_value)
```

- **Multiplying the samples is a linear volume change.** A gain of 0.25 is about −12 dB.
- **Clipping protects against gain > 1.** Without it, a loud sample would wrap around from +32767 to −32768, which sounds like a crack.
- **It handles 8-, 16- and 32-bit WAVs**, choosing the `struct` format from the sample width. One caveat: 8-bit WAV is *unsigned* by the WAV spec, and this treats it as signed. Piper writes 16-bit, so it never matters here.

With a gain of exactly 1.0, the step is skipped and the original file is played.

### Playback and cleanup

`aplay` plays the file, on `SPEECH_ALSA_DEVICE` if set. The `finally` block removes both temp files, the synthesised one and the gained one, even when synthesis or playback fails.

## Failure handling

```python
try:
    self.speak_text(announcement.text)
    ...
except Exception as exc:
    self.get_logger().error(f"Speech output failed: {exc}")
```

**One failed announcement must not kill the node**, so every error is logged and the node carries on. That's what you see on the robot today: `No such file or directory` for the missing piper binary, once per announcement, with the node still running.

The catch is broad, though. A programming error in `speak_text` would be logged the same way as a missing file.

## Shutdown

`main()` treats `KeyboardInterrupt` and `ExternalShutdownException` (the launcher's SIGTERM) as a normal stop. Then it destroys the node and calls `rclpy.try_shutdown()`, so stopping a launch prints no traceback.

## Observations

1. **Speech blocks the callback.** `speak_text` runs piper and aplay synchronously inside the subscription callback. With the default single-threaded executor, announcements arriving during speech queue up in the 10-deep subscription buffer, and anything beyond that is dropped.
2. **Priority is ignored.** The contract supports priorities and dedup keys, and dome_control's features F08 to F10 (priority queue, barge-in, dedup) plan to use them. Until then, the order is first-come, first-served.
3. **Two sets of defaults.** This node's fallbacks (gain 0.35, length 1.25) differ from the launch file's (0.25, 1.0). Only the launch file's apply on the robot. One set would be enough.
4. **The gain loop is per-sample Python.** For a few seconds of 22 kHz audio it's fine; `numpy` would do the same in one vectorised call.
5. **A broad `except Exception`** hides bugs as runtime failures. Catching `subprocess.CalledProcessError`, `OSError` and `wave.Error` would cover the real cases.
