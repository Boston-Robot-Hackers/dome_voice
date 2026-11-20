#!/usr/bin/env python3
"""
voice_input_node.py — ROS2 node: wake word, then a command by fixed grammar or by LLM.

Author: Pito Salas and Claude Code
Open Source Under MIT license

`command_path` in the voice YAML picks what happens after the wake word:

- **grammar:** Vosk transcribes against the command table, and the node
  publishes the matched intent on `/intent`.
- **llm:** the captured audio goes to the VM on `/voice/utterance`. The VM
  publishes `/intent` itself, and its spoken reply comes back on
  `/voice/llm_reply`, which this node relays to `/announcement`.

The wake/capture loop blocks the main thread, so ROS callbacks (the
`/voice/speaking` subscription) spin on a daemon thread. While speech_output
reports it is speaking, the wake word is ignored, so the robot doesn't hear
itself and its beeps never fight speech for the sound card.
"""

import array
import json
import os
import threading

import numpy as np
import rclpy
from dome_control.announcement_contract import (
    PRIORITY_QUERY_REPLY,
    AnnouncementMsg,
    make_announcement_msg,
)
from rclpy.executors import ExternalShutdownException, SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Bool, String, UInt8MultiArray

from dome_voice import (
    IntentMapper,
    VoiceRuntime,
    VoiceTurn,
    beep,
    load_voice_runtime_config,
)
from dome_voice.turn_recorder import RATE
from dome_voice.utterance_capture import VoiceUtterance, next_utterance

VOICE_STATES = ("IDLE", "LISTENING", "PROCESSING", "SPEAKING")


class VoiceInputNode(Node):
    def __init__(self):
        super().__init__("voice_input")
        self.intent_pub = self.create_publisher(String, "/intent", 10)
        self.state_pub = self.create_publisher(String, "/voice/state", 10)
        self.intent_mapper = IntentMapper()
        self.voice_config = load_voice_runtime_config(self.config_path())
        self.is_speaking = False
        self.create_subscription(Bool, "/voice/speaking", self.on_speaking, 10)
        if self.voice_config.command_path == "llm":
            self.utterance_pub = self.create_publisher(
                UInt8MultiArray, "/voice/utterance", 10
            )
            self.announce_pub = self.create_publisher(
                AnnouncementMsg, "/announcement", 10
            )
            self.create_subscription(String, "/voice/llm_reply", self.on_llm_reply, 10)

    def on_speaking(self, msg: Bool) -> None:
        self.is_speaking = msg.data

    def on_llm_reply(self, msg: String) -> None:
        """Speak the VM's reply; empty means an intent's consumer will talk."""
        if not msg.data:
            return
        self.get_logger().info(f"LLM reply: {msg.data!r}")
        self.announce_pub.publish(
            make_announcement_msg(msg.data, priority=PRIORITY_QUERY_REPLY, source="llm")
        )

    def play_beep(self, kind: str, device_index: int) -> None:
        """Play the `wake`, `intent` or `fail` beep from the voice config."""
        beep(
            frequency=getattr(self.voice_config, f"beep_{kind}_freq"),
            duration=getattr(self.voice_config, f"beep_{kind}_duration"),
            volume=getattr(self.voice_config, f"beep_{kind}_volume"),
            device_index=device_index,
        )

    def config_path(self) -> str:
        """The `config` parameter: the voice YAML, set by robot.launch.py."""
        self.declare_parameter("config", "")
        path = self.get_parameter("config").get_parameter_value().string_value
        if not path:
            raise RuntimeError(
                "voice_input needs the `config` parameter (the voice YAML); "
                "launch it with `bl dome_voice robot.launch.py`"
            )
        return path

    def publish_intent(self, intent: dict) -> None:
        msg = String()
        msg.data = json.dumps(intent)
        self.intent_pub.publish(msg)
        self.get_logger().info(f"Intent published: {msg.data}")

    def publish_state(self, state: str) -> None:
        msg = String()
        msg.data = state
        self.state_pub.publish(msg)
        self.get_logger().info(f"Voice state: {state}")

    def process_transcript(self, text: str, device_index: int = 0) -> None:
        self.get_logger().info(f"Transcribed: '{text}'")
        self.publish_state("PROCESSING")

        intent = self.intent_mapper.map_intent(text)
        if intent:
            self.publish_intent(intent)
        self.publish_state("SPEAKING")
        self.play_beep("intent" if intent else "fail", device_index)

    def process_turn(self, turn: VoiceTurn, device_index: int = 0) -> None:
        if turn.empty:
            cmd = (turn.metadata or {}).get("command", {})
            floor = cmd.get("floor")
            cutoff = cmd.get("cutoff")
            self.get_logger().info(
                f"Empty turn: floor={floor:.1f} cutoff={cutoff:.1f} "
                f"started={cmd.get('command_started')} raw={cmd.get('raw_text')!r}"
                if floor is not None and cutoff is not None
                else "Empty turn: no command metadata"
            )
            self.publish_state("SPEAKING")
            self.play_beep("fail", device_index)
            return
        self.process_transcript(turn.text, device_index=device_index)

    def process_utterance(self, utterance: VoiceUtterance, device_index: int) -> None:
        if utterance.pcm is None:
            self.get_logger().info("No speech after wake")
            self.play_beep("fail", device_index)
            return
        self.publish_utterance(utterance.pcm)
        self.publish_state("PROCESSING")

    def publish_utterance(self, pcm: np.ndarray) -> None:
        msg = UInt8MultiArray()
        msg.data = array.array("B", pcm.tobytes())
        self.utterance_pub.publish(msg)
        self.get_logger().info(f"Sent {len(pcm) / RATE:.1f} s of audio to the LLM")


