#!/usr/bin/env python3
# utterance_capture — the LLM path's turn: wake word, then raw PCM, no STT
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-20
# Updated: 2026-11-20
# Open Source Under MIT license
"""After a wake, `capture_utterance` reads mono chunks until the speaker stops,
using the same start and silence rules as `runtime.capture_command`, and
returns the audio itself instead of a transcript. The audio gets
`stt_gain_db`, since the mic is quiet (I02) and whatever transcribes it
downstream (Whisper on the VM) needs the same boost.

`next_utterance` composes the two steps for one turn. It lives here, not on
`VoiceRuntime`, so `runtime.py` needn't import this module.
"""

import collections
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from dome_voice.runtime import (
    CHUNK,
    LiveBandpass,
    VoiceRuntime,
    VoiceRuntimeConfig,
    apply_gain,
    noise_floor,
    read_mono_chunk,
    rms_dbfs,
    secs_to_chunks,
    silence_cutoff,
    wake_skip_chunks,
)


@dataclass(frozen=True)
class VoiceUtterance:
    """One LLM-path turn. `pcm` is None when the wake fired but no one spoke."""

    is_woken: bool
    pcm: np.ndarray | None
    wake: dict[str, Any]


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


def next_utterance(
    runtime: VoiceRuntime,
    ok_fn: Callable[[], bool],
    on_wake: Callable[[dict[str, Any]], None],
    is_muted_fn: Callable[[], bool],
) -> VoiceUtterance:
    """Wait for the wake word, call `on_wake` (the beep), then capture."""
    wake = runtime.wake_up(ok_fn, None, is_muted_fn)
    if not wake["wake_hit"]:
        return VoiceUtterance(False, None, wake)
    on_wake(wake)
    pcm = capture_utterance(
        runtime.stream, runtime.config, runtime.live_filter, wake["noise_window"]
    )
    return VoiceUtterance(True, pcm, wake)
