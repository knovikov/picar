"""Адаптер железа робота с безопасным mock-режимом."""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from kidbot.core.smoothing import clamp

logger = logging.getLogger("kidbot.robot")


class RobotHardware:
    """Говорит с PiCar-X, а без железа запоминает mock-команды."""

    def __init__(self, config: dict[str, Any], mock: bool = False):
        self.config = config
        self.mock = mock
        self._picar = None
        self.last_speed = 0.0
        self.last_steering_angle = 0.0
        self.pan = 0.0
        self.tilt = 0.0

        if not mock:
            self._connect_hardware()
        if self.mock:
            logger.info("RobotHardware is running in mock mode")

    def _connect_hardware(self) -> None:
        try:
            from picarx import Picarx

            self._picar = Picarx()
        except Exception as exc:
            logger.warning("PiCar-X hardware unavailable; switching to mock mode: %s", exc)
            self.mock = True

    def drive(self, speed: float, steering_angle: float) -> None:
        self.last_speed = float(speed)
        self.last_steering_angle = float(steering_angle)

        if self.mock:
            logger.debug("mock drive speed=%s steering=%s", speed, steering_angle)
            return

        assert self._picar is not None
        self._picar.set_dir_servo_angle(steering_angle)
        if speed > 0:
            self._picar.forward(speed)
        elif speed < 0:
            self._picar.backward(abs(speed))
        else:
            self._picar.stop()

    def stop(self) -> None:
        self.drive(0.0, 0.0)

    def emergency_stop(self) -> None:
        logger.warning("emergency stop requested")
        self.stop()

    def set_head(self, pan: float, tilt: float) -> None:
        head_config = self.config.get("head", {})
        pan_min = float(head_config.get("pan_min", -45))
        pan_max = float(head_config.get("pan_max", 45))
        tilt_min = float(head_config.get("tilt_min", -30))
        tilt_max = float(head_config.get("tilt_max", 30))
        self.pan = clamp(float(pan), pan_min, pan_max)
        self.tilt = clamp(float(tilt), tilt_min, tilt_max)

        if self.mock:
            logger.debug("mock head pan=%s tilt=%s", self.pan, self.tilt)
            return

        assert self._picar is not None
        if hasattr(self._picar, "set_cam_pan_angle"):
            self._picar.set_cam_pan_angle(self.pan)
        if hasattr(self._picar, "set_cam_tilt_angle"):
            self._picar.set_cam_tilt_angle(self.tilt)

    def move_head(self, pan_delta: float, tilt_delta: float) -> None:
        self.set_head(self.pan + pan_delta, self.tilt + tilt_delta)

    def read_front_distance_cm(self) -> float | None:
        if self.mock or self._picar is None:
            return None

        try:
            raw_distance = self._read_front_distance_raw()
            if raw_distance is None:
                return None
            distance = float(raw_distance)
        except Exception as exc:
            logger.debug("front distance sensor unavailable: %s", exc)
            return None

        if distance < 0:
            return None
        return _round_distance_cm(distance)

    def read_battery(self) -> dict[str, Any]:
        battery_config = self.config.get("battery", {})
        source = "mock" if self.mock else "hardware"
        voltage = self._mock_battery_voltage(battery_config) if self.mock else self.read_battery_voltage()
        if voltage is None:
            return {
                "percentage": None,
                "voltage": None,
                "status": "no-data",
                "source": source,
            }

        percentage = _battery_percentage(
            voltage,
            min_voltage=float(battery_config.get("empty_voltage", 6.4)),
            max_voltage=float(battery_config.get("full_voltage", 8.4)),
        )
        return {
            "percentage": percentage,
            "voltage": _round_voltage(voltage),
            "status": _battery_status(
                voltage,
                low_voltage=float(battery_config.get("low_voltage", 6.8)),
                critical_voltage=float(battery_config.get("critical_voltage", 6.4)),
            ),
            "source": source,
        }

    def read_battery_voltage(self) -> float | None:
        if self._picar is None:
            return None

        try:
            raw_voltage = self._read_battery_voltage_raw()
            voltage = _coerce_voltage(raw_voltage)
        except Exception as exc:
            logger.debug("battery sensor unavailable: %s", exc)
            return None

        if voltage is None or voltage <= 0:
            return None
        return _round_voltage(voltage)

    def _read_front_distance_raw(self) -> Any:
        assert self._picar is not None
        for method_name in ("get_distance", "get_ultrasonic_distance"):
            method = getattr(self._picar, method_name, None)
            if callable(method):
                return method()

        ultrasonic = getattr(self._picar, "ultrasonic", None)
        read = getattr(ultrasonic, "read", None)
        if callable(read):
            return read()
        return None

    def _read_battery_voltage_raw(self) -> Any:
        assert self._picar is not None
        for owner in (self._picar, getattr(self._picar, "robot_hat", None), getattr(self._picar, "hat", None)):
            if owner is None:
                continue
            for method_name in (
                "get_battery_voltage",
                "read_battery_voltage",
                "battery_voltage",
                "get_voltage",
                "read_voltage",
                "power_read",
            ):
                method = getattr(owner, method_name, None)
                if callable(method):
                    return method()
            for attr_name in ("battery_voltage", "voltage"):
                value = getattr(owner, attr_name, None)
                if value is not None and not callable(value):
                    return value
        return None

    def _mock_battery_voltage(self, battery_config: dict[str, Any]) -> float | None:
        if "mock_voltage" not in battery_config:
            return None
        return _coerce_voltage(battery_config.get("mock_voltage"))

    def cleanup(self) -> None:
        self.stop()


def _round_distance_cm(distance: float) -> float:
    return float(Decimal(str(distance)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _round_voltage(voltage: float) -> float:
    return float(Decimal(str(voltage)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _coerce_voltage(raw_voltage: Any) -> float | None:
    if raw_voltage is None:
        return None
    if isinstance(raw_voltage, dict):
        for key in ("voltage", "battery_voltage", "value"):
            if key in raw_voltage:
                return _coerce_voltage(raw_voltage[key])
        return None
    if isinstance(raw_voltage, (list, tuple)):
        if not raw_voltage:
            return None
        return _coerce_voltage(raw_voltage[0])

    voltage = float(raw_voltage)
    if voltage > 1000:
        voltage = voltage / 1000.0
    return voltage


def _battery_percentage(voltage: float, min_voltage: float, max_voltage: float) -> float:
    if max_voltage <= min_voltage:
        return 0.0
    percentage = (voltage - min_voltage) / (max_voltage - min_voltage) * 100.0
    return round(clamp(percentage, 0.0, 100.0), 1)


def _battery_status(voltage: float, low_voltage: float, critical_voltage: float) -> str:
    if voltage <= critical_voltage:
        return "critical"
    if voltage <= low_voltage:
        return "low"
    return "ok"
