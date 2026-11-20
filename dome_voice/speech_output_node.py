#!/usr/bin/env python3
# speech_output_node — ROS2 node: speak each /announcement via Piper and ALSA
# Author: Pito Salas and Claude Code
# Version: 4
# Created: 2026-11-19
# Updated: 2026-11-20
# Open Source Under MIT license

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

from dome_voice.runtime import load_speech_settings

PCM_CHUNK_BYTES = 4096


def piper_command(piper_bin: str, model_path: str, length_scale: float) -> list[str]:
    """Piper writing raw int16 mono PCM to stdout as each sentence is ready."""
    return [
        piper_bin,
        "--model",
        model_path,
        "--output_raw",
        "--length_scale",
        str(length_scale),
        "--quiet",
    ]


def aplay_command(sample_rate: int, alsa_device: str = "") -> list[str]:
    """aplay reading raw int16 mono PCM at `sample_rate` from stdin."""
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


def stream_speech(
    text: str, synth_cmd: list[str], play_cmd: list[str], gain: float
) -> None:
    """Pipe `text` through the synthesizer into the player, scaling on the way.

    Playback starts as soon as the synthesizer emits its first audio, instead
    of after the whole reply is rendered. Chunks are cut to whole samples, so
    an odd byte is carried to the next read. Raises if either process fails.
    """
    synth = subprocess.Popen(
        synth_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    play = subprocess.Popen(play_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        synth.stdin.write(text.encode("utf-8"))
        synth.stdin.close()
        carry = b""
        while chunk := synth.stdout.read(PCM_CHUNK_BYTES):
            chunk = carry + chunk
            whole = len(chunk) - len(chunk) % 2
            play.stdin.write(scale_pcm(chunk[:whole], gain))
            carry = chunk[whole:]
        play.stdin.close()
        check_exit("piper", synth)
        check_exit("aplay", play)
    finally:
        for proc in (synth, play):
            if proc.poll() is None:
                proc.kill()
                proc.wait()


def check_exit(name: str, proc: subprocess.Popen) -> None:
    """Wait for `proc`; raise with its stderr if it exited non-zero."""
    err = proc.stderr.read()
    if proc.wait() != 0:
        raise RuntimeError(
            f"{name} failed ({proc.returncode}): {err.decode(errors='replace').strip()}"
        )


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
        stream_speech(
            text,
            piper_command(self.piper_bin, self.piper_model_path, self.length_scale),
            aplay_command(self.sample_rate, self.alsa_device),
            self.speech_gain,
        )


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
