#!/usr/bin/env python3
# test_piper_server — the long-lived Piper process and the speech cache
# Author: Pito Salas and Claude Code
# Open Source Under MIT license
"""A small Python script stands in for Piper's `--json-input` mode: it reads
JSON lines, writes a WAV of constant samples to each `output_file`, prints the
path, and appends one line to a starts file each time it launches, so a test
can tell how often "the model was loaded"."""

import struct
import sys

import pytest

from dome_voice.piper_server import (
    PiperServer,
    SpeechCache,
    piper_command,
    split_sentences,
)

RATE = 22050

FAKE_PIPER = """
import json, struct, sys, wave
starts, rate, samples = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
with open(starts, "a") as f:
    f.write("start\\n")
for line in sys.stdin:
    request = json.loads(line)
    if request["text"] == "crash":
        print("model exploded", file=sys.stderr)
        sys.exit(4)
    with wave.open(request["output_file"], "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(struct.pack("<h", len(request["text"])) * samples)
    print(request["output_file"], flush=True)
"""


def fake_piper(tmp_path, rate: int = RATE, samples: int = 100) -> list[str]:
    script = tmp_path / "fake_piper.py"
    script.write_text(FAKE_PIPER)
    starts = tmp_path / "starts.txt"
    return [sys.executable, str(script), str(starts), str(rate), str(samples)]


def starts(tmp_path) -> int:
    return len((tmp_path / "starts.txt").read_text().splitlines())


@pytest.fixture
def server(tmp_path):
    server = PiperServer(fake_piper(tmp_path), RATE, tmp_path)
    yield server
    server.close()


def test_piper_command_reads_json_lines():
    cmd = piper_command("piper", "/tmp/model.onnx", 1.4)
    assert cmd[:3] == ["piper", "--model", "/tmp/model.onnx"]
    assert "--json-input" in cmd
    assert "--output_raw" not in cmd
    assert cmd[cmd.index("--length_scale") + 1] == "1.4"
    assert "--quiet" in cmd


def test_synthesize_returns_the_wavs_samples(server):
    pcm = server.synthesize("hello")
    assert pcm == struct.pack("<h", 5) * 100


def test_one_process_serves_every_request(server, tmp_path):
    """The point of F15: the model loads once, not per announcement."""
    for text in ["one", "two", "three"]:
        server.synthesize(text)
    assert starts(tmp_path) == 1


def test_wav_files_are_deleted_after_reading(server, tmp_path):
    server.synthesize("hello")
    assert list(tmp_path.glob("dome_speech_*.wav")) == []


def test_piper_exiting_raises_with_its_stderr(server):
    with pytest.raises(RuntimeError, match=r"piper exited \(4\): model exploded"):
        server.synthesize("crash")


def test_writing_after_piper_exited_raises(server):
    with pytest.raises(RuntimeError):
        server.synthesize("crash")
    with pytest.raises(RuntimeError, match="piper exited"):
        server.synthesize("hello")


def test_wrong_sample_rate_raises(tmp_path):
    server = PiperServer(fake_piper(tmp_path, rate=16000), RATE, tmp_path)
    try:
        with pytest.raises(RuntimeError, match="expected \\(1, 2, 22050\\)"):
            server.synthesize("hello")
    finally:
        server.close()


def test_close_stops_piper(server):
    server.close()
    assert server.proc.poll() is not None


def test_close_twice_is_harmless(server):
    server.close()
    server.close()


def test_cache_returns_what_was_put():
    cache = SpeechCache(size=2)
    cache.put("a", b"1")
    assert cache.get("a") == b"1"
    assert cache.get("b") is None


def test_cache_drops_the_least_recently_used():
    cache = SpeechCache(size=2)
    cache.put("a", b"1")
    cache.put("b", b"2")
    cache.get("a")
    cache.put("c", b"3")
    assert cache.get("b") is None
    assert cache.get("a") == b"1"
    assert cache.get("c") == b"3"


def test_split_sentences_at_end_punctuation():
    text = "Why did the robot cross the road? It was programmed to. Ha!"
    assert split_sentences(text) == [
        "Why did the robot cross the road?",
        "It was programmed to.",
        "Ha!",
    ]


def test_split_sentences_keeps_decimals_and_commas_whole():
    text = "linear speed 0.2, angular speed 0.7"
    assert split_sentences(text) == [text]


def test_split_sentences_trims_and_drops_empty_parts():
    assert split_sentences("  Hello.   Bye.  ") == ["Hello.", "Bye."]
