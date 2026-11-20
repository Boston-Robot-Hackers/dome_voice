#!/usr/bin/env python3
# publish_wav — publish a recorded turn on /voice/utterance, to test the VM node
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-20
# Updated: 2026-11-20
# Open Source Under MIT license
"""Takes a 16 kHz mono WAV, such as one from `~/voice_recordings`. Those are
saved before any gain, so this applies `stt_gain_db` from the voice YAML,
the same as the live robot side does.

python3 spikes/llm_loop/publish_wav.py ~/voice_recordings/<stamp>.wav
"""

import argparse
import array
import time
import wave
from pathlib import Path

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray

from dome_voice import load_voice_runtime_config
from dome_voice.runtime import RATE, apply_gain

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "voice.yaml"
SUBSCRIBER_WAIT_SECS = 5.0


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wav:
        shape = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
        if shape != (1, 2, RATE):
            raise ValueError(
                f"{path}: need mono 16-bit {RATE} Hz, got channels/width/rate = {shape}"
            )
        return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("wav", type=Path)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    config = load_voice_runtime_config(args.config)
    pcm = apply_gain(read_wav(args.wav), config.stt_gain_db)

    rclpy.init()
    node = Node("llm_spike_wav")
    publisher = node.create_publisher(UInt8MultiArray, "/voice/utterance", 10)
    deadline = time.monotonic() + SUBSCRIBER_WAIT_SECS
    while publisher.get_subscription_count() == 0:
        if time.monotonic() > deadline:
            raise RuntimeError("No subscriber on /voice/utterance; is the VM node up?")
        time.sleep(0.1)
    msg = UInt8MultiArray()
    msg.data = array.array("B", pcm.tobytes())
    publisher.publish(msg)
    node.get_logger().info(f"Published {len(pcm) / RATE:.1f} s from {args.wav}")
    time.sleep(0.5)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
