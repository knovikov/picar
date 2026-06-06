"""Звуки, музыка и сказки."""

from __future__ import annotations

import logging
import random
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("kidbot.media")
AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg"}
ProcessLauncher = Callable[[Path], Optional[subprocess.Popen]]


class MediaPlayer:
    def __init__(
        self,
        sounds_dir: Path,
        music_dir: Path,
        stories_dir: Path,
        process_launcher: Optional[ProcessLauncher] = None,
    ):
        self.sounds_dir = Path(sounds_dir)
        self.music_dir = Path(music_dir)
        self.stories_dir = Path(stories_dir)
        self._process_launcher = process_launcher or (lambda path: play_audio_file(path, wait=False))
        self._music_process: Optional[subprocess.Popen] = None
        self._engine_process: Optional[subprocess.Popen] = None
        self._engine_sound_name = ""

    @property
    def is_music_playing(self) -> bool:
        return self._music_process is not None and self._music_process.poll() is None

    @property
    def is_engine_sound_playing(self) -> bool:
        return self._engine_process is not None and self._engine_process.poll() is None

    def play_sound(self, name: str) -> None:
        path = self.sounds_dir / name
        if path.exists():
            self._process_launcher(path)

    def play_random_music(self) -> None:
        files = list_audio_files(self.music_dir)
        if not files:
            logger.warning("no music files found in %s", self.music_dir)
            return
        self.stop_music()
        self._music_process = self._process_launcher(random.choice(files))

    def stop_music(self) -> None:
        if self.is_music_playing:
            assert self._music_process is not None
            self._music_process.terminate()
        self._music_process = None

    def update_engine_sound(self, speed: float, config: dict) -> None:
        if not bool(config.get("enabled", True)):
            self.stop_engine_sound()
            return

        speed_abs = abs(float(speed))
        min_speed = float(config.get("min_speed", 4.0))
        if speed_abs < min_speed:
            self.stop_engine_sound()
            return

        rev_speed = float(config.get("rev_speed", 18.0))
        desired_name = str(config.get("rev_file", "engine_rev.wav") if speed_abs >= rev_speed else config.get("idle_file", "engine_idle.wav"))
        if desired_name == self._engine_sound_name and self.is_engine_sound_playing:
            return

        self.stop_engine_sound()
        path = self.sounds_dir / desired_name
        if not path.exists():
            logger.warning("engine sound file not found: %s", path)
            return
        self._engine_process = self._process_launcher(path)
        self._engine_sound_name = desired_name if self._engine_process is not None else ""

    def stop_engine_sound(self) -> None:
        if self.is_engine_sound_playing:
            assert self._engine_process is not None
            self._engine_process.terminate()
        self._engine_process = None
        self._engine_sound_name = ""

    def stop_all(self) -> None:
        self.stop_music()
        self.stop_engine_sound()

    def read_random_story(self) -> str:
        stories = sorted(self.stories_dir.glob("*.txt"))
        if not stories:
            return "Я пока не нашел сказки. Похоже, книжная полка пустая."
        return random.choice(stories).read_text(encoding="utf-8").strip()

def list_audio_files(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in Path(directory).glob("*")
        if path.suffix.lower() in AUDIO_EXTENSIONS
    )


def play_audio_file(path: Path, wait: bool = False) -> Optional[subprocess.Popen]:
    command = _player_command(path)
    try:
        if wait:
            subprocess.run(command, check=False)
            return None
        return subprocess.Popen(command)
    except FileNotFoundError as exc:
        logger.error("audio player not found: %s", exc)
        return None


def _player_command(path: Path) -> list[str]:
    if path.suffix.lower() == ".wav":
        if sys.platform == "darwin":
            return ["afplay", str(path)]
        return ["aplay", str(path)]
    return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]
