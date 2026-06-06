"""Голос робота и простые крючки для распознавания речи."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Callable, Optional, Sequence

logger = logging.getLogger("kidbot.voice")


class Voice:
    def __init__(
        self,
        use_openai: bool = True,
        espeak_voice: str = "ru",
        espeak_speed: int = 150,
        command_runner: Optional[Callable[[Sequence[str]], object]] = None,
        openai_model: str = "gpt-4o-mini-tts",
    ):
        self.use_openai = use_openai
        self.espeak_voice = espeak_voice
        self.espeak_speed = espeak_speed
        self.openai_model = openai_model
        self.command_runner = command_runner or self._run_command
        self._last_process: Optional[subprocess.Popen] = None

    def say(self, text: str) -> None:
        if not text:
            return

        if self.use_openai and os.environ.get("OPENAI_API_KEY") and self._say_with_openai(text):
            return

        command = ["espeak-ng", "-v", self.espeak_voice, "-s", str(self.espeak_speed), text]
        logger.info("speaking with espeak-ng")
        self.command_runner(command)

    def stop(self) -> None:
        if self._last_process and self._last_process.poll() is None:
            self._last_process.terminate()
        self._last_process = None

    def _say_with_openai(self, text: str) -> bool:
        try:
            from openai import OpenAI

            client = OpenAI()
            output_path = Path("/tmp/kidbot_tts.mp3")
            if hasattr(client.audio.speech, "with_streaming_response"):
                with client.audio.speech.with_streaming_response.create(
                    model=self.openai_model,
                    voice="alloy",
                    input=text,
                ) as response:
                    response.stream_to_file(output_path)
            else:
                speech = client.audio.speech.create(
                    model=self.openai_model,
                    voice="alloy",
                    input=text,
                )
                speech.write_to_file(output_path)
            self.command_runner(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(output_path)])
            return True
        except Exception as exc:
            logger.warning("OpenAI TTS failed; falling back to espeak-ng: %s", exc)
            return False

    def _run_command(self, command: Sequence[str]) -> None:
        try:
            subprocess.run(list(command), check=False)
        except FileNotFoundError as exc:
            logger.error("voice command not found: %s", exc)
