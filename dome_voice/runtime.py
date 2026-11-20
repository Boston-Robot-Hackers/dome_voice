#!/usr/bin/env python3
"""
runtime.py — ROS-free voice pipeline: wake detection, STT, and turn capture.

Author: Pito Salas and Claude Code
Open Source Under MIT license
"""

import argparse
import collections
import json
import math
import os
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dome_voice.intent_mapper import command_words
from dome_voice.turn_recorder import RATE, TurnRecorder, stereo_to_mono

CHUNK = 1280
WAKE_SKIP_CHUNKS = 2  # wake word tail and aplay start-up, on top of the beep itself
FLOOR_MAX_DBFS = -25.0

VOSK_MODEL_PATHS = {
    "small": "~/models/vosk-model-small-en-us-0.15",
    "large": "~/models/vosk-model-en-us-0.22",
}


class StrictModel(BaseModel):
    """Rejects unknown keys, so a misspelled YAML key fails loudly."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def none_if_blank(value: Any) -> Any:
    """YAML spellings of "no value" for optional floats: none, None, or empty."""
    return None if value in ("", "none", "None") else value


class StreamSettings(StrictModel):
    wake_word: str = "alexa"
    threshold: float = Field(0.3, ge=0.0, le=1.0)
    wake_hits: int = Field(1, ge=1)
    wake_cooldown_secs: float = Field(1.5, ge=0.0)
    live_filter: bool = True
    vosk_model: str = "small"
    silence_dbfs: float | None = None
    silence_margin: float = 5.0
    silence_secs: float = Field(1.0, gt=0.0)
    min_command_secs: float = Field(0.4, ge=0.0)
    command_start_secs: float = Field(2.5, gt=0.0)
    max_command_secs: float = Field(8.0, gt=0.0)
    stt_gain_db: float = 0.0
    record_dir: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_grammar(cls, values: Any) -> Any:
        """`grammar` was a key before F03; say where it went instead of 'extra'."""
        if isinstance(values, dict) and "grammar" in values:
            raise ValueError(
                "stream_settings.grammar is no longer a setting: the grammar is "
                "derived from PHRASE_INTENTS in dome_voice/intent_mapper.py"
            )
        return values

    @field_validator("silence_dbfs", "record_dir", mode="before")
    @classmethod
    def blank_optional(cls, value: Any) -> Any:
        return none_if_blank(value)


class SoxChain(StrictModel):
    """Bandpass cutoffs in Hz; none (or <= 0) turns that side off."""

    highpass: float | None = 120.0
    lowpass: float | None = 4000.0

    @field_validator("highpass", "lowpass", mode="before")
    @classmethod
    def blank_cutoff(cls, value: Any) -> Any:
        return none_if_blank(value)


class BeepSettings(StrictModel):
    wake_freq: int = 880
    wake_duration: float = 0.3
    wake_volume: float = Field(1.0, ge=0.0, le=1.0)
    intent_freq: int = 330
    intent_duration: float = 0.02
    intent_volume: float = Field(1.0, ge=0.0, le=1.0)
    fail_freq: int = 220
    fail_duration: float = 0.6
    fail_volume: float = Field(1.0, ge=0.0, le=1.0)


class SpeechSettings(StrictModel):
    """speech_output's settings; the Piper paths stay in the environment (F13)."""

    gain: float = Field(0.25, gt=0.0)  # Piper peaks at full scale, so > 1.0 clips
    length_scale: float = Field(1.0, gt=0.0)  # above 1.0 speaks slower
    alsa_device: str = "plughw:0,0"  # "" = ALSA's default device


class VoiceConfigFile(StrictModel):
    """The voice YAML's shape, and the only place voice defaults are written.

    A YAML file overrides just the keys it names; everything else keeps the
    default here. The shape mirrors `~/tune`'s active.yaml, so tune results
    can be pasted into `config/voice.yaml` directly.
    """

    capture_card: int = 0
    playback_card: int = 0
    stream_settings: StreamSettings = Field(default_factory=StreamSettings)
    sox_chain: SoxChain = Field(default_factory=SoxChain)
    beep: BeepSettings = Field(default_factory=BeepSettings)
    speech: SpeechSettings = Field(default_factory=SpeechSettings)

    def to_runtime_config(self, source_path: str) -> "VoiceRuntimeConfig":
        beeps = {f"beep_{k}": v for k, v in self.beep.model_dump().items()}
        return VoiceRuntimeConfig(
            source_path=source_path,
            capture_card=self.capture_card,
            playback_card=self.playback_card,
            **self.stream_settings.model_dump(),
            **self.sox_chain.model_dump(),
            **beeps,
        )


