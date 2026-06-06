"""Снимки статуса для голоса и веб-страницы."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


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

    def to_sentence(self) -> str:
        wifi = "Wi-Fi подключен" if self.wifi_connected else "Wi-Fi не подключен"
        internet = "Интернет работает" if self.internet_connected else "Интернета сейчас нет"
        controller = "пульт подключен" if self.controller_connected else "пульт не найден"
        error = "Ошибок нет" if not self.latest_error else f"Последняя ошибка: {self.latest_error}"
        return (
            f"Я {self.robot_name}. {wifi}. Мой адрес {self.ip_address}. "
            f"{internet}. {controller}. {error}. Я готов к приключениям."
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

    def set_network(self, wifi_connected: bool, internet_connected: bool, ip_address: str) -> None:
        self.wifi_connected = wifi_connected
        self.internet_connected = internet_connected
        self.ip_address = ip_address

    def set_controller_connected(self, connected: bool) -> None:
        self.controller_connected = connected

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
        )
