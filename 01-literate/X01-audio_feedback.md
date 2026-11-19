---
version: "2.0"
generated: "2026-11-19"
---

# X01 — `audio_feedback.py`: Confirmation Beeps

## What it does

`beep()` synthesises a short tone and plays it through `aplay`. The voice node uses three beeps, all set in `config/voice.yaml`:

| Event | Frequency | Duration | Meaning |
|---|---|---|---|
| wake word heard | 880 Hz | 0.3 s | "I'm listening" |
| intent recognised | 330 Hz | 0.02 s | "got it" (a click) |
| nothing understood | 220 Hz | 0.6 s | "try again" |

The design leans on *contrast*: a high tone to start, a near-instant tick for success, and a long low tone for failure, so they are easy to tell apart without looking.

## A bell, not a beep

A pure sine sounds harsh and electronic. This one adds a second, *inharmonic* partial and gives both an exponential decay:

```python
fund = math.sin(2 * math.pi * frequency * t) * math.exp(-4.0 * t)
partial = math.sin(2 * math.pi * frequency * 2.76 * t) * math.exp(-12.0 * t) * 0.4
```

- **The 2.76× partial is not a whole-number harmonic.** Real bells have partials at non-integer ratios, which is what makes them sound like bells and not like organ pipes.
- **The partial decays three times faster** than the fundamental. The tone starts bright and settles into a pure pitch, the way a struck bell does.

## Building the buffer

- 16 kHz, 16-bit, **stereo**, with the same sample in both channels, matching the Seeed board's output format.
- **Amplitude is capped at 7 % of full scale** (`0.07 × volume`). The board's amplifier is loud, and a full-scale beep next to someone's head is painful.
- `struct.pack_into` writes left and right samples straight into a pre-sized `bytearray`, avoiding a copy per sample.

## Playing it

```python
cmd = ["aplay", "-q", "-f", "S16_LE", "-r", str(sample_rate), "-c", "2"]
if alsa_device:
    cmd.extend(["-D", alsa_device])
subprocess.run(cmd, input=bytes(buf), check=False, capture_output=True)
```

The raw PCM goes to `aplay` on stdin, so no file is written. The device comes from **`$SPEECH_ALSA_DEVICE`**, the same variable speech output uses, so beeps and speech come out of the same speaker.

**The call blocks** until the beep finishes, so command capture starts only after the "I'm listening" beep has played.

**But arecord keeps recording during the beep.** Its audio waits in the pipe, and `capture_command` reads it first. Only one 80 ms chunk is skipped (`WAKE_SKIP_CHUNKS`), so most of the 0.3 s beep, picked up by the microphone, is probably fed to Vosk and the speech detector. That is unverified, but it could count as "speech has started" and shorten the real command window.

## Observations

1. **The wake beep is probably recorded.** Skipping the beep's duration in chunks after `on_wake`, instead of one chunk, would keep it out of the command.
2. **`device_index` is accepted and ignored.** The parameter suggests the caller picks the device, but the environment variable does. The voice node passes it on every call.
3. **Failures are only half reported.** `check=False` means a non-zero `aplay` exit, such as a busy device, passes silently. Only an exception, such as `aplay` missing, is printed, and that goes to `print(..., file=sys.stderr)` rather than a logger.
4. **The per-sample loop** builds up to 9 600 samples in Python for the longest beep. That's fine at this size; numpy would make it one expression.
