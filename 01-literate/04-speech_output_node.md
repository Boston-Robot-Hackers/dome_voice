---
version: "2.2"
generated: "2026-11-20"
---

# 04 — `speech_output_node.py`: Giving the Robot a Voice

## Introduction

`speech_output_node` subscribes to `/announcement` and speaks each message aloud. It is the only node in the stack that produces speech. Anything that wants the robot to talk publishes an announcement and leaves the rest to this node.

Each announcement flows through a **pipeline of two processes**, with the node in the middle scaling the volume:

```mermaid
flowchart LR
    A["/announcement"] --> B[Announcement.from_msg]
    B -->|text on stdin| C["piper --output_raw"]
    C -->|raw int16 PCM| D["scale_pcm<br/>(numpy, per chunk)"]
    D -->|raw int16 PCM| E["aplay -t raw"]
    E --> F[speaker]
```

The key property is that **audio flows as soon as Piper produces it**. The robot starts speaking after the first sentence is synthesized, not after the whole reply.

## The announcement contract

The message type and the `Announcement` dataclass both come from `dome_control.announcement_contract`. An announcement has `text`, `priority`, `stamp`, `source` and `dedup_key`.

This node uses only `text`, plus `priority` and `source` for the log line. **Priorities and dedup keys are carried but not acted on yet.** There is no queue, no pre-emption and no dropping of repeats. A safety announcement waits behind chit-chat.

## Configuration: the YAML for tuning, the environment for paths

Since F13 (2026-11-20), the node's settings come from **two sources, split by kind**:

| Setting | Source | Robot value |
|---|---|---|
| `gain` | `speech:` in `voice.yaml` | 0.5 |
| `length_scale` | `speech:` in `voice.yaml` | 1.0 |
| `alsa_device` | `speech:` in `voice.yaml` | `plughw:0,0` |
| `DOME_PIPER_BIN` | environment | set by `provision_dome` |
| `DOME_PIPER_MODEL_PATH` | environment (required) | set by `provision_dome` |

**Tuning goes in the YAML; install paths stay in the environment.** The volume is a choice about how the robot sounds, so it belongs next to the rest of the voice config, where you can read it. The Piper paths differ per machine and are written by the installer, so a checked-in file is the wrong place for them.

The YAML arrives the same way as for `voice_input`: as the **`config` parameter**, set by `robot.launch.py`. Without it the node refuses to start:

```python
def config_path(self) -> str:
    self.declare_parameter("config", "")
    path = self.get_parameter("config").get_parameter_value().string_value
    if not path:
        raise RuntimeError(
            "speech_output needs the `config` parameter (the voice YAML); "
            "launch it with `bl dome_voice robot.launch.py`"
        )
    return path
```

`load_speech_settings` (chapter 01) validates the file with the same strict model, so a gain of 0 or a misspelled key stops the node at startup. The old `SPEECH_GAIN`, `PIPER_LENGTH_SCALE` and `SPEECH_ALSA_DEVICE` variables are no longer read.

**This replaced three layers of defaults** that disagreed: the node's own (gain 0.35), the launch file's fallbacks (0.25), and the shell. Now there is one, in `SpeechSettings`, and the YAML writes out the robot's values.

Startup also reads the **voice's sample rate** from the `<model>.onnx.json` file Piper ships beside every voice:

```python
def model_sample_rate(model_path: str) -> int:
    if not model_path:
        raise RuntimeError("DOME_PIPER_MODEL_PATH is required for speech output")
    config_path = Path(f"{model_path}.json")
    return int(json.loads(config_path.read_text())["audio"]["sample_rate"])
```

This is needed because **raw PCM has no header**. A WAV file says its own rate, but `aplay -t raw` must be told, and the wrong rate plays the voice too fast or too slow. The robot's `en_US-lessac-medium` voice is 22050 Hz.

All of this is **validated at startup**: a missing `config`, a bad YAML value, a missing model path or a missing `.json` makes the node fail to start. That is the right place to fail, because a bad value would otherwise surface on the first announcement, possibly much later.

## Speaking one message

### Two commands

The node builds one command line for each end of the pipe:

```python
def piper_command(piper_bin, model_path, length_scale):
    return [piper_bin, "--model", model_path, "--output_raw",
            "--length_scale", str(length_scale), "--quiet"]

def aplay_command(sample_rate, alsa_device=""):
    cmd = ["aplay", "-q"]
    if alsa_device:
        cmd.extend(["-D", alsa_device])
    cmd.extend(["-t", "raw", "-f", "S16_LE", "-r", str(sample_rate), "-c", "1"])
    return cmd
```

