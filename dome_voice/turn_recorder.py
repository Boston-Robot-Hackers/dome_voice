#!/usr/bin/env python3
"""
turn_recorder.py — save each voice turn's mic audio to WAV, for listening and replay.

Author: Pito Salas and Claude Code
Open Source Under MIT license

`TurnRecorder` wraps the mic stream and sees every read the runtime makes.
It has two modes:

- **Waiting** (between turns): reads go into a ring buffer holding the last
  `PREROLL_SECS`, so the audio just before wake detection is kept.
- **In a turn** (after `mark_wake`): every read is kept until `write_turn`.

`write_turn` saves `<stamp>.wav` (16 kHz mono, unfiltered, so a replay goes
through the same filter as live audio) and `<stamp>.json` with what the
pipeline heard, then returns to waiting. `expected` in the sidecar is left
`None` for the user to fill in by hand.
"""

import collections
import json
import wave
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from dome_voice.intent_mapper import map_intent

RATE = 16000
STEREO_BYTES_PER_SAMPLE = 4
PREROLL_SECS = 1.0


def stereo_to_mono(raw: bytes) -> np.ndarray:
    """Average interleaved S16_LE stereo bytes into int16 mono samples."""
    stereo = np.frombuffer(raw, dtype=np.int16).reshape(-1, 2)
    return stereo.mean(axis=1).astype(np.int16)


class TurnRecorder:
    """A mic stream wrapper that records each turn, starting before the wake."""

    def __init__(self, stream, record_dir: Path, chunk_bytes: int):
        self.stream = stream
        self.record_dir = record_dir
        preroll_reads = max(
            1, round(PREROLL_SECS * RATE * STEREO_BYTES_PER_SAMPLE / chunk_bytes)
        )
        self.preroll: collections.deque[bytes] = collections.deque(maxlen=preroll_reads)
        self.turn_reads: list[bytes] | None = None
        self.preroll_bytes = 0
        self.record_dir.mkdir(parents=True, exist_ok=True)

    def read(self, size: int) -> bytes:
        data = self.stream.read(size)
        if self.turn_reads is None:
            self.preroll.append(data)
        else:
            self.turn_reads.append(data)
        return data

    def mark_wake(self) -> None:
        """Start keeping every read; the ring buffer becomes the turn's start."""
        self.turn_reads = list(self.preroll)
        self.preroll_bytes = sum(len(data) for data in self.turn_reads)
        self.preroll.clear()

    def write_turn(self, heard: dict[str, Any]) -> Path:
        """Write the turn's WAV and sidecar, return the WAV path, start waiting."""
        if self.turn_reads is None:
            raise RuntimeError("write_turn called without mark_wake")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        wav_path = self.record_dir / f"{stamp}.wav"
        samples = stereo_to_mono(b"".join(self.turn_reads))
        with wave.open(str(wav_path), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(RATE)
            out.writeframes(samples.tobytes())

        sidecar = {
            **heard,
            "intent": map_intent(heard["text"]) if heard["text"] else None,
            "wake_offset_secs": self.preroll_bytes / STEREO_BYTES_PER_SAMPLE / RATE,
            "expected": None,
        }
        wav_path.with_suffix(".json").write_text(json.dumps(sidecar, indent=2))
        self.turn_reads = None
        return wav_path
