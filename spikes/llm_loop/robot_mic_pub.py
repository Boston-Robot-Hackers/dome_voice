#!/usr/bin/env python3
"""
robot_mic_pub.py — robot side of the F12 spike: mic → /voice/utterance, /voice/llm_reply → /announcement.

Author: Pito Salas and Claude Code
Open Source Under MIT license

It listens for its own wake word (`--wake-word`), not the fixed grammar's.

Each utterance is published as one `std_msgs/UInt8MultiArray`: int16
little-endian mono PCM at 16 kHz. The VM node transcribes it and answers on
`/voice/llm_reply` as a plain `std_msgs/String`; this node relays that to
`/announcement` for `speech_output`. Doing the relay here means the VM needs
only stock ROS 2, not `dome_control` and its dependencies.

The mic loop blocks, so it runs on the main thread and ROS callbacks spin
on a daemon thread. Run this instead of `voice_input`, because the mic can
only be opened once.

    python3 spikes/llm_loop/robot_mic_pub.py [--config FILE] [--wake-word NAME]
"""

import argparse
import array
import dataclasses
import threading
import time
from pathlib import Path

import rclpy
from dome_control.announcement_contract import PRIORITY_QUERY_REPLY, Announcement
from dome_control.msg import Announcement as AnnouncementMsg
from rclpy.executors import ExternalShutdownException, SingleThreadedExecutor
from rclpy.node import Node
from spike_capture import capture_utterance
from std_msgs.msg import String, UInt8MultiArray

from dome_voice import beep, load_voice_runtime_config
from dome_voice.runtime import (
    RATE,
    load_wake_model,
    make_live_filter,
    open_arecord,
    wait_for_wake,
)

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "voice.yaml"
TOPIC = "/voice/utterance"
REPLY_TOPIC = "/voice/llm_reply"
DEFAULT_WAKE_WORD = "hey_jarvis"  # stands in for "hey robbie"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument(
        "--wake-word",
        default=DEFAULT_WAKE_WORD,
        help="openWakeWord model name, or an absolute .onnx path",
    )
    return parser.parse_args()


def listen_loop(node: Node, publisher, config) -> None:
    """Wake, beep, capture, publish — until ROS shuts down or the mic ends."""
    proc = open_arecord(config.capture_card)
    wake_model, wake_key = load_wake_model(config.wake_word)
    live_filter = make_live_filter(config)
    log = node.get_logger()
    log.info(f"Listening for '{config.wake_word}', publishing on {TOPIC}")
    try:
        while rclpy.ok():
            wake = wait_for_wake(
                proc.stdout,
                wake_model,
                wake_key,
                config,
                live_filter=live_filter,
                ok_fn=rclpy.ok,
                cooldown_s=config.wake_cooldown_secs,
            )
            if not wake["wake_hit"]:
                break
            beep(
                config.beep_wake_freq,
                config.beep_wake_duration,
                volume=config.beep_wake_volume,
            )
            start = time.monotonic()
            pcm = capture_utterance(
                proc.stdout, config, live_filter, wake["noise_window"]
            )
            if pcm is None:
                log.info("No speech after wake")
                beep(
                    config.beep_fail_freq,
                    config.beep_fail_duration,
                    volume=config.beep_fail_volume,
                )
                continue
            msg = UInt8MultiArray()
            msg.data = array.array("B", pcm.tobytes())
            publisher.publish(msg)
            log.info(
                f"Published {len(pcm) / RATE:.1f} s of audio "
                f"(capture took {time.monotonic() - start:.1f} s)"
            )
    finally:
        proc.terminate()
        proc.wait(timeout=2)


def relay_replies(node: Node) -> None:
    """Republish each `/voice/llm_reply` string as an `/announcement`."""
    announce_pub = node.create_publisher(AnnouncementMsg, "/announcement", 10)

    def on_reply(msg: String) -> None:
        node.get_logger().info(f"Speaking reply: {msg.data!r}")
        announcement = Announcement(
            text=msg.data, priority=PRIORITY_QUERY_REPLY, source="llm_spike"
        )
        announce_pub.publish(announcement.to_msg())

    node.create_subscription(String, REPLY_TOPIC, on_reply, 10)


def spin_until_shutdown(executor: SingleThreadedExecutor) -> None:
    """Spin callbacks; Ctrl-C shuts the context down, which ends spin this way."""
    try:
        executor.spin()
    except ExternalShutdownException:
        return


def main() -> None:
    args = parse_args()
    config = dataclasses.replace(
        load_voice_runtime_config(args.config), wake_word=args.wake_word
    )
    rclpy.init()
    node = Node("llm_spike_mic")
    publisher = node.create_publisher(UInt8MultiArray, TOPIC, 10)
    relay_replies(node)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    threading.Thread(target=spin_until_shutdown, args=(executor,), daemon=True).start()
    try:
        listen_loop(node, publisher, config)
    except KeyboardInterrupt:
        node.get_logger().info("Stopped by Ctrl-C")
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
