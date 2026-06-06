"""Маленькие помощники, чтобы робот ехал мягко, а не дергался."""

from __future__ import annotations

from dataclasses import dataclass


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Держит число внутри безопасных границ."""
    return max(minimum, min(maximum, value))


def apply_deadzone(value: float, deadzone: float) -> float:
    """Игнорирует крошечный шум стика и растягивает остальное до -1..1."""
    value = clamp(float(value), -1.0, 1.0)
    deadzone = clamp(float(deadzone), 0.0, 0.95)

    if abs(value) <= deadzone:
        return 0.0

    sign = 1.0 if value > 0 else -1.0
    return sign * ((abs(value) - deadzone) / (1.0 - deadzone))


def expo_curve(value: float, exponent: float) -> float:
    """Делает маленькие движения стика мягче, но оставляет полную силу у края."""
    value = clamp(float(value), -1.0, 1.0)
    exponent = max(1.0, float(exponent))
    sign = 1.0 if value >= 0 else -1.0
    return sign * (abs(value) ** exponent)


@dataclass
class Smoother:
    """Простой сглаживатель."""

    alpha: float = 0.25
    value: float = 0.0

    def update(self, target: float) -> float:
        self.alpha = clamp(self.alpha, 0.0, 1.0)
        self.value = self.value + (target - self.value) * self.alpha
        return self.value

    def reset(self, value: float = 0.0) -> None:
        self.value = float(value)


@dataclass
class RateLimiter:
    """Ограничивает скорость изменения числа."""

    rate_per_second: float
    initial_value: float = 0.0

    def __post_init__(self) -> None:
        self.value = float(self.initial_value)

    def update(self, target: float, dt: float) -> float:
        max_step = max(0.0, float(self.rate_per_second)) * max(0.0, float(dt))
        delta = float(target) - self.value

        if abs(delta) <= max_step:
            self.value = float(target)
        else:
            self.value += max_step if delta > 0 else -max_step

        return self.value

    def reset(self, value: float = 0.0) -> None:
        self.value = float(value)
