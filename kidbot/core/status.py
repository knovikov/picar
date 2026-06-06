"""Снимки статуса для голоса и веб-страницы."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BatteryStatus:
    percentage: Optional[float] = None
    voltage: Optional[float] = None
    status: str = "unknown"
    source: str = ""
    updated_at: Optional[float] = None


@dataclass
class SystemStatus:
    robot_name: str
    version: str
    wifi_connected: bool
    internet_connected: bool
    ip_address: str
    controller_connected: bool
    latest_error: Optional[str]
    uptime_seconds: float
    battery: BatteryStatus = field(default_factory=BatteryStatus)

    def to_sentence(self) -> str:
        wifi = "Wi-Fi подключен" if self.wifi_connected else "Wi-Fi не подключен"
        internet = "Интернет работает" if self.internet_connected else "Интернета сейчас нет"
        controller = "пульт подключен" if self.controller_connected else "пульт не найден"
        battery = _battery_sentence(self.battery)
        error = "Ошибок нет" if not self.latest_error else f"Последняя ошибка: {self.latest_error}"
        return (
            f"Я {self.robot_name}. {wifi}. Мой адрес {self.ip_address}. "
            f"{internet}. {controller}. {battery}. {error}. Я готов к приключениям."
        )


class StatusTracker:
    def __init__(self, robot_name: str, version: str):
        self.robot_name = robot_name
        self.version = version
        self.started_at = time.monotonic()
        self.wifi_connected = False
        self.internet_connected = False
        self.ip_address = "unknown"
        self.controller_connected = False
        self.latest_error: Optional[str] = None
        self.battery = BatteryStatus()

    def set_network(self, wifi_connected: bool, internet_connected: bool, ip_address: str) -> None:
        self.wifi_connected = wifi_connected
        self.internet_connected = internet_connected
        self.ip_address = ip_address

    def set_controller_connected(self, connected: bool) -> None:
        self.controller_connected = connected

    def set_battery(
        self,
        percentage: Optional[float],
        voltage: Optional[float],
        status: str = "unknown",
        source: str = "",
    ) -> None:
        self.battery = BatteryStatus(
            percentage=percentage,
            voltage=voltage,
            status=status,
            source=source,
            updated_at=round(time.time(), 3),
        )

    def set_error(self, error: Exception | str) -> None:
        self.latest_error = str(error)

    def clear_error(self) -> None:
        self.latest_error = None

    def snapshot(self) -> SystemStatus:
        return SystemStatus(
            robot_name=self.robot_name,
            version=self.version,
            wifi_connected=self.wifi_connected,
            internet_connected=self.internet_connected,
            ip_address=self.ip_address,
            controller_connected=self.controller_connected,
            latest_error=self.latest_error,
            uptime_seconds=time.monotonic() - self.started_at,
            battery=self.battery,
        )


def _battery_sentence(battery: BatteryStatus) -> str:
    if battery.percentage is not None:
        return f"Батарея {battery.percentage:.0f} процентов"
    if battery.voltage is not None:
        return f"Батарея {battery.voltage:.2f} вольт"
    return "Батарея пока без данных"