- **`--output_raw`** makes Piper write 16-bit mono PCM to stdout *sentence by sentence*, instead of a finished WAV file.
- **`aplay -t raw -f S16_LE -c 1`** is the matching consumer: little-endian 16-bit mono at the model's rate.

Both are plain functions, so the tests can check them without running anything.

### The streaming loop

`stream_speech` connects the two with pipes and copies audio across in chunks:

```python
carry = b""
while chunk := synth.stdout.read(PCM_CHUNK_BYTES):
    chunk = carry + chunk
    whole = len(chunk) - len(chunk) % 2
    play.stdin.write(scale_pcm(chunk[:whole], gain))
    carry = chunk[whole:]
```

**Why the node sits in the middle** instead of piping Piper straight to aplay: the volume. Piper's output peaks at full scale, which is too loud for the robot's speaker, so every chunk is scaled on its way through.

**The carry handles a subtle pipe property.** A read from a pipe returns *whatever is available*, up to the limit, and that can be an odd number of bytes. An int16 sample is 2 bytes, so a split sample would misalign every sample after it, and the audio would turn into loud noise. Keeping the stray byte for the next read keeps the stream aligned.

The text itself is written to Piper's stdin up front and stdin is closed. A reply is small enough to fit in the pipe buffer, so this can't block.

### Gain with numpy

```python
def scale_pcm(pcm: bytes, gain: float) -> bytes:
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) * gain
    return np.clip(samples, -32768, 32767).astype("<i2").tobytes()
```

- **Multiplying the samples is a linear volume change.** A gain of 0.5 is about −6 dB; 0.25 is about −12 dB.
- **Clipping protects against gain > 1.** Without it, a loud sample would wrap around from +32767 to −32768, which sounds like a crack. Since Piper already peaks at full scale, any gain above 1.0 distorts.
- **One vectorised call per 4 KB chunk.** The earlier per-sample `struct` loop took about 0.15 s per reply; this takes a fraction of a millisecond.

### Exits and cleanup

```python
check_exit("piper", synth)
check_exit("aplay", play)
...
finally:
    for proc in (synth, play):
        if proc.poll() is None:
            proc.kill()
            proc.wait()
```

`check_exit` waits for each process and raises with its stderr if it exited non-zero, so a log line says *why* (no device, bad model) and not just that it failed.

The `finally` covers the early-failure case. If aplay dies mid-stream, for example because the device is busy, the next write raises `BrokenPipeError`, and Piper would otherwise be left running. **Both processes are always reaped**, so a failed announcement leaves no stray processes behind.

## Failure handling

```python
try:
    self.speak_text(announcement.text)
    ...
except (RuntimeError, ValueError, OSError) as exc:
    self.get_logger().error(f"Speech output failed: {exc}")
```

**One failed announcement must not kill the node**, so these errors are logged and the node carries on.

**The catch names what `speak_text` can raise:**
- `RuntimeError` when piper or aplay exits non-zero.
- `OSError` for a missing binary or a broken pipe.
- `ValueError` from bad audio data.

A programming error, such as a `TypeError`, still surfaces instead of being logged as a speech failure.

## Shutdown

`main()` treats `KeyboardInterrupt` and `ExternalShutdownException` (the launcher's SIGTERM) as a normal stop. Then it destroys the node and calls `rclpy.try_shutdown()`, so stopping a launch prints no traceback.

## Observations

1. **Piper still starts per announcement.** About 1 s of the 1.3 s before the first word is Piper loading its model. A long-lived Piper process fed one line per announcement would remove that, but the node would then need a way to find where each utterance's raw audio ends, since the stream has no markers.
2. **Speech blocks the callback.** `speak_text` runs inside the subscription callback. With the default single-threaded executor, announcements arriving during speech queue up in the 10-deep subscription buffer, and anything beyond that is dropped.
3. **Priority is ignored.** The contract supports priorities and dedup keys, and dome_control's features F08 to F10 (priority queue, barge-in, dedup) plan to use them. Until then, the order is first-come, first-served.
4. **Speech and beeps can collide.** Speech plays on `plughw:0,0`, which takes the device exclusively, while beeps use ALSA's default. A beep during an announcement can fail with *Device or resource busy*.
