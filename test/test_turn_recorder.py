#!/usr/bin/env python3
# test_turn_recorder — tests for recording each voice turn to WAV + JSON.
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-20
# Updated: 2026-11-20
# Open Source Under MIT license

import json
import wave
from dataclasses import replace

import numpy as np
import pytest
from test_voice_runtime import FakeStream, FakeVosk, FakeWakeModel, stereo_chunk

from dome_voice.runtime import CHUNK, RATE, VoiceRuntime, load_voice_runtime_config
from dome_voice.turn_recorder import PREROLL_SECS, TurnRecorder


def recording_runtime(chunks, scores, record_dir):
    cfg = replace(
        load_voice_runtime_config(),
        wake_cooldown_secs=0.0,
        min_command_secs=0.0,
        max_command_secs=1.0,
        silence_dbfs=-80.0,
        record_dir=str(record_dir) if record_dir else None,
    )
    stream = FakeStream(chunks)
    runtime = VoiceRuntime(
        cfg,
        stream=stream,
        wake_model=FakeWakeModel(scores),
        wake_key="alexa",
        vosk_module=FakeVosk("alexa stop"),
        stt_model=object(),
        time_fn=lambda: 0.0,
    )
    return runtime, stream


def read_wav(path):
    with wave.open(str(path)) as wav:
        assert (wav.getnchannels(), wav.getframerate()) == (1, RATE)
        return np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)


def test_one_turn_writes_wav_from_before_wake_and_sidecar(tmp_path):
    pre_wake = [stereo_chunk(level) for level in (11, 12, 13)]
    wake_and_command = [stereo_chunk(14)] + [stereo_chunk(2000)] * 6
    runtime, stream = recording_runtime(
        pre_wake + wake_and_command, [0.0, 0.0, 0.0, 0.6], tmp_path
    )

    turn = runtime.next_turn()

    wavs = list(tmp_path.glob("*.wav"))
    assert len(wavs) == 1
    samples = read_wav(wavs[0])
    reads_consumed = len(pre_wake + wake_and_command) - len(stream.chunks)
    assert len(samples) == reads_consumed * CHUNK
    assert samples[0] == 11
    assert samples[3 * CHUNK] == 14

    sidecar = json.loads(wavs[0].with_suffix(".json").read_text())
    assert sidecar["text"] == turn.text == "stop"
    assert sidecar["raw_text"] == "alexa stop"
    assert sidecar["wake_score"] == 0.6
    assert sidecar["intent"]["name"] == "stop"
    assert sidecar["wake_offset_secs"] == pytest.approx(4 * CHUNK / RATE)
    assert sidecar["expected"] is None


def test_preroll_keeps_only_the_last_second(tmp_path):
    pre_wake = [stereo_chunk(level) for level in range(1, 31)]
    chunks = pre_wake + [stereo_chunk(2000)] * 6
    runtime, _ = recording_runtime(chunks, [0.0] * 29 + [0.6], tmp_path)

    runtime.next_turn()

    wav_path = next(tmp_path.glob("*.wav"))
    samples = read_wav(wav_path)
    kept = round(PREROLL_SECS * RATE / CHUNK)
    assert samples[0] == 30 - kept + 1
    sidecar = json.loads(wav_path.with_suffix(".json").read_text())
    assert sidecar["wake_offset_secs"] == pytest.approx(kept * CHUNK / RATE)


def test_no_record_dir_writes_nothing(tmp_path):
    chunks = [stereo_chunk(10)] + [stereo_chunk(2000)] * 6
    runtime, _ = recording_runtime(chunks, [0.6], None)

    runtime.next_turn()

    assert runtime.recorder is None
    assert list(tmp_path.iterdir()) == []


def test_missed_wake_writes_nothing(tmp_path):
    runtime, _ = recording_runtime([stereo_chunk(10)] * 3, [0.0] * 3, tmp_path)

    turn = runtime.next_turn()

    assert turn.empty
    assert list(tmp_path.glob("*.wav")) == []


def test_write_turn_without_wake_raises(tmp_path):
    recorder = TurnRecorder(FakeStream([]), tmp_path, CHUNK * 4)

    with pytest.raises(RuntimeError, match="without mark_wake"):
        recorder.write_turn({"text": ""})
