"""Сетевые помощники для KidBot."""

from __future__ import annotations

import socket
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional


def is_wifi_connected() -> bool:
    try:
        result = subprocess.run(
            ["iwgetid", "-r"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        return bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def has_internet(host: str = "1.1.1.1", port: int = 53, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_ip_address() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def get_hostname() -> str:
    return socket.gethostname()


@dataclass
class NetworkSnapshot:
    wifi_connected: bool
    internet_connected: bool
    ip_address: str
    hostname: str


class NetworkMonitor:
    """Замечает пропажу и возврат интернета без повторения фраз каждую секунду."""

    def __init__(self, speaker: Optional[Callable[[str], None]] = None):
        self.speaker = speaker
        self.last_internet_state: Optional[bool] = None

    def check(self) -> NetworkSnapshot:
        snapshot = NetworkSnapshot(
            wifi_connected=is_wifi_connected(),
            internet_connected=has_internet(),
            ip_address=get_ip_address(),
            hostname=get_hostname(),
        )

        if self.last_internet_state is True and not snapshot.internet_connected:
            self._say_once("Интернет пропал. Я все еще умею ездить, фотографировать и шутить простыми шутками.")
        elif self.last_internet_state is False and snapshot.internet_connected:
            self._say_once("Интернет вернулся. Мой ум снова подключен к облакам.")

        self.last_internet_state = snapshot.internet_connected
        return snapshot

    def _say_once(self, text: str) -> None:
        if self.speaker:
            self.speaker(text)