@dataclass(frozen=True)
class VoiceRuntimeConfig:
    """The flat, resolved config the runtime and node read.

    Built only by `VoiceConfigFile.to_runtime_config`, so it has no defaults
    of its own. Tests derive variants with `dataclasses.replace`.
    """

    source_path: str
    capture_card: int
    playback_card: int
    wake_word: str
    threshold: float
    wake_hits: int
    wake_cooldown_secs: float
    live_filter: bool
    highpass: float | None
    lowpass: float | None
    vosk_model: str
    silence_dbfs: float | None
    silence_margin: float
    silence_secs: float
    min_command_secs: float
    command_start_secs: float
    max_command_secs: float
    stt_gain_db: float
    record_dir: str | None
    beep_wake_freq: int
    beep_wake_duration: float
    beep_wake_volume: float
    beep_intent_freq: int
    beep_intent_duration: float
    beep_intent_volume: float
    beep_fail_freq: int
    beep_fail_duration: float
    beep_fail_volume: float

    @property
    def grammar(self) -> tuple[str, ...]:
        return command_words()

    @property
    def vosk_model_path(self) -> str:
        model_path = VOSK_MODEL_PATHS.get(self.vosk_model, self.vosk_model)
        return os.path.expanduser(model_path)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["grammar"] = list(self.grammar)
        data["vosk_model_path"] = self.vosk_model_path
        return data


@dataclass(frozen=True)
class VoiceTurn:
    """One completed or timed-out voice interaction."""

    text: str = ""
    raw_text: str = ""
    wake_score: float = 0.0
    wake_elapsed_ms: int = 0
    command_elapsed_ms: int = 0
    empty: bool = True
    metadata: dict[str, Any] | None = None


class LiveBandpass:
    """Tiny streaming highpass/lowpass filter matching the tuned SoX cutoffs."""

    def __init__(self, highpass_hz: float | None, lowpass_hz: float | None):
        self.highpass_hz = highpass_hz if highpass_hz and highpass_hz > 0 else None
        self.lowpass_hz = lowpass_hz if lowpass_hz and lowpass_hz > 0 else None
        self.hp_x = 0.0
        self.hp_y = 0.0
        self.lp_y = 0.0

        dt = 1.0 / RATE
        self.hp_alpha = None
        self.lp_alpha = None
        if self.highpass_hz:
            rc = 1.0 / (2.0 * math.pi * self.highpass_hz)
            self.hp_alpha = rc / (rc + dt)
        if self.lowpass_hz:
            rc = 1.0 / (2.0 * math.pi * self.lowpass_hz)
            self.lp_alpha = dt / (rc + dt)

    def process(self, samples: np.ndarray) -> np.ndarray:
        x = samples.astype(np.float32)
        if self.hp_alpha is not None:
            y = np.empty_like(x)
            prev_x = self.hp_x
            prev_y = self.hp_y
            alpha = self.hp_alpha
            for i, sample in enumerate(x):
                prev_y = alpha * (prev_y + sample - prev_x)
                prev_x = float(sample)
                y[i] = prev_y
            self.hp_x = prev_x
            self.hp_y = prev_y
            x = y

        if self.lp_alpha is not None:
            y = np.empty_like(x)
            prev_y = self.lp_y
            alpha = self.lp_alpha
            for i, sample in enumerate(x):
                prev_y = prev_y + alpha * (float(sample) - prev_y)
                y[i] = prev_y
            self.lp_y = prev_y
            x = y

        return np.clip(x, -32768, 32767).astype(np.int16)


