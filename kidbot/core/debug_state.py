"""Realtime debug snapshots for the web debug page."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Iterable

from kidbot.core.controller import JoystickState


class DebugStateStore:
    def __init__(self, max_logs: int = 120, max_events: int = 80):
        self._lock = threading.Lock()
        self._logs = deque(maxlen=max_logs)
        self._events = deque(maxlen=max_events)
        self._controller: dict[str, Any] = _empty_controller()
        self._drive: dict[str, Any] = {"speed": 0.0, "steering_angle": 0.0}
        self._head: dict[str, Any] = {"pan_delta": 0.0, "tilt_delta": 0.0}
        self._front_sensor: dict[str, Any] = _empty_front_sensor()

    def record_controller(
        self,
        state: JoystickState,
        named_buttons: dict[str, bool],
        events: Iterable[tuple[str, str]],
    ) -> None:
        with self._lock:
            self._controller = {
                "connected": state.connected,
                "name": state.name,
                "axes": {str(key): round(value, 3) for key, value in state.axes.items()},
                "buttons": {str(key): value for key, value in state.buttons.items()},
                "named_buttons": dict(named_buttons),
                "hats": {str(key): value for key, value in state.hats.items()},
                "timestamp": round(time.time(), 3),
            }
            for button, event in events:
                self._events.append({"button": button, "event": event, "time": round(time.time(), 3)})

    def record_drive(self, speed: float, steering_angle: float) -> None:
        with self._lock:
            self._drive = {"speed": round(speed, 3), "steering_angle": round(steering_angle, 3)}

    def record_head(self, pan_delta: float, tilt_delta: float) -> None:
        with self._lock:
            self._head = {"pan_delta": round(pan_delta, 3), "tilt_delta": round(tilt_delta, 3)}

    def record_front_sensor(self, distance_cm: float | None, status: str = "ok") -> None:
        with self._lock:
            self._front_sensor = {
                "distance_cm": None if distance_cm is None else round(float(distance_cm), 2),
                "status": status,
                "timestamp": round(time.time(), 3),
            }

    def append_log(self, level: str, logger_name: str, message: str) -> None:
        with self._lock:
            self._logs.append(
                {
                    "time": round(time.time(), 3),
                    "level": level,
                    "logger": logger_name,
                    "message": message,
                }
            )

    def snapshot(self, status: dict[str, object] | None = None) -> dict[str, object]:
        with self._lock:
            return {
                "time": round(time.time(), 3),
                "status": status or {},
                "controller": dict(self._controller),
                "drive": dict(self._drive),
                "head": dict(self._head),
                "front_sensor": dict(self._front_sensor),
                "events": list(self._events),
                "logs": list(self._logs),
            }


class DebugLogHandler(logging.Handler):
    def __init__(self, store: DebugStateStore):
        super().__init__(level=logging.DEBUG)
        self.store = store

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self.store.append_log(record.levelname, record.name, message)
        except Exception:
            self.handleError(record)


def attach_debug_log_handler(store: DebugStateStore) -> None:
    root = logging.getLogger()
    if any(isinstance(handler, DebugLogHandler) for handler in root.handlers):
        return
    handler = DebugLogHandler(store)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    root.addHandler(handler)


def _empty_controller() -> dict[str, Any]:
    return {
        "connected": False,
        "name": "not connected",
        "axes": {},
        "buttons": {},
        "named_buttons": {},
        "hats": {},
        "timestamp": round(time.time(), 3),
    }


def _empty_front_sensor() -> dict[str, Any]:
    return {
        "distance_cm": None,
        "status": "waiting",
        "timestamp": round(time.time(), 3),
    }