def spin_in_background(node: Node) -> SingleThreadedExecutor:
    """Spin `node`'s callbacks on a daemon thread; the caller shuts it down."""
    executor = SingleThreadedExecutor()
    executor.add_node(node)

    def spin() -> None:
        try:
            executor.spin()
        except ExternalShutdownException:
            return

    threading.Thread(target=spin, daemon=True).start()
    return executor


def run_grammar_turn(node, runtime, on_wake, device_index: int) -> bool:
    """One wake and Vosk turn; False when listening ended without a wake."""
    turn = runtime.next_turn(
        ok_fn=rclpy.ok, on_wake=on_wake, is_muted_fn=lambda: node.is_speaking
    )
    if turn.metadata and not turn.metadata.get("wake", {}).get("wake_hit", False):
        return False
    node.process_turn(turn, device_index=device_index)
    return True


def run_llm_turn(node, runtime, on_wake, device_index: int) -> bool:
    """One wake and capture, sent to the VM; False when listening ended."""
    utterance = next_utterance(
        runtime, rclpy.ok, on_wake, is_muted_fn=lambda: node.is_speaking
    )
    if not utterance.is_woken:
        return False
    node.process_utterance(utterance, device_index)
    return True


def main():
    rclpy.init()
    node = VoiceInputNode()
    executor = spin_in_background(node)
    voice_config = node.voice_config
    device_index = int(os.environ.get("VOICE_DEVICE_INDEX", voice_config.capture_card))
    runtime = VoiceRuntime(voice_config)

    try:
        node.get_logger().info(
            f"Voice input ready — {voice_config.command_path} path, listening for "
            f"'{voice_config.wake_word}', from "
            f"{voice_config.source_path or 'built-in defaults'}"
        )
        node.publish_state("IDLE")

        def on_wake(_wake):
            node.get_logger().info("Wake word detected — speak your command")
            node.publish_state("LISTENING")
            node.play_beep("wake", device_index)

        run_turn = (
            run_llm_turn if voice_config.command_path == "llm" else run_grammar_turn
        )
        while rclpy.ok() and run_turn(node, runtime, on_wake, device_index):
            node.publish_state("IDLE")

    finally:
        runtime.close()
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
