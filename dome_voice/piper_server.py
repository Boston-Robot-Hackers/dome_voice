#!/usr/bin/env python3
# piper_server — one long-lived Piper process, and a cache of what it has said
# Author: Pito Salas and Claude Code
# Open Source Under MIT license
"""ROS-free speech synthesis for `speech_output` (F15).

**`PiperServer` keeps one Piper process running**, so the voice model loads
once instead of on every announcement (about 0.6 s on the robot, measured in
TF15.0). Piper runs in `--json-input` mode: each request is one JSON line,
`{"text": ..., "output_file": ...}`, and Piper prints the file's path when
the WAV is written. That printed line is the only "done" signal Piper
gives, so requests are strictly one at a time. The WAVs go to `/dev/shm`
(RAM), and each is deleted once read.

A WAV arrives only when its whole text is synthesised, so **the caller
splits text into sentences** (`split_sentences`) and plays one while the
next is made. That keeps the old streaming path's early start on
multi-sentence replies (history.md: first audio about 1.3 s instead of
2.2 s) without reloading the model.

**`SpeechCache` keeps the audio of recent sentences**, so a repeated one
(a status reply, say) plays without synthesis. Its key is the text alone,
which is right because the voice and length scale are fixed for the life of
the node.
"""

import itertools
import json
import re
import subprocess
import wave
from collections import OrderedDict
from pathlib import Path

SPEECH_DIR = Path("/dev/shm")
CACHE_SIZE = 32
CLOSE_TIMEOUT_S = 2.0
# A sentence ends at . ! or ? followed by whitespace, so "0.2" stays whole.
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    """`text` as its sentences, in order, without surrounding whitespace."""
    return [part for part in SENTENCE_BREAK.split(text.strip()) if part]


def piper_command(piper_bin: str, model_path: str, length_scale: float) -> list[str]:
    """Piper reading JSON lines on stdin and printing each WAV path when written."""
    return [
        piper_bin,
        "--model",
        model_path,
        "--json-input",
        "--length_scale",
        str(length_scale),
        "--quiet",
    ]


class PiperServer:
    """A running Piper: `synthesize` turns text into int16 mono PCM bytes."""

    def __init__(self, command: list[str], sample_rate: int, out_dir: Path):
        self.sample_rate = sample_rate
        self.out_dir = out_dir
        self.file_numbers = itertools.count()
        # Unbuffered: a write that fails because Piper died leaves nothing
        # behind for Python to flush into the dead pipe later.
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )

    def synthesize(self, text: str) -> bytes:
        out_path = (
            self.out_dir / f"dome_speech_{self.proc.pid}_{next(self.file_numbers)}.wav"
        )
        request = {"text": text, "output_file": str(out_path)}
        try:
            self.proc.stdin.write((json.dumps(request) + "\n").encode())
        except BrokenPipeError:
            self.raise_exited()
        done_path = self.proc.stdout.readline().decode().strip()
        if not done_path:
            self.raise_exited()
        if done_path != str(out_path):
            raise RuntimeError(f"piper wrote {done_path!r}, expected {str(out_path)!r}")
        try:
            return self.read_pcm(out_path)
        finally:
            out_path.unlink(missing_ok=True)

    def read_pcm(self, path: Path) -> bytes:
        """The WAV's samples, after checking they are int16 mono at our rate."""
        with wave.open(str(path), "rb") as wav:
            shape = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
            if shape != (1, 2, self.sample_rate):
                raise RuntimeError(
                    f"piper wrote {shape} (channels, bytes per sample, rate); "
                    f"expected (1, 2, {self.sample_rate})"
                )
            return wav.readframes(wav.getnframes())

    def raise_exited(self) -> None:
        code = self.proc.wait()
        err = self.proc.stderr.read().decode(errors="replace").strip()
        raise RuntimeError(f"piper exited ({code}): {err}")

    def close(self) -> None:
        """Stop Piper: end its input, then kill it if it doesn't exit in time."""
        if self.proc.poll() is not None:
            return
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=CLOSE_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


class SpeechCache:
    """Most-recently-used audio for up to `size` texts."""

    def __init__(self, size: int = CACHE_SIZE):
        self.size = size
        self.audio_by_text: OrderedDict[str, bytes] = OrderedDict()

    def get(self, text: str) -> bytes | None:
        pcm = self.audio_by_text.get(text)
        if pcm is not None:
            self.audio_by_text.move_to_end(text)
        return pcm

    def put(self, text: str, pcm: bytes) -> None:
        self.audio_by_text[text] = pcm
        self.audio_by_text.move_to_end(text)
        if len(self.audio_by_text) > self.size:
            self.audio_by_text.popitem(last=False)
