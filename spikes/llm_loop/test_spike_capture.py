#!/usr/bin/env python3
"""
test_spike_capture.py — tests for the F12 spike's capture-until-silence helper.

Author: Pito Salas and Claude Code
Open Source Under MIT license

Run with `python3 -m pytest spikes/llm_loop/`.
"""

import collections
from dataclasses import replace

import numpy as np
from spike_capture import capture_utterance, secs_to_chunks

from dome_voice.runtime import CHUNK, load_voice_runtime_config, wake_skip_chunks

LOUD = 3000
QUIET = 10


class FakeStream:
    def __init__(self, chunks: list[bytes]):
        self.chunks = list(chunks)

    def read(self, _size: int) -> bytes:
        return self.chunks.pop(0) if self.chunks else b""


def stereo(level: int) -> bytes:
    mono = np.full(CHUNK, level, dtype=np.int16)
    return np.column_stack([mono, mono]).tobytes()


def spike_config():
    return replace(
        load_voice_runtime_config(),
        silence_dbfs=-40.0,
        silence_secs=0.4,
        min_command_secs=0.0,
        command_start_secs=1.0,
        max_command_secs=8.0,
        stt_gain_db=0.0,
    )


def run_capture(config, levels: list[int]):
    skip = [stereo(QUIET)] * wake_skip_chunks(config)
    stream = FakeStream(skip + [stereo(level) for level in levels])
    pcm = capture_utterance(stream, config, None, collections.deque())
    return pcm, stream


def test_speech_then_silence_returns_speech_and_stops():
    config = spike_config()
    silence = secs_to_chunks(config.silence_secs)
    pcm, stream = run_capture(config, [LOUD] * 5 + [QUIET] * (silence + 10))
    assert pcm is not None
    assert len(pcm) == (5 + silence) * CHUNK
    assert len(stream.chunks) == 10


def test_no_speech_returns_none():
    config = spike_config()
    pcm, _ = run_capture(config, [QUIET] * 50)
    assert pcm is None


def test_single_loud_chunk_is_not_speech():
    config = spike_config()
    pcm, _ = run_capture(config, [LOUD] + [QUIET] * 50)
    assert pcm is None


def test_capture_stops_at_max_command_secs():
    config = replace(spike_config(), max_command_secs=1.0)
    pcm, _ = run_capture(config, [LOUD] * 100)
    assert len(pcm) == secs_to_chunks(1.0) * CHUNK


def test_gain_is_applied():
    config = replace(spike_config(), stt_gain_db=20.0)
    pcm, _ = run_capture(config, [LOUD] * 5 + [QUIET] * 20)
    assert pcm[0] == LOUD * 10
