#!/usr/bin/env python3
"""
vm_llm_node.py — VM side of the F12 spike: /voice/utterance → Whisper → Claude → /voice/llm_reply.

Author: Pito Salas and Claude Code
Open Source Under MIT license

Each utterance is transcribed with faster-whisper on the CPU, sent to Claude
with the conversation so far, and the reply is published as a
plain `std_msgs/String` on `/voice/llm_reply`. The robot script relays it to
`/announcement`, so this side needs only stock ROS 2. Work runs in the
subscription callback, so utterances that arrive meanwhile queue up.

    python3 spikes/llm_loop/vm_llm_node.py [--whisper-model base.en]
"""

import argparse
import time

import anthropic
import rclpy
from faster_whisper import WhisperModel
from llm_turn import MODEL, RATE, Conversation, pcm_to_float
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray

NOT_HEARD_REPLY = "Sorry, I didn't catch that."
API_ERROR_REPLY = "Sorry, I couldn't reach my brain just now."


class LlmSpikeNode(Node):
    def __init__(self, whisper_model: str, model: str):
        super().__init__("llm_spike_vm")
        self.get_logger().info(f"Loading faster-whisper '{whisper_model}'...")
        self.whisper = WhisperModel(whisper_model, device="cpu", compute_type="int8")
        self.conversation = Conversation(anthropic.Anthropic(), model)
        self.reply_pub = self.create_publisher(String, "/voice/llm_reply", 10)
        self.create_subscription(
            UInt8MultiArray, "/voice/utterance", self.on_utterance, 10
        )
        self.get_logger().info(f"Ready: Whisper '{whisper_model}', Claude '{model}'")

    def transcribe(self, payload: bytes) -> str:
        segments, _info = self.whisper.transcribe(
            pcm_to_float(payload), language="en", beam_size=1
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    def on_utterance(self, msg: UInt8MultiArray) -> None:
        log = self.get_logger()
        payload = bytes(msg.data)
        stt_start = time.monotonic()
        heard = self.transcribe(payload)
        stt_secs = time.monotonic() - stt_start
        log.info(
            f"Heard ({len(payload) / 2 / RATE:.1f} s audio, STT {stt_secs:.1f} s): {heard!r}"
        )
        if not heard:
            self.speak(NOT_HEARD_REPLY)
            return
        llm_start = time.monotonic()
        try:
            reply = self.conversation.ask(heard)
        except anthropic.APIError as error:
            log.error(f"Claude request failed: {error}")
            self.speak(API_ERROR_REPLY)
            return
        log.info(f"Reply (LLM {time.monotonic() - llm_start:.1f} s): {reply!r}")
        self.speak(reply)

    def speak(self, text: str) -> None:
        msg = String()
        msg.data = text
        self.reply_pub.publish(msg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--whisper-model", default="base.en")
    parser.add_argument("--model", default=MODEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rclpy.init()
    node = LlmSpikeNode(args.whisper_model, args.model)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        node.get_logger().info("Stopped by Ctrl-C")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
