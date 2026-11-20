import collections
import json
from dataclasses import replace

import numpy as np

from dome_voice.intent_mapper import command_words
from dome_voice.runtime import (
    CHUNK,
    LiveBandpass,
    VoiceRuntime,
    apply_gain,
    capture_command,
    load_voice_runtime_config,
    make_live_filter,
    read_mono_chunk,
    wait_for_wake,
    wake_skip_chunks,
)


class FakeStream:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def read(self, _size):
        if not self.chunks:
            return b""
        return self.chunks.pop(0)


class FakeWakeModel:
    def __init__(self, scores):
        self.scores = list(scores)

    def predict(self, _chunk):
        score = self.scores.pop(0) if self.scores else 0.0
        return {"alexa": score}


class FakeRecognizer:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def SetWords(self, _enabled):
        pass

    def AcceptWaveform(self, _data):
        self.calls += 1
        return self.calls >= 2

    def Result(self):
        return json.dumps({"text": self.text})

    def FinalResult(self):
        return json.dumps({"text": self.text})


class FakeVosk:
    def __init__(self, text):
        self.text = text
        self.grammar = None

    def KaldiRecognizer(self, _model, _rate, grammar=None):
        self.grammar = grammar
        return FakeRecognizer(self.text)


def stereo_chunk(left, right=None, n=CHUNK):
    if right is None:
        right = left
    stereo = np.column_stack(
        [
            np.full(n, left, dtype=np.int16),
            np.full(n, right, dtype=np.int16),
        ]
    )
    return stereo.tobytes()


def test_runtime_module_has_no_ros_import():
    from dome_voice import runtime

    assert not hasattr(runtime, "rclpy")


def stereo_chunks(mono: np.ndarray) -> list[bytes]:
    stereo = np.column_stack([mono, mono]).astype(np.int16)
    return [stereo[i : i + CHUNK].tobytes() for i in range(0, len(mono), CHUNK)]


def test_read_mono_chunk_averages_channels():
    left = np.full(CHUNK, 100, dtype=np.int16)
    right = np.full(CHUNK, 300, dtype=np.int16)
    stereo = np.column_stack([left, right])
    chunk = read_mono_chunk(FakeStream([stereo.tobytes()]))

    assert chunk.shape == (CHUNK,)
    assert np.all(chunk == 200)


def test_read_mono_chunk_has_no_jump_at_chunk_boundaries():
    t_s = np.arange(4 * CHUNK) / 16000
    mono = (1000 + 500 * np.sin(2 * np.pi * 3 * t_s)).astype(np.int16)
    stream = FakeStream(stereo_chunks(mono))
    out = np.concatenate([read_mono_chunk(stream) for _ in range(4)])

    assert np.array_equal(out, mono)


def test_live_filter_removes_dc_without_boundary_clicks():
    t_s = np.arange(20 * CHUNK) / 16000
    mono = (1000 + 300 * np.sin(2 * np.pi * 440 * t_s)).astype(np.int16)
    stream = FakeStream(stereo_chunks(mono))
    live_filter = LiveBandpass(120, 4000)
    out = np.concatenate(
        [read_mono_chunk(stream, CHUNK, live_filter) for _ in range(20)]
    ).astype(np.float32)
    settled = out[10 * CHUNK :]
    jumps = np.abs(np.diff(settled))
    boundary_jumps = jumps[CHUNK - 1 :: CHUNK]

    assert abs(float(np.mean(settled))) < 5.0
    assert boundary_jumps.max() <= jumps.max()


def test_make_live_filter_can_be_enabled_and_disabled():
    cfg = load_voice_runtime_config()

    assert isinstance(make_live_filter(cfg), LiveBandpass)
    assert make_live_filter(replace(cfg, live_filter=False)) is None


def test_wait_for_wake_honors_threshold_and_wake_hits():
    cfg = replace(load_voice_runtime_config(), threshold=0.3, wake_hits=2)
    stream = FakeStream(
        [
            stereo_chunk(20),
            stereo_chunk(20),
            stereo_chunk(20),
        ]
    )
    wake = wait_for_wake(
        stream,
        FakeWakeModel([0.2, 0.4, 0.5]),
        "alexa",
        cfg,
        time_fn=lambda: 0.0,
    )

    assert wake["wake_hit"] is True
    assert wake["chunks"] == 3
    assert wake["score"] == 0.5