class VoiceRuntime:
    """Production voice loop with no ROS imports."""

    def __init__(
        self,
        config: VoiceRuntimeConfig | None = None,
        stream=None,
        wake_model=None,
        wake_key: str = "",
        vosk_module=None,
        stt_model=None,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        self.config = config or load_voice_runtime_config()
        self.stream = stream
        self.wake_model = wake_model
        self.wake_key = wake_key
        self.vosk_module = vosk_module
        self.stt_model = stt_model
        self.time_fn = time_fn
        self.live_filter = make_live_filter(self.config)
        self.recorder: TurnRecorder | None = None
        self._arecord_process = None

    def next_turn(
        self,
        ok_fn: Callable[[], bool] = lambda: True,
        wake_timeout_s: float | None = None,
        on_wake: Callable[[dict[str, Any]], None] | None = None,
    ) -> VoiceTurn:
        self._ensure_ready()
        wake = wait_for_wake(
            self.stream,
            self.wake_model,
            self.wake_key,
            self.config,
            live_filter=self.live_filter,
            ok_fn=ok_fn,
            timeout_s=wake_timeout_s,
            time_fn=self.time_fn,
            cooldown_s=self.config.wake_cooldown_secs,
        )
        if not wake["wake_hit"]:
            return VoiceTurn(
                wake_score=wake["score"],
                wake_elapsed_ms=wake["elapsed_ms"],
                metadata={"wake": wake},
            )
        if self.recorder:
            self.recorder.mark_wake()
        if on_wake:
            on_wake(wake)

        command = capture_command(
            self.stream,
            self.vosk_module,
            self.stt_model,
            self.config,
            self.config.wake_word,
            grammar=list(self.config.grammar),
            live_filter=self.live_filter,
            noise_window=wake["noise_window"],
            time_fn=self.time_fn,
        )
        turn = VoiceTurn(
            text=command["text"],
            raw_text=command["raw_text"],
            wake_score=wake["score"],
            wake_elapsed_ms=wake["elapsed_ms"],
            command_elapsed_ms=command["elapsed_ms"],
            empty=command["empty"],
            metadata={"wake": wake, "command": command},
        )
        if self.recorder:
            self.recorder.write_turn(heard_summary(turn, self.config))
        return turn

    def close(self) -> None:
        if self._arecord_process is not None:
            _terminate_process(self._arecord_process)
            self._arecord_process = None
        self.stream = None
        self.recorder = None

    def _ensure_ready(self) -> None:
        if self.stream is None:
            proc = open_arecord(self.config.capture_card)
            if proc.stdout is None:
                raise RuntimeError("arecord stdout unavailable")
            self.stream = proc.stdout
            self._arecord_process = proc
        if self.config.record_dir and self.recorder is None:
            self.recorder = TurnRecorder(
                self.stream, Path(self.config.record_dir).expanduser(), CHUNK * 4
            )
            self.stream = self.recorder
        if self.wake_model is None or not self.wake_key:
            self.wake_model, self.wake_key = load_wake_model(self.config.wake_word)
        if self.vosk_module is None or self.stt_model is None:
            self.vosk_module, self.stt_model = load_stt_model(self.config.vosk_model)


def heard_summary(turn: VoiceTurn, config: VoiceRuntimeConfig) -> dict[str, Any]:
    """What the pipeline heard in one turn, for a recording's JSON sidecar."""
    wake = turn.metadata["wake"]
    command = turn.metadata["command"]
    return {
        "text": turn.text,
        "raw_text": turn.raw_text,
        "empty": turn.empty,
        "wake_score": turn.wake_score,
        "wake_max_score": wake["max_score"],
        "command_started": command["command_started"],
        "floor_dbfs": command["floor"],
        "cutoff_dbfs": command["cutoff"],
        "command_elapsed_ms": turn.command_elapsed_ms,
        "config": config.source_path,
    }


def load_voice_runtime_config(
    path: str | os.PathLike[str] | None = None,
    overrides: dict[str, Any] | None = None,
) -> VoiceRuntimeConfig:
    """Load the voice config: the defaults, then a YAML, then overrides.

    The YAML is `path`; with none, the defaults in `VoiceConfigFile` are used
    as they are. No environment variable chooses the file (see dome2's
    stack/config_conventions.md). A named file that does not exist raises:
    silently running on the defaults would hide a wrong path. `overrides` uses the flat names (`threshold`,
    `beep_wake_freq`, ...); a `None` value means "not given".
    """
    config_path = Path(path).expanduser() if path else None
    if config_path is None:
        file_data: dict[str, Any] = {}
        source_path = "defaults"
    else:
        file_data = read_yaml(config_path)
        source_path = str(config_path)
    for key, value in (overrides or {}).items():
        if value is not None:
            set_flat_key(file_data, key, value)
    return VoiceConfigFile.model_validate(file_data).to_runtime_config(source_path)


def load_speech_settings(path: str | os.PathLike[str]) -> SpeechSettings:
    """speech_output's settings from the voice YAML: the defaults, then the file.

    Goes through the whole `VoiceConfigFile`, so a bad key anywhere in the
    file fails here too, not only when voice_input loads it.
    """
    file_data = read_yaml(Path(path).expanduser())
    return VoiceConfigFile.model_validate(file_data).speech


def set_flat_key(file_data: dict[str, Any], key: str, value: Any) -> None:
    """Put a flat override (`threshold`, `beep_fail_freq`) in its YAML section."""
    if key in VoiceConfigFile.model_fields:
        file_data[key] = value
        return
    sections = (
        ("stream_settings", StreamSettings, key),
        ("sox_chain", SoxChain, key),
        ("beep", BeepSettings, key.removeprefix("beep_")),
    )
    for section, model, field in sections:
        if field in model.model_fields and (section != "beep" or key != field):
            file_data.setdefault(section, {})[field] = value
            return
    raise ValueError(f"unknown voice config override: {key!r}")


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


def make_live_filter(config: VoiceRuntimeConfig) -> LiveBandpass | None:
    if not config.live_filter:
        return None
    return LiveBandpass(config.highpass, config.lowpass)


def read_mono_chunk(
    stream,
    n_samples: int = CHUNK,
    live_filter: LiveBandpass | None = None,
) -> np.ndarray | None:
    raw = stream.read(n_samples * 4)
    if len(raw) < n_samples * 4:
        return None
    chunk = stereo_to_mono(raw)
    if live_filter:
        chunk = live_filter.process(chunk)
    return chunk


def rms_dbfs(samples: np.ndarray) -> float:
    rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
    return 20 * math.log10(rms / 32768) if rms > 0 else -96.0


def noise_floor(samples: collections.deque[float] | list[float]) -> float | None:
    quiet = [value for value in samples if value <= FLOOR_MAX_DBFS]
    values = quiet or list(samples)
    if not values:
        return None
    return float(np.percentile(values, 20))


def silence_cutoff(
    noise_floor_value: float | None,
    override: float | None,
    margin: float,
) -> float:
    if override is not None:
        return override
    if noise_floor_value is None:
        return -38.0
    return min(noise_floor_value + margin, -22.0)


def apply_gain(samples: np.ndarray, gain_db: float) -> np.ndarray:
    scaled = samples.astype(np.float32) * 10 ** (gain_db / 20)
    return np.clip(scaled, -32768, 32767).astype(np.int16)


def wake_skip_chunks(config: VoiceRuntimeConfig) -> int:
    """Chunks to drop after wake so the wake beep doesn't start the command."""
    return WAKE_SKIP_CHUNKS + math.ceil(config.beep_wake_duration * RATE / CHUNK)


def clean_transcript(text: str, wake_word: str) -> str:
    words = text.split()
    wake_words = wake_word.replace("_", " ").split()
    if words[: len(wake_words)] == wake_words:
        return " ".join(words[len(wake_words) :]).strip()
    return text


def open_arecord(card: int) -> subprocess.Popen:
    return subprocess.Popen(
        [
            "arecord",
            "-q",
            "-D",
            f"hw:{card},0",
            "-f",
            "S16_LE",
            "-r",
            str(RATE),
            "-c",
            "2",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=CHUNK * 4,
    )


def wait_for_wake(
    stream,
    wake_model,
    wake_key: str,
    config: VoiceRuntimeConfig,
    live_filter: LiveBandpass | None = None,
    ok_fn: Callable[[], bool] = lambda: True,
    timeout_s: float | None = None,
    time_fn: Callable[[], float] = time.monotonic,
    cooldown_s: float = 0.0,
) -> dict[str, Any]:
    # Flush pipe AND model sliding window before scoring — prevents both stale
    # buffered audio and residual OWW activations from the previous "alexa" from
    # immediately re-triggering after a turn completes.
    if cooldown_s > 0:
        drain_end = time_fn() + cooldown_s
        while ok_fn() and time_fn() < drain_end:
            chunk = read_mono_chunk(stream, CHUNK, live_filter)
            if chunk is None:
                break
            wake_model.predict(chunk)

    noise_window: collections.deque[float] = collections.deque(maxlen=50)
    scores: list[float] = []
    wake_hits = 0
    chunks = 0
    start = time_fn()

    while ok_fn():
        if timeout_s is not None and time_fn() - start >= timeout_s:
            break
        chunk = read_mono_chunk(stream, CHUNK, live_filter)
        if chunk is None:
            break
        chunks += 1
        chunk_dbfs = rms_dbfs(chunk)
        score = float(wake_model.predict(chunk).get(wake_key, 0.0))
        scores.append(score)

        if score < config.threshold:
            noise_window.append(chunk_dbfs)
            wake_hits = 0
            continue

        wake_hits += 1
        if wake_hits < config.wake_hits:
            continue

        return {
            "wake_hit": True,
            "score": round(score, 6),
            "chunks": chunks,
            "elapsed_ms": round((time_fn() - start) * 1000),
            "max_score": round(max(scores), 6) if scores else 0.0,
            "noise_window": noise_window,
        }

    return {
        "wake_hit": False,
        "score": 0.0,
        "chunks": chunks,
        "elapsed_ms": round((time_fn() - start) * 1000),
        "max_score": round(max(scores), 6) if scores else 0.0,
        "noise_window": noise_window,
    }


def capture_command(
    stream,
    vosk_module,
    stt_model,
    config: VoiceRuntimeConfig,
    wake_word: str,
    grammar: list[str] | None = None,
    live_filter: LiveBandpass | None = None,
    noise_window: collections.deque[float] | None = None,
    time_fn: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    floor = noise_floor(noise_window or [])
    cutoff = silence_cutoff(floor, config.silence_dbfs, config.silence_margin)
    for _ in range(wake_skip_chunks(config)):
        read_mono_chunk(stream, CHUNK, live_filter)

    grammar_json = json.dumps((grammar or []) + ["[unk]"]) if grammar else None
    if grammar_json:
        rec = vosk_module.KaldiRecognizer(stt_model, RATE, grammar_json)
    else:
        rec = vosk_module.KaldiRecognizer(stt_model, RATE)
    rec.SetWords(True)

    silence_limit_chunks = max(1, math.ceil(config.silence_secs * RATE / CHUNK))
    min_cmd_chunks = max(1, math.ceil(config.min_command_secs * RATE / CHUNK))
    start_limit_chunks = max(1, math.ceil(config.command_start_secs * RATE / CHUNK))
    max_cmd_chunks = max(1, math.ceil(config.max_command_secs * RATE / CHUNK))

    silence_chunks = 0
    speech_chunks = 0
    command_started = False
    final_text = ""
    start = time_fn()

    for chunk_idx in range(max_cmd_chunks):
        cmd_chunk = read_mono_chunk(stream, CHUNK, live_filter)
        if cmd_chunk is None:
            break

        chunk_is_speech = rms_dbfs(cmd_chunk) > cutoff
        if chunk_is_speech:
            speech_chunks += 1
            silence_chunks = 0
            if speech_chunks >= 2:
                command_started = True
        else:
            speech_chunks = 0
            silence_chunks += 1

        endpoint = rec.AcceptWaveform(
            apply_gain(cmd_chunk, config.stt_gain_db).tobytes()
        )
        if endpoint:
            result = json.loads(rec.Result())
            final_text = result.get("text", "").strip()
            if command_started and final_text and chunk_idx >= min_cmd_chunks:
                break

        if not command_started and chunk_idx >= start_limit_chunks:
            break
        if (
            command_started
            and chunk_idx >= min_cmd_chunks
            and silence_chunks >= silence_limit_chunks
        ):
            break

    if not final_text:
        final_text = json.loads(rec.FinalResult()).get("text", "").strip()

    text = clean_transcript(final_text, wake_word)
    return {
        "text": text,
        "raw_text": final_text,
        "empty": not bool(text),
        "command_started": command_started,
        "floor": floor,
        "cutoff": cutoff,
        "elapsed_ms": round((time_fn() - start) * 1000),
    }


def load_wake_model(model_name: str):
    import warnings

    saved = _suppress_fd2()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from openwakeword.model import Model as OWWModel
        oww = OWWModel(wakeword_model_paths=[_resolve_oww_model(model_name)])
    finally:
        _restore_fd2(saved)

    model_key = next(
        key
        for key in oww.models
        if key not in {"embedding_model", "melspectrogram", "silero_vad"}
    )
    return oww, model_key


def load_stt_model(model_key: str):
    import vosk

    vosk.SetLogLevel(-1)
    model_path = VOSK_MODEL_PATHS.get(model_key, model_key)
    model_path = os.path.expanduser(model_path)
    if not os.path.isdir(model_path):
        raise RuntimeError(f"Vosk model not found: {model_path}")
    return vosk, vosk.Model(model_path)


def _resolve_oww_model(name: str) -> str:
    if os.path.isabs(name) and os.path.exists(name):
        return name

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import openwakeword
    models_dir = os.path.join(
        os.path.dirname(openwakeword.__file__), "resources", "models"
    )
    utility_models = {"embedding_model", "melspectrogram", "silero_vad"}
    candidates = [
        fname
        for fname in os.listdir(models_dir)
        if fname.endswith(".onnx") and os.path.splitext(fname)[0] not in utility_models
    ]
    for fname in candidates:
        stem = os.path.splitext(fname)[0]
        if stem == name or stem.startswith(name + "_"):
            return os.path.join(models_dir, fname)
    names = [os.path.splitext(fname)[0] for fname in candidates]
    raise RuntimeError(
        f"Wake word model '{name}' not found. Available: {', '.join(sorted(names))}"
    )


def _suppress_fd2() -> int:
    saved = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 2)
    os.close(devnull)
    return saved


def _restore_fd2(saved: int) -> None:
    os.dup2(saved, 2)
    os.close(saved)


def _terminate_process(proc) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        proc.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run tuned voice runtime smoke test")
    parser.add_argument("--config", help="Path to tune active.yaml or preset YAML")
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--wake-hits", type=int)
    parser.add_argument("--wake-word")
    parser.add_argument(
        "--trials", type=int, default=0, help="Run this many voice turns"
    )
    args = parser.parse_args()

    config = load_voice_runtime_config(
        args.config,
        overrides={
            "threshold": args.threshold,
            "wake_hits": args.wake_hits,
            "wake_word": args.wake_word,
        },
    )
    if args.trials <= 0:
        print(json.dumps(config.to_dict(), indent=2, sort_keys=True))
        return

    runtime = VoiceRuntime(config)
    try:
        hits = 0
        empties = 0
        latencies: list[int] = []
        for trial in range(args.trials):
            print(
                f"Trial {trial + 1}/{args.trials}: listening for {config.wake_word!r}"
            )
            turn = runtime.next_turn()
            hits += int(turn.wake_score >= config.threshold)
            empties += int(turn.empty)
            latencies.append(turn.command_elapsed_ms)
            print(
                json.dumps(
                    {
                        "text": turn.text,
                        "raw_text": turn.raw_text,
                        "wake_score": turn.wake_score,
                        "empty": turn.empty,
                        "command_elapsed_ms": turn.command_elapsed_ms,
                    },
                    sort_keys=True,
                )
            )
        median_latency = int(np.median(latencies)) if latencies else 0
        print(
            json.dumps(
                {
                    "trials": args.trials,
                    "wake_hits": hits,
                    "empty_count": empties,
                    "median_latency_ms": median_latency,
                },
                sort_keys=True,
            )
        )
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
