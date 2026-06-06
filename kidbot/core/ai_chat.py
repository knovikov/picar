"""Обертка для OpenAI-чата и распознавания речи."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from kidbot.kid_code.robot_personality import OFFLINE_SMART_REPLY, PERSONALITY_PROMPT

logger = logging.getLogger("kidbot.ai")


class AIChat:
    def __init__(self, config: dict[str, Any]):
        openai_config = config.get("openai", {})
        self.chat_model = openai_config.get("chat_model", "gpt-5-mini")
        self.stt_model = openai_config.get("stt_model", "gpt-4o-mini-transcribe")
        self.history: list[dict[str, str]] = []
        self.client = None

        if os.environ.get("OPENAI_API_KEY"):
            self._ensure_client()

    @property
    def is_available(self) -> bool:
        return self._ensure_client()

    def clear(self) -> None:
        self.history.clear()

    def ask(self, text: str) -> str:
        if not self._ensure_client():
            return OFFLINE_SMART_REPLY

        self.history.append({"role": "user", "content": text})
        try:
            response = self.client.responses.create(
                model=self.chat_model,
                instructions=PERSONALITY_PROMPT,
                input=self._response_input(),
            )
            answer = response.output_text.strip()
            self.history.append({"role": "assistant", "content": answer})
            self.history = self.history[-12:]
            return answer
        except Exception as exc:
            logger.error("OpenAI chat failed: %s", exc)
            return "Мой облачный мозг споткнулся. Давай попробуем еще раз позже."

    def transcribe(self, audio_path: Optional[Path]) -> str:
        if not self._ensure_client() or audio_path is None:
            return ""

        try:
            with Path(audio_path).open("rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model=self.stt_model,
                    file=audio_file,
                    response_format="text",
                )
            return str(transcript)
        except Exception as exc:
            logger.error("OpenAI transcription failed: %s", exc)
            return ""

    def _response_input(self) -> str:
        lines = []
        for message in self.history:
            role = "Ярослав" if message["role"] == "user" else "KidBot"
            lines.append(f"{role}: {message['content']}")
        return "\n".join(lines)

    def _ensure_client(self) -> bool:
        if self.client is not None:
            return True
        if not os.environ.get("OPENAI_API_KEY"):
            return False
        try:
            from openai import OpenAI

            self.client = OpenAI()
            return True
        except Exception as exc:
            logger.error("OpenAI client unavailable: %s", exc)
            return False
