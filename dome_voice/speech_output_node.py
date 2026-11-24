#!/usr/bin/env python3
# speech_output_node — ROS2 node: speak each /announcement via Piper and ALSA
# Author: Pito Salas and Claude Code
# Version: 4
# Created: 2026-11-19
# Updated: 2026-11-20
# Open Source Under MIT license
"""Speaks each `/announcement` through Piper and ALSA, with `/voice/speaking`
true for the duration.

F15 made speech start sooner. An announcement used to start a new Piper and
load the voice model each time, about 0.6 s of the ~1.6 s before sound.
Now:
- **One Piper process runs for the life of the node**
  (`dome_voice.piper_server`).
- **Text is spoken a sentence at a time, pipelined:** sentence n+1 is
  synthesised while sentence n plays. Each sentence is written to a file
  in `/dev/shm` and `aplay` plays the file, so playing doesn't block
  synthesis.
- **Recent sentences are cached**, so a repeated one plays at once.
"""

import json
import os
import subprocess
from pathlib import Path

import numpy as np
import rclpy
from dome_control.announcement_contract import Announcement, AnnouncementMsg
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Bool

from dome_voice.piper_server import (
    SPEECH_DIR,
    PiperServer,
    SpeechCache,
    piper_command,
    split_sentences,
)
from dome_voice.runtime import load_speech_settings


def aplay_command(sample_rate: int, alsa_device: str = "") -> list[str]:
    """aplay playing raw int16 mono PCM at `sample_rate`; the file path goes last."""
    cmd = ["aplay", "-q"]
    if alsa_device:
        cmd.extend(["-D", alsa_device])
    cmd.extend(["-t", "raw", "-f", "S16_LE", "-r", str(sample_rate), "-c", "1"])
    return cmd


def model_sample_rate(model_path: str) -> int:
    """The voice's output rate, from the `<model>.json` Piper ships beside it."""
    if not model_path:
        raise RuntimeError("DOME_PIPER_MODEL_PATH is required for speech output")
    config_path = Path(f"{model_path}.json")
    return int(json.loads(config_path.read_text())["audio"]["sample_rate"])


def scale_pcm(pcm: bytes, gain: float) -> bytes:
    """Scale int16 PCM by `gain`, clipping to the int16 range."""
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) * gain
    return np.clip(samples, -32768, 32767).astype("<i2").tobytes()


class Playback:
    """One sentence playing in the background: `pcm` written to `path`, then
    the player started on it. `wait` blocks until it ends and raises if the
    player failed; `stop` cuts it short. Both remove the file."""

    def __init__(self, pcm: bytes, play_cmd: list[str], path: Path):
        self.path = path
        path.write_bytes(pcm)
        self.proc = subprocess.Popen([*play_cmd, str(path)], stderr=subprocess.PIPE)

    def wait(self) -> None:
        code = self.proc.wait()
        err = self.proc.stderr.read().decode(errors="replace").strip()
        self.path.unlink(missing_ok=True)
        if code != 0:
            raise RuntimeError(f"aplay failed ({code}): {err}")

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait()
        self.path.unlink(missing_ok=True)


class SpeechOutputNode(Node):
    def __init__(self):
        super().__init__("speech_output")
        self.announcement_sub = self.create_subscription(
            AnnouncementMsg, "/announcement", self.on_announcement, 10
        )
        self.speaking_pub = self.create_publisher(Bool, "/voice/speaking", 10)
        config = self.config_path()
        speech = load_speech_settings(config)
        self.speech_gain = speech.gain
        self.length_scale = speech.length_scale
        self.alsa_device = speech.alsa_device
        self.piper_bin = os.environ.get("DOME_PIPER_BIN", "piper")
        self.piper_model_path = os.environ.get("DOME_PIPER_MODEL_PATH", "")
        self.sample_rate = model_sample_rate(self.piper_model_path)
        self.piper = PiperServer(
            piper_command(self.piper_bin, self.piper_model_path, self.length_scale),
            self.sample_rate,
            SPEECH_DIR,
        )
        self.cache = SpeechCache()
        self.get_logger().info(
            f"Speech from {config}: gain {self.speech_gain}, length scale "
            f"{self.length_scale}, device {self.alsa_device or 'ALSA default'}"
        )

    def config_path(self) -> str:
        """The `config` parameter: the voice YAML, set by robot.launch.py."""
        self.declare_parameter("config", "")
        path = self.get_parameter("config").get_parameter_value().string_value
        if not path:
            raise RuntimeError(
                "speech_output needs the `config` parameter (the voice YAML); "
                "launch it with `bl dome_voice robot.launch.py`"
            )
        return path

    def on_announcement(self, msg: AnnouncementMsg) -> None:
        announcement = Announcement.from_msg(msg)
        if not announcement.text:
            self.get_logger().debug("Ignoring empty announcement payload")
            return

        # Listeners mute their wake word while this is true, so the robot
        # doesn't hear itself and their beeps don't fight speech for the card.
        self.speaking_pub.publish(Bool(data=True))
        try:
            self.speak_text(announcement.text)
            self.get_logger().info(
                f"Spoken announcement ({announcement.priority}) from "
                f"{announcement.source}: {announcement.text}"
            )
        except (
            RuntimeError,
            ValueError,
            OSError,
        ) as exc:
            self.get_logger().error(f"Speech output failed: {exc}")
        finally:
            self.speaking_pub.publish(Bool(data=False))

    def speak_text(self, text: str) -> None:
        """Speak `text` a sentence at a time, synthesising the next while one plays."""
        play_cmd = aplay_command(self.sample_rate, self.alsa_device)
        playing = None
        try:
            for index, sentence in enumerate(split_sentences(text)):
                pcm = scale_pcm(self.sentence_audio(sentence), self.speech_gain)
                if playing is not None:
                    playing.wait()
                playing = Playback(pcm, play_cmd, self.play_path(index))
            playing.wait()
            playing = None
        finally:
            if playing is not None:
                playing.stop()

    def sentence_audio(self, sentence: str) -> bytes:
        pcm = self.cache.get(sentence)
        if pcm is None:
            pcm = self.piper.synthesize(sentence)
            self.cache.put(sentence, pcm)
        return pcm

    def play_path(self, index: int) -> Path:
        return SPEECH_DIR / f"dome_play_{os.getpid()}_{index}.raw"

    def destroy_node(self) -> None:
        self.piper.close()
        super().destroy_node()


def main():
    rclpy.init()
    node = SpeechOutputNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass  # Ctrl-C or the launcher's SIGTERM: a normal stop
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
