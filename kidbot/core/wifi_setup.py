"""Wi-Fi setup helpers and setup access point mode."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence

logger = logging.getLogger("kidbot.network")

CommandRunner = Callable[..., object]


@dataclass(frozen=True)
class WiFiNetwork:
    ssid: str
    signal: int
    security: str


@dataclass(frozen=True)
class WiFiActionResult:
    success: bool
    message: str
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class AccessPointConfig:
    ssid: str = "KidBot-Setup"
    password: str = "kidbot1234"
    interface: str = "wlan0"
    address: str = "192.168.4.1/24"


def scan_wifi_networks(runner: CommandRunner = subprocess.run) -> list[WiFiNetwork]:
    try:
        result = runner(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("nmcli is not installed; wifi scan is unavailable")
        return []
    if getattr(result, "returncode", 1) != 0:
        logger.warning("wifi scan failed: %s", getattr(result, "stderr", ""))
        return []
    return parse_nmcli_wifi_list(getattr(result, "stdout", ""))


def parse_nmcli_wifi_list(output: str) -> list[WiFiNetwork]:
    networks: list[WiFiNetwork] = []
    seen: set[str] = set()
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = _split_nmcli_line(line)
        if len(parts) < 3:
            continue
        ssid, signal_text, security = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not ssid or ssid in seen:
            continue
        try:
            signal = int(signal_text)
        except ValueError:
            signal = 0
        networks.append(WiFiNetwork(ssid=ssid, signal=signal, security=security or "open"))
        seen.add(ssid)
    return sorted(networks, key=lambda network: network.signal, reverse=True)


def connect_to_wifi(
    ssid: str,
    password: str,
    runner: CommandRunner = subprocess.run,
    use_sudo: bool = False,
) -> WiFiActionResult:
    if not ssid.strip():
        return WiFiActionResult(False, "Название сети пустое.")

    command = ["nmcli", "dev", "wifi", "connect", ssid.strip()]
    if password:
        command.extend(["password", password])
    result = _run_network_command(command, runner=runner, use_sudo=use_sudo)
    if getattr(result, "returncode", 1) == 0:
        return WiFiActionResult(True, f"Подключаюсь к сети {ssid}.", getattr(result, "stdout", ""), "")
    return WiFiActionResult(False, "Не получилось подключиться к Wi-Fi.", getattr(result, "stdout", ""), getattr(result, "stderr", ""))


def start_access_point(
    config: AccessPointConfig,
    runner: CommandRunner = subprocess.run,
    use_sudo: bool = False,
) -> WiFiActionResult:
    last_result = None
    for index, command in enumerate(build_access_point_commands(config)):
        last_result = _run_network_command(command, runner=runner, use_sudo=use_sudo)
        if index == 0 and getattr(last_result, "returncode", 1) != 0:
            continue
        if getattr(last_result, "returncode", 1) != 0:
            return WiFiActionResult(
                False,
                "Не получилось включить точку доступа KidBot.",
                getattr(last_result, "stdout", ""),
                getattr(last_result, "stderr", ""),
            )
    return WiFiActionResult(
        True,
        f"Точка доступа {config.ssid} включена. Открой http://192.168.4.1:8080",
        getattr(last_result, "stdout", "") if last_result else "",
        "",
    )


def stop_access_point(
    ssid: str = "KidBot-Setup",
    runner: CommandRunner = subprocess.run,
    use_sudo: bool = False,
) -> WiFiActionResult:
    result = _run_network_command(["nmcli", "connection", "down", ssid], runner=runner, use_sudo=use_sudo)
    if getattr(result, "returncode", 1) == 0:
        return WiFiActionResult(True, f"Точка доступа {ssid} выключена.", getattr(result, "stdout", ""), "")
    return WiFiActionResult(False, "Не получилось выключить точку доступа.", getattr(result, "stdout", ""), getattr(result, "stderr", ""))


def build_access_point_commands(config: AccessPointConfig) -> list[list[str]]:
    return [
        ["nmcli", "connection", "delete", config.ssid],
        [
            "nmcli",
            "connection",
            "add",
            "type",
            "wifi",
            "ifname",
            config.interface,
            "con-name",
            config.ssid,
            "autoconnect",
            "no",
            "ssid",
            config.ssid,
        ],
        [
            "nmcli",
            "connection",
            "modify",
            config.ssid,
            "802-11-wireless.mode",
            "ap",
            "802-11-wireless.band",
            "bg",
            "ipv4.method",
            "shared",
            "ipv4.addresses",
            config.address,
            "wifi-sec.key-mgmt",
            "wpa-psk",
            "wifi-sec.psk",
            config.password,
        ],
        ["nmcli", "connection", "up", config.ssid],
    ]


def _run_network_command(
    command: Sequence[str],
    runner: CommandRunner,
    use_sudo: bool,
) -> object:
    full_command = ["sudo", "-n", *command] if use_sudo else list(command)
    logger.debug("network command: %s", " ".join(full_command))
    try:
        result = runner(full_command, capture_output=True, text=True, timeout=30, check=False)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(full_command, 127, "", str(exc))
    if (
        getattr(result, "returncode", 1) != 0
        and not use_sudo
        and ("permission" in getattr(result, "stderr", "").lower() or "not authorized" in getattr(result, "stderr", "").lower())
    ):
        return _run_network_command(command, runner=runner, use_sudo=True)
    return result


def _split_nmcli_line(line: str) -> list[str]:
    parts: list[str] = []
    current = []
    escaped = False
    for character in line:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == ":":
            parts.append("".join(current))
            current = []
        else:
            current.append(character)
    parts.append("".join(current))
    return parts
