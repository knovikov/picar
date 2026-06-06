"""Простые правила езды для KidBot.

Этот файл можно читать ребенку вместе со взрослым.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from kidbot.core.smoothing import apply_deadzone, clamp, expo_curve


@dataclass(frozen=True)
class DriveCommand:
    """Что мы просим сделать колеса и руль."""

    speed: float
    steering_angle: float


def _setting(config: Mapping[str, object], section: str, name: str, default: float) -> float:
    group = config.get(section, {})
    if isinstance(group, Mapping):
        return float(group.get(name, default))
    return default


def build_drive_command(
    steering_axis: float,
    throttle_axis: float,
    config: Mapping[str, object],
) -> DriveCommand:
    """Превращает числа от стика в безопасную команду для робота."""
    steering_deadzone = _setting(config, "steering", "deadzone", 0.1)
    steering_curve = _setting(config, "steering", "curve", 1.6)
    max_angle = _setting(config, "steering", "max_angle", 30.0)

    speed_deadzone = _setting(config, "speed", "deadzone", 0.1)
    max_forward = _setting(config, "speed", "max_forward", 40.0)
    max_reverse = _setting(config, "speed", "max_reverse", 40.0)

    # Левый стик поворачивает нос робота.
    turn = apply_deadzone(steering_axis, steering_deadzone)
    turn = expo_curve(turn, steering_curve)
    steering_angle = clamp(turn * max_angle, -max_angle, max_angle)

    # На многих геймпадах "вверх" это -1, поэтому мы переворачиваем знак.
    throttle = -apply_deadzone(throttle_axis, speed_deadzone)
    if throttle >= 0:
        speed = throttle * max_forward
    else:
        speed = throttle * max_reverse

    return DriveCommand(speed=speed, steering_angle=steering_angle)


def emergency_stop_command() -> DriveCommand:
    """Остановиться прямо сейчас."""
    # Тут мы говорим колесам: "Спокойно, стоим!"
    return DriveCommand(speed=0.0, steering_angle=0.0)


def child_friendly_drive_message(command: DriveCommand) -> str:
    """Коротко объясняет, что сейчас делает KidBot."""
    if command.speed == 0:
        return "Я стою и думаю о приключениях."
    if command.speed > 0:
        return "Еду вперед!"
    return "Аккуратно сдаю назад."
