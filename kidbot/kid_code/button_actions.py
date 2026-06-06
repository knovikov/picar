"""Что делает KidBot, когда нажимают кнопки.

Этот файл специально простой и дружелюбный.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from kidbot.kid_code import robot_personality


@dataclass
class ButtonActionContext:
    robot: object
    camera: object
    voice: object
    media: object
    ai_chat: object
    ai_vision: object
    status: object
    photo_dir: Path


class ButtonActions:
    """Действия кнопок, которые легко объяснить."""

    def __init__(self, context: ButtonActionContext):
        self.context = context

    def press_a_take_photo(self) -> Optional[Path]:
        # Кнопка A делает фотографию, как маленький фотоаппарат.
        photo_path = self.context.camera.capture_photo()
        self.context.voice.say("Фотография готова!")
        return photo_path

    def press_b_toggle_music(self) -> None:
        # Кнопка B включает музыку. Если музыка уже играет, она делает тишину.
        if self.context.media.is_music_playing:
            self.context.media.stop_music()
        else:
            self.context.media.play_random_music()

    def press_x_read_story(self) -> None:
        # Кнопка X выбирает сказку и просит робота ее прочитать.
        story = self.context.media.read_random_story()
        self.context.voice.say(story)

    def press_y_funny_vision(self) -> None:
        # Кнопка Y просит робота посмотреть и пошутить добрым голосом.
        photo_path = self.context.camera.capture_photo(prefix="funny")
        if self.context.ai_vision.is_available:
            text = self.context.ai_vision.describe_funny(photo_path)
        else:
            text = robot_personality.random_offline_joke()
        self.context.voice.say(text)

    def double_press_y_describe_scene(self) -> None:
        photo_path = self.context.camera.capture_photo(prefix="scene")
        if self.context.ai_vision.is_available:
            text = self.context.ai_vision.describe_scene(photo_path)
        else:
            text = "Я вижу мир, но без интернета не могу описать его очень подробно."
        self.context.voice.say(text)

    def hold_y_explore_around(self) -> None:
        photos = []
        for name, pan in (("left", -35), ("center", 0), ("right", 35)):
            self.context.robot.set_head(pan=pan, tilt=0)
            photos.append((name, self.context.camera.capture_photo(prefix=name)))
        self.context.robot.set_head(pan=0, tilt=0)

        if self.context.ai_vision.is_available:
            text = self.context.ai_vision.describe_panorama(photos)
        else:
            text = "Я посмотрел налево, вперед и направо. Без интернета я просто скажу: вокруг есть загадки!"
        self.context.voice.say(text)

    def press_select_new_chat(self) -> None:
        self.context.ai_chat.clear()
        self.context.voice.say(robot_personality.new_chat_sentence())

    def press_start_stop_everything(self) -> None:
        self.context.robot.emergency_stop()
        self.context.media.stop_all()
        self.context.voice.stop()
        self.context.voice.say(robot_personality.stopped_sentence())

    def press_r1_status(self) -> None:
        status = self.context.status.snapshot()
        self.context.voice.say(status.to_sentence())

    def press_l1_push_to_talk(self, audio_path: Optional[Path] = None) -> None:
        if not self.context.ai_chat.is_available:
            self.context.voice.say(robot_personality.OFFLINE_SMART_REPLY)
            return

        text = self.context.ai_chat.transcribe(audio_path)
        answer = self.context.ai_chat.ask(text)
        self.context.voice.say(answer)

    def press_l2_find_thing(self, hint: str) -> None:
        if not self.context.ai_vision.is_available:
            self.context.voice.say("Я без интернета и пока не могу искать вещи глазами.")
            return

        photos = self._look_around()
        answer = self.context.ai_vision.find_thing(photos, hint)
        self.context.voice.say(answer)

    def press_r2_find_interesting(self) -> None:
        if not self.context.ai_vision.is_available:
            self.context.voice.say("Я нашел кое-что интересное: свой веселый моторчик.")
            return

        photos = self._look_around()
        answer = self.context.ai_vision.find_interesting(photos)
        self.context.voice.say(answer)

    def _look_around(self) -> list[tuple[str, Path]]:
        photos = []
        for name, pan in (("left", -35), ("center", 0), ("right", 35)):
            self.context.robot.set_head(pan=pan, tilt=0)
            photos.append((name, self.context.camera.capture_photo(prefix=name)))
        self.context.robot.set_head(pan=0, tilt=0)
        return photos
