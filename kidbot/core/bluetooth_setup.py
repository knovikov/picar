"""Bluetooth setup helpers for pairing a simple controller from the web UI."""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence

logger = logging.getLogger("kidbot.controller")

CommandRunner = Callable[..., object]
BLUETOOTH_ADDRESS_RE = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True)
class BluetoothDevice:
    address: str
    name: str
    connected: bool = False
    paired: bool = False
    trusted: bool = False


@dataclass(frozen=True)
class BluetoothActionResult:
    success: bool
    message: str
    stdout: str = ""
    stderr: str = ""


def scan_bluetooth_devices(runner: CommandRunner = subprocess.run) -> list[BluetoothDevice]:
    _run_bluetooth_command(["bluetoothctl", "power", "on"], runner=runner, timeout=5)
    scan_result = _run_bluetooth_command(["bluetoothctl", "--timeout", "12", "scan", "on"], runner=runner, timeout=15)
    _run_bluetooth_command(["bluetoothctl", "scan", "off"], runner=runner, timeout=5)

    devices_result = _run_bluetooth_command(["bluetoothctl", "devices"], runner=runner, timeout=5)
    if getattr(devices_result, "returncode", 1) != 0:
        logger.warning("bluetooth scan failed: %s", getattr(devices_result, "stderr", ""))
        return []

    paired = {
        device.address
        for device in parse_bluetooth_devices(
            getattr(_run_bluetooth_command(["bluetoothctl", "devices", "Paired"], runner=runner, timeout=5), "stdout", "")
        )
    }
    connected = {
        device.address
        for device in parse_bluetooth_devices(
            getattr(_run_bluetooth_command(["bluetoothctl", "devices", "Connected"], runner=runner, timeout=5), "stdout", "")
        )
    }

    devices = []
    found_devices = parse_bluetooth_devices(
        f"{getattr(scan_result, 'stdout', '')}\n{getattr(devices_result, 'stdout', '')}"
    )
    for device in found_devices:
        devices.append(
            BluetoothDevice(
                address=device.address,
                name=device.name,
                paired=device.address in paired,
                connected=device.address in connected,
                trusted=device.trusted,
            )
        )
    return devices


def parse_bluetooth_devices(output: str) -> list[BluetoothDevice]:
    devices: list[BluetoothDevice] = []
    seen: set[str] = set()
    for line in output.splitlines():
        line = ANSI_RE.sub("", line).strip()
        device_index = line.find("Device ")
        if device_index < 0:
            continue
        line = line[device_index:]
        parts = line.split(maxsplit=2)
        if len(parts) < 2 or not is_valid_bluetooth_address(parts[1]):
            continue
        address = parts[1].upper()
        if address in seen:
            continue
        name = parts[2].strip() if len(parts) > 2 else "Bluetooth device"
        devices.append(BluetoothDevice(address=address, name=name or address))
        seen.add(address)
    return devices


def connect_bluetooth_device(
    address: str,
    runner: CommandRunner = subprocess.run,
    use_sudo: bool = False,
) -> BluetoothActionResult:
    address = address.strip().upper()
    if not is_valid_bluetooth_address(address):
        return BluetoothActionResult(False, "Выбери Bluetooth-устройство из списка.")

    _run_bluetooth_command(["bluetoothctl", "power", "on"], runner=runner, use_sudo=use_sudo, timeout=5)
    _run_bluetooth_command(["bluetoothctl", "--timeout", "8", "scan", "on"], runner=runner, use_sudo=use_sudo, timeout=11)
    _run_bluetooth_command(["bluetoothctl", "scan", "off"], runner=runner, use_sudo=use_sudo, timeout=5)

    script_commands = [
        "power on",
        "pairable on",
        "agent NoInputNoOutput",
        "default-agent",
        f"pair {address}",
        f"trust {address}",
        f"connect {address}",
        f"info {address}",
        "quit",
    ]
    result = _run_bluetooth_script(script_commands, runner=runner, use_sudo=use_sudo, timeout=45)
    output = f"{getattr(result, 'stdout', '')}\n{getattr(result, 'stderr', '')}"

    if getattr(result, "returncode", 1) != 0 or _has_bluetooth_failure(output):
        return BluetoothActionResult(
            False,
            "Не получилось подключить пульт. Включи pairing mode и попробуй еще раз.",
            getattr(result, "stdout", ""),
            getattr(result, "stderr", ""),
        )

    if "Connected: yes" not in output and "Connection successful" not in output:
        return BluetoothActionResult(
            False,
            "Пульт найден, но не подключился. Попробуй pairing mode еще раз.",
            getattr(result, "stdout", ""),
            getattr(result, "stderr", ""),
        )

    return BluetoothActionResult(
        True,
        "Пульт подключается. Через пару секунд статус должен стать 'подключен'.",
        getattr(result, "stdout", ""),
        "",
    )


def disconnect_bluetooth_device(
    address: str,
    runner: CommandRunner = subprocess.run,
    use_sudo: bool = False,
) -> BluetoothActionResult:
    address = address.strip().upper()
    if not is_valid_bluetooth_address(address):
        return BluetoothActionResult(False, "Выбери Bluetooth-устройство из списка.")
    result = _run_bluetooth_command(["bluetoothctl", "disconnect", address], runner=runner, use_sudo=use_sudo, timeout=15)
    if getattr(result, "returncode", 1) == 0:
        return BluetoothActionResult(True, "Пульт отключен.", getattr(result, "stdout", ""), "")
    return BluetoothActionResult(False, "Не получилось отключить пульт.", getattr(result, "stdout", ""), getattr(result, "stderr", ""))


def is_valid_bluetooth_address(address: str) -> bool:
    return bool(BLUETOOTH_ADDRESS_RE.match(address.strip()))


def _run_bluetooth_command(
    command: Sequence[str],
    runner: CommandRunner,
    use_sudo: bool = False,
    timeout: int = 30,
) -> object:
    full_command = ["sudo", "-n", *command] if use_sudo else list(command)
    logger.debug("bluetooth command: %s", " ".join(full_command))
    try:
        result = runner(full_command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(full_command, 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(full_command, 124, exc.stdout or "", exc.stderr or "timeout")

    stderr = getattr(result, "stderr", "")
    if (
        getattr(result, "returncode", 1) != 0
        and not use_sudo
        and ("permission" in stderr.lower() or "not authorized" in stderr.lower())
    ):
        return _run_bluetooth_command(command, runner=runner, use_sudo=True, timeout=timeout)
    return result


def _run_bluetooth_script(
    commands: Sequence[str],
    runner: CommandRunner,
    use_sudo: bool = False,
    timeout: int = 45,
) -> object:
    full_command = ["bluetoothctl", "--agent", "NoInputNoOutput"]
    if use_sudo:
        full_command = ["sudo", "-n", *full_command]
    logger.debug("bluetooth script: %s", " ; ".join(commands))
    try:
        return runner(
            full_command,
            input="\n".join(commands) + "\n",
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(full_command, 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(full_command, 124, exc.stdout or "", exc.stderr or "timeout")


def _has_bluetooth_failure(output: str) -> bool:
    lowered = output.lower()
    failures = ("failed to pair", "failed to connect", "not available", "not permitted", "authentication")
    return any(failure in lowered for failure in failures)
