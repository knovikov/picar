"""Помощники безопасности, чтобы робот останавливался при проблемах."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class SafetyWatchdog:
    timeout_seconds: float
    last_controller_event: float = 0.0
    stopped_due_to_timeout: bool = False

    def __post_init__(self) -> None:
        self.last_controller_event = time.monotonic()

    def mark_controller_event(self) -> None:
        self.last_controller_event = time.monotonic()
        self.stopped_due_to_timeout = False

    def expired(self) -> bool:
        return time.monotonic() - self.last_controller_event > self.timeout_seconds