def test_capture_command_returns_transcript_text():
    cfg = replace(
        load_voice_runtime_config(),
        min_command_secs=0.0,
        command_start_secs=1.0,
        max_command_secs=1.0,
        silence_dbfs=-80.0,
    )
    chunks = [stereo_chunk(0) for _ in range(4)] + [
        stereo_chunk(2000),
        stereo_chunk(2000),
    ]
    vosk = FakeVosk("alexa go forward")

    result = capture_command(
        FakeStream(chunks),
        vosk,
        object(),
        cfg,
        "alexa",
        grammar=list(cfg.grammar),
        noise_window=collections.deque([-50.0], maxlen=50),
        time_fn=lambda: 0.0,
    )

    assert result["text"] == "go forward"
    assert result["raw_text"] == "alexa go forward"
    assert result["empty"] is False
    assert json.loads(vosk.grammar) == list(command_words()) + ["[unk]"]


def test_voice_runtime_next_turn_uses_fake_models():
    cfg = replace(
        load_voice_runtime_config(),
        threshold=0.3,
        wake_hits=1,
        wake_cooldown_secs=0.0,
        min_command_secs=0.0,
        max_command_secs=1.0,
        silence_dbfs=-80.0,
    )
    chunks = (
        [stereo_chunk(10)]
        + [stereo_chunk(0) for _ in range(4)]
        + [
            stereo_chunk(2000),
            stereo_chunk(2000),
        ]
    )
    runtime = VoiceRuntime(
        cfg,
        stream=FakeStream(chunks),
        wake_model=FakeWakeModel([0.6]),
        wake_key="alexa",
        vosk_module=FakeVosk("alexa stop"),
        stt_model=object(),
        time_fn=lambda: 0.0,
    )
    wake_events = []

    turn = runtime.next_turn(on_wake=lambda wake: wake_events.append(wake))

    assert turn.text == "stop"
    assert turn.raw_text == "alexa stop"
    assert turn.empty is False
    assert turn.wake_score == 0.6
    assert len(wake_events) == 1


class RecordingRecognizer(FakeRecognizer):
    def __init__(self, text):
        super().__init__(text)
        self.received: list[np.ndarray] = []

    def AcceptWaveform(self, data):
        self.received.append(np.frombuffer(data, dtype=np.int16))
        return False


class RecordingVosk(FakeVosk):
    def KaldiRecognizer(self, _model, _rate, grammar=None):
        self.recognizer = RecordingRecognizer(self.text)
        return self.recognizer


def capture_with(cfg, chunks, vosk):
    return capture_command(
        FakeStream(chunks),
        vosk,
        object(),
        cfg,
        "alexa",
        grammar=list(cfg.grammar),
        noise_window=collections.deque([-50.0], maxlen=50),
        time_fn=lambda: 0.0,
    )


def test_apply_gain_scales_and_clips():
    samples = np.array([100, -100, 20000, -20000], dtype=np.int16)

    gained = apply_gain(samples, 20.0)

    assert gained.tolist() == [1000, -1000, 32767, -32768]
    assert apply_gain(samples, 0.0).tolist() == samples.tolist()


def test_stt_gain_applies_to_vosk_input_only():
    cfg = replace(
        load_voice_runtime_config(),
        beep_wake_duration=0.0,
        max_command_secs=0.4,
        silence_dbfs=-30.0,
        stt_gain_db=20.0,
    )
    chunks = [stereo_chunk(100)] * 10
    vosk = RecordingVosk("")

    result = capture_with(cfg, chunks, vosk)

    assert all(np.all(chunk == 1000) for chunk in vosk.recognizer.received)
    # 100 is -50 dBFS: still below the -30 dBFS cutoff, as if no gain were applied
    assert result["command_started"] is False


def test_wake_skip_covers_the_wake_beep():
    cfg = replace(load_voice_runtime_config(), beep_wake_duration=0.3)

    assert wake_skip_chunks(cfg) == 6


def test_wake_beep_does_not_start_the_command():
    cfg = replace(
        load_voice_runtime_config(),
        beep_wake_duration=0.3,
        command_start_secs=0.3,
        max_command_secs=1.0,
        silence_dbfs=-40.0,
    )
    beep = [stereo_chunk(8000)] * wake_skip_chunks(cfg)
    chunks = beep + [stereo_chunk(0)] * 10
    vosk = RecordingVosk("")

    result = capture_with(cfg, chunks, vosk)

    assert result["command_started"] is False
    assert all(np.all(chunk == 0) for chunk in vosk.recognizer.received)
