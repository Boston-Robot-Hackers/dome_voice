#!/usr/bin/env python3
"""
llm_node.py — VM side of the LLM command path: speech or text → Claude → /intent and a reply.

Author: Pito Salas and Claude Code
Open Source Under MIT license

Inputs:
- `/voice/utterance` (`std_msgs/UInt8MultiArray`): 16 kHz int16 mono PCM from
  the robot, transcribed with faster-whisper on the CPU.
- `/voice/llm_text` (`std_msgs/String`): a question from a program (a gamepad
  button, say), which skips Whisper.

Both go into one conversation. Each tool call Claude makes is published on
`/intent` as JSON (source `llm`). **Every input gets exactly one reply** on
`/voice/llm_reply`, empty when an intent's consumer will do the talking, so
the robot can tell a slow VM from a missing one.

`/intent` and the reply are plain `std_msgs/String`, so the VM needs only stock
ROS 2. Work runs in the subscription callbacks, so inputs queue up in order.
Run it from the repo root, with no `colcon build` on the VM:

    python3 -m dome_voice.llm_node [--persona FILE] [--whisper-model base.en]
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import anthropic
import rclpy
from faster_whisper import WhisperModel
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray

from dome_voice.llm_turn import MODEL, Conversation, load_persona, pcm_to_float
from dome_voice.turn_recorder import RATE

DEFAULT_PERSONA = Path(__file__).resolve().parents[1] / "config" / "llm_persona.md"
NOT_HEARD_REPLY = "Sorry, I didn't catch that."
API_ERROR_REPLY = "Sorry, I couldn't reach my brain just now."


class LlmNode(Node):
    def __init__(self, args: argparse.Namespace):
        super().__init__("llm_node")
        persona = load_persona(Path(args.persona))
        self.get_logger().info(f"Loading faster-whisper '{args.whisper_model}'...")
        self.whisper = WhisperModel(
            args.whisper_model, device="cpu", compute_type="int8"
        )
        self.conversation = Conversation(anthropic.Anthropic(), persona, args.model)
        self.reply_pub = self.create_publisher(String, "/voice/llm_reply", 10)
        self.intent_pub = self.create_publisher(String, "/intent", 10)
        self.create_subscription(
            UInt8MultiArray, "/voice/utterance", self.on_utterance, 10
        )
        self.create_subscription(String, "/voice/llm_text", self.on_text, 10)
        self.get_logger().info(
            f"Ready: Whisper '{args.whisper_model}', Claude '{args.model}', "
            f"persona {args.persona}"
        )

    def transcribe(self, payload: bytes) -> str:
        segments, _info = self.whisper.transcribe(
            pcm_to_float(payload), language="en", beam_size=1
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    def on_utterance(self, msg: UInt8MultiArray) -> None:
        payload = bytes(msg.data)
        stt_start = time.monotonic()
        heard = self.transcribe(payload)
        self.get_logger().info(
            f"Heard ({len(payload) / 2 / RATE:.1f} s audio, "
            f"STT {time.monotonic() - stt_start:.1f} s): {heard!r}"
        )
        if not heard:
            self.publish_reply(NOT_HEARD_REPLY)
            return
        self.answer(heard)

    def on_text(self, msg: String) -> None:
        self.get_logger().info(f"Text in: {msg.data!r}")
        self.answer(msg.data)

    def answer(self, user_text: str) -> None:
        log = self.get_logger()
        llm_start = time.monotonic()
        try:
            turn = self.conversation.ask(user_text, datetime.now())
        except anthropic.APIError as error:
            log.error(f"Claude request failed: {error}")
            self.publish_reply(API_ERROR_REPLY)
            return
        log.info(
            f"Reply (LLM {time.monotonic() - llm_start:.1f} s): {turn.reply!r}, "
            f"intents {[intent['name'] for intent in turn.intents]}"
        )
        for intent in turn.intents:
            self.intent_pub.publish(String(data=json.dumps(intent)))
        self.publish_reply(turn.reply)

    def publish_reply(self, text: str) -> None:
        self.reply_pub.publish(String(data=text))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--persona", default=str(DEFAULT_PERSONA))
    parser.add_argument("--whisper-model", default="base.en")
    parser.add_argument("--model", default=MODEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rclpy.init()
    node = LlmNode(args)
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
