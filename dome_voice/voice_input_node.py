#!/usr/bin/env python3
"""
voice_input_node.py — ROS2 node: openWakeWord + Vosk STT + intent mapper → /intent.

Author: Pito Salas and Claude Code
Open Source Under MIT license

The wake/capture loop blocks the main thread, so ROS callbacks (the
`/voice/speaking` subscription) spin on a daemon thread. While speech_output
reports it is speaking, the wake word is ignored, so the robot doesn't hear
itself and its beeps never fight speech for the sound card.
"""

import json
import os
import threading

import rclpy
from rclpy.executors import ExternalShutdownException, SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Bool, String

from dome_voice import (
    IntentMapper,
    VoiceRuntime,
    VoiceTurn,
    beep,
    load_voice_runtime_config,
)

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

    def on_speaking(self, msg: Bool) -> None:
        self.is_speaking = msg.data

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
            beep(
                frequency=self.voice_config.beep_intent_freq,
                duration=self.voice_config.beep_intent_duration,
                volume=self.voice_config.beep_intent_volume,
                device_index=device_index,
            )
        else:
            self.publish_state("SPEAKING")
            beep(
                frequency=self.voice_config.beep_fail_freq,
                duration=self.voice_config.beep_fail_duration,
                volume=self.voice_config.beep_fail_volume,
                device_index=device_index,
            )

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
            beep(
                frequency=self.voice_config.beep_fail_freq,
                duration=self.voice_config.beep_fail_duration,
                volume=self.voice_config.beep_fail_volume,
                device_index=device_index,
            )
            return
        self.process_transcript(turn.text, device_index=device_index)


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


def main():
    rclpy.init()
    node = VoiceInputNode()
    executor = spin_in_background(node)
    voice_config = node.voice_config
    device_index = int(os.environ.get("VOICE_DEVICE_INDEX", voice_config.capture_card))
    runtime = VoiceRuntime(voice_config)

    try:
        node.get_logger().info(
            f"Voice input ready — listening for '{voice_config.wake_word}' "
            f"from {voice_config.source_path or 'built-in defaults'}"
        )
        node.publish_state("IDLE")

        while rclpy.ok():

            def on_wake(_wake):
                node.get_logger().info("Wake word detected — speak your command")
                node.publish_state("LISTENING")
                beep(
                    frequency=voice_config.beep_wake_freq,
                    duration=voice_config.beep_wake_duration,
                    volume=voice_config.beep_wake_volume,
                    device_index=device_index,
                )

            turn = runtime.next_turn(
                ok_fn=rclpy.ok,
                on_wake=on_wake,
                is_muted_fn=lambda: node.is_speaking,
            )
            if turn.metadata and not turn.metadata.get("wake", {}).get(
                "wake_hit", False
            ):
                break
            node.process_turn(turn, device_index=device_index)
            node.publish_state("IDLE")

    finally:
        runtime.close()
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
