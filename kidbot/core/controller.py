"""Опрос Bluetooth-геймпада через pygame, если он доступен."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Iterable

logger = logging.getLogger("kidbot.controller")


@dataclass
class JoystickState:
    connected: bool = False
    name: str = "not connected"
    axes: dict[int, float] = field(default_factory=dict)
    buttons: dict[int, bool] = field(default_factory=dict)
    hats: dict[int, tuple[int, int]] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)

    def axis(self, index: int, default: float = 0.0) -> float:
        return self.axes.get(index, default)

    def button(self, index: int) -> bool:
        return bool(self.buttons.get(index, False))

    def hat(self, index: int) -> tuple[int, int]:
        return self.hats.get(index, (0, 0))


class ControllerReader:
    """Читает геймпад через pygame и спокойно отключается без Raspberry Pi."""

    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self._pygame = None
        self._joystick = None
        self._connected = False
        self._last_connect_attempt = 0.0
        self.retry_seconds = 2.0

    def connect(self) -> bool:
        self._last_connect_attempt = time.monotonic()
        try:
            import pygame
        except ImportError:
            logger.warning("pygame is not installed; controller is unavailable")
            self._connected = False
            return False

        self._pygame = pygame
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() <= self.device_index:
            logger.warning("no joystick found at index %s", self.device_index)
            self._connected = False
            return False

        self._joystick = pygame.joystick.Joystick(self.device_index)
        self._joystick.init()
        self._connected = True
        logger.info("controller connected: %s", self._joystick.get_name())
        return True

    def poll(self) -> JoystickState:
        if self._pygame is None or self._joystick is None:
            if time.monotonic() - self._last_connect_attempt < self.retry_seconds:
                return JoystickState(connected=False)
            if not self.connect():
                return JoystickState(connected=False)

        assert self._pygame is not None
        assert self._joystick is not None
        self._pygame.event.pump()

        axes = {i: float(self._joystick.get_axis(i)) for i in range(self._joystick.get_numaxes())}
        buttons = {i: bool(self._joystick.get_button(i)) for i in range(self._joystick.get_numbuttons())}
        hats = {i: self._joystick.get_hat(i) for i in range(self._joystick.get_numhats())}

        return JoystickState(
            connected=True,
            name=self._joystick.get_name(),
            axes=axes,
            buttons=buttons,
            hats=hats,
        )


class ButtonTracker:
    """Замечает нажатие, отпускание, двойное нажатие и долгое удержание."""

    def __init__(self, double_press_seconds: float = 0.35, long_press_seconds: float = 0.8):
        self.double_press_seconds = double_press_seconds
        self.long_press_seconds = long_press_seconds
        self.previous: dict[str, bool] = {}
        self.last_press_at: dict[str, float] = {}
        self.pressed_at: dict[str, float] = {}
        self.long_sent: set[str] = set()
        self.combo_pressed_at: dict[str, float] = {}
        self.combo_long_sent: set[str] = set()

    def update(self, pressed_buttons: dict[str, bool], now: float | None = None) -> list[tuple[str, str]]:
        now = now or time.monotonic()
        events: list[tuple[str, str]] = []

        for name, is_pressed in pressed_buttons.items():
            was_pressed = self.previous.get(name, False)
            if is_pressed and not was_pressed:
                previous_press = self.last_press_at.get(name)
                if previous_press is not None and now - previous_press <= self.double_press_seconds:
                    events.append((name, "double"))
                else:
                    events.append((name, "press"))
                self.last_press_at[name] = now
                self.pressed_at[name] = now
                self.long_sent.discard(name)

            if is_pressed and name not in self.long_sent:
                pressed_at = self.pressed_at.get(name, now)
                if now - pressed_at >= self.long_press_seconds:
                    events.append((name, "long"))
                    self.long_sent.add(name)

            if not is_pressed and was_pressed:
                events.append((name, "release"))
                self.pressed_at.pop(name, None)

            self.previous[name] = is_pressed

        return events

    def combo_long_pressed(
        self,
        combo_name: str,
        pressed_buttons: dict[str, bool],
        button_names: tuple[str, ...],
        now: float | None = None,
        hold_seconds: float = 2.0,
    ) -> bool:
        now = now or time.monotonic()
        is_pressed = all(bool(pressed_buttons.get(name, False)) for name in button_names)
        if not is_pressed:
            self.combo_pressed_at.pop(combo_name, None)
            self.combo_long_sent.discard(combo_name)
            return False

        pressed_at = self.combo_pressed_at.setdefault(combo_name, now)
        if combo_name in self.combo_long_sent:
            return False
        if now - pressed_at >= hold_seconds:
            self.combo_long_sent.add(combo_name)
            return True
        return False


def map_named_buttons(state: JoystickState, mapping: dict[str, int]) -> dict[str, bool]:
    return {name: state.button(index) for name, index in mapping.items()}


def print_controller_events() -> None:
    """Печатает сырые значения, чтобы подобрать маппинг 8BitDo."""
    reader = ControllerReader()
    if not reader.connect():
        print("Controller not found. Pair the 8BitDo controller, then try again.")
        return

    print("Press Ctrl+C to stop.")
    try:
        while True:
            state = reader.poll()
            print(f"\nController: {state.name}")
            _print_values("axes", state.axes.items())
            _print_values("buttons", state.buttons.items())
            _print_values("hats / dpad", state.hats.items())
            time.sleep(0.15)
    except KeyboardInterrupt:
        print("\nDone.")


def _print_values(title: str, values: Iterable[tuple[int, object]]) -> None:
    print(title + ":")
    for index, value in values:
        print(f"  {index}: raw={value!r} normalized={value!r}")
