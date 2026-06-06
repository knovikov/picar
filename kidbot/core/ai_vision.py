"""Помощник OpenAI Vision с дружелюбными русскими промптами."""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any, Iterable

from kidbot.kid_code.robot_personality import FACTUAL_VISION_PROMPT, FUNNY_VISION_PROMPT

logger = logging.getLogger("kidbot.ai")


class AIVision:
    def __init__(self, config: dict[str, Any]):
        openai_config = config.get("openai", {})
        self.vision_model = openai_config.get("vision_model", "gpt-5-mini")
        self.client = None

        if os.environ.get("OPENAI_API_KEY"):
            self._ensure_client()

    @property
    def is_available(self) -> bool:
        return self._ensure_client()

    def describe_funny(self, photo_path: Path) -> str:
        return self._describe([photo_path], FUNNY_VISION_PROMPT)

    def describe_scene(self, photo_path: Path) -> str:
        return self._describe([photo_path], FACTUAL_VISION_PROMPT)

    def describe_panorama(self, photos: Iterable[tuple[str, Path]]) -> str:
        prompt = (
            "Опиши три фото для ребенка 7 лет. Ответь кратко по-русски в формате: "
            "Слева я вижу... Перед собой я вижу... Справа я вижу..."
        )
        return self._describe([path for _, path in photos], prompt)

    def find_thing(self, photos: Iterable[tuple[str, Path]], hint: str) -> str:
        prompt = (
            f"Ребенок попросил найти: {hint}. Посмотри на фото вокруг робота. "
            "Если видишь похожий предмет, скажи где он. Если нет, скажи: "
            "Я пока не нашел. Возможно предмет спрятался как ниндзя."
        )
        return self._describe([path for _, path in photos], prompt)

    def find_interesting(self, photos: Iterable[tuple[str, Path]]) -> str:
        prompt = (
            "Выбери один интересный объект на этих фото. Ответь по-русски одной "
            "доброй фразой: Я нашел кое-что интересное: ..."
        )
        return self._describe([path for _, path in photos], prompt)

    def _describe(self, photo_paths: list[Path], prompt: str) -> str:
        if not self._ensure_client():
            return "Я вижу фото, но без интернета не могу спросить облачный мозг."

        content: list[dict[str, str]] = [{"type": "input_text", "text": prompt}]
        for path in photo_paths:
            content.append({"type": "input_image", "image_url": _image_data_url(path)})

        try:
            response = self.client.responses.create(
                model=self.vision_model,
                input=[{"role": "user", "content": content}],
            )
            return response.output_text.strip()
        except Exception as exc:
            logger.error("OpenAI vision failed: %s", exc)
            return "Мои робо-глаза посмотрели, но облачный ответ не получился."

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
            logger.error("OpenAI vision client unavailable: %s", exc)
            return False


def _image_data_url(path: Path) -> str:
    image_bytes = Path(path).read_bytes()
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"
