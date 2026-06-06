"""Звуки, музыка и сказки."""

from __future__ import annotations

import logging
import random
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("kidbot.media")
AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg"}


class MediaPlayer:
    def __init__(self, sounds_dir: Path, music_dir: Path, stories_dir: Path):
        self.sounds_dir = Path(sounds_dir)
        self.music_dir = Path(music_dir)
        self.stories_dir = Path(stories_dir)
        self._music_process: Optional[subprocess.Popen] = None

    @property
    def is_music_playing(self) -> bool:
        return self._music_process is not None and self._music_process.poll() is None

    def play_sound(self, name: str) -> None:
        path = self.sounds_dir / name
        if path.exists():
            play_audio_file(path, wait=False)

    def play_random_music(self) -> None:
        files = list_audio_files(self.music_dir)
        if not files:
            logger.warning("no music files found in %s", self.music_dir)
            return
        self.stop_music()
        self._music_process = play_audio_file(random.choice(files), wait=False)

    def stop_music(self) -> None:
        if self.is_music_playing:
            assert self._music_process is not None
            self._music_process.terminate()
        self._music_process = None

    def stop_all(self) -> None:
        self.stop_music()

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
        return ["aplay", str(path)]
    return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]
