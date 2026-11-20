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
ROS 2 and this package. Work runs in the subscription callbacks, so inputs
queue up in order. Parameters: `persona` (required, the persona file),
`whisper_model` (default `base.en`), `model` (default Claude Haiku).

    bl dome_voice remote.launch.py
    bl dome2 remote.launch.py --options "vi vo"       # with the map view
"""

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

NOT_HEARD_REPLY = "Sorry, I didn't catch that."
API_ERROR_REPLY = "Sorry, I couldn't reach my brain just now."


class LlmNode(Node):
    def __init__(self):
        super().__init__("llm_node")
        persona_path = self.declare_parameter("persona", "").value
        whisper_model = self.declare_parameter("whisper_model", "base.en").value
        model = self.declare_parameter("model", MODEL).value
        if not persona_path:
            raise RuntimeError(
                "llm_node needs the `persona` parameter (the persona file); "
                "launch it with `bl dome_voice remote.launch.py`"
            )
        persona = load_persona(Path(persona_path))
        self.get_logger().info(f"Loading faster-whisper '{whisper_model}'...")
        self.whisper = WhisperModel(whisper_model, device="cpu", compute_type="int8")
        self.conversation = Conversation(anthropic.Anthropic(), persona, model)
        self.reply_pub = self.create_publisher(String, "/voice/llm_reply", 10)
        self.intent_pub = self.create_publisher(String, "/intent", 10)
        self.create_subscription(
            UInt8MultiArray, "/voice/utterance", self.on_utterance, 10
        )
        self.create_subscription(String, "/voice/llm_text", self.on_text, 10)
        self.get_logger().info(
            f"Ready: Whisper '{whisper_model}', Claude '{model}', persona {persona_path}"
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


def main() -> None:
    rclpy.init()
    node = LlmNode()
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
