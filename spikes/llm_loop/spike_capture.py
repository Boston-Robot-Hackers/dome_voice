#!/usr/bin/env python3
"""
spike_capture.py — capture one open-ended utterance as raw PCM, no STT (F12 spike).

Author: Pito Salas and Claude Code
Open Source Under MIT license

After a wake hit, read mono chunks until the speaker stops, using the same
start/silence rules as `runtime.capture_command`, and return the audio itself
instead of a transcript. The audio gets `stt_gain_db`, since the mic is
quiet (I02) and whatever transcribes it downstream needs the same boost.
"""

import collections
import math

import numpy as np

from dome_voice.runtime import (
    CHUNK,
    RATE,
    LiveBandpass,
    VoiceRuntimeConfig,
    apply_gain,
    noise_floor,
    read_mono_chunk,
    rms_dbfs,
    silence_cutoff,
    wake_skip_chunks,
)


def secs_to_chunks(secs: float) -> int:
    return max(1, math.ceil(secs * RATE / CHUNK))


def capture_utterance(
    stream,
    config: VoiceRuntimeConfig,
    live_filter: LiveBandpass | None,
    noise_window: collections.deque[float],
) -> np.ndarray | None:
    """Return the utterance as gained int16 mono at RATE, or None if no speech.

    Speech starts after 2 loud chunks in a row. Capture ends after
    `silence_secs` of quiet (once `min_command_secs` has passed), at
    `max_command_secs`, or at `command_start_secs` if speech never started.
    """
    cutoff = silence_cutoff(
        noise_floor(noise_window), config.silence_dbfs, config.silence_margin
    )
    for _ in range(wake_skip_chunks(config)):
        read_mono_chunk(stream, CHUNK, live_filter)

    silence_limit = secs_to_chunks(config.silence_secs)
    min_chunks = secs_to_chunks(config.min_command_secs)
    start_limit = secs_to_chunks(config.command_start_secs)
    chunks: list[np.ndarray] = []
    speech_run = 0
    silence_run = 0
    is_started = False

    for chunk_idx in range(secs_to_chunks(config.max_command_secs)):
        chunk = read_mono_chunk(stream, CHUNK, live_filter)
        if chunk is None:
            break
        chunks.append(chunk)
        if rms_dbfs(chunk) > cutoff:
            speech_run += 1
            silence_run = 0
            is_started = is_started or speech_run >= 2
        else:
            speech_run = 0
            silence_run += 1
        if not is_started and chunk_idx >= start_limit:
            break
        if is_started and chunk_idx >= min_chunks and silence_run >= silence_limit:
            break

    if not is_started:
        return None
    return apply_gain(np.concatenate(chunks), config.stt_gain_db)
