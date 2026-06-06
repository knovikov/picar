"""Boot-time Wi-Fi recovery helpers."""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from kidbot.core.config import load_config
from kidbot.core.network import is_wifi_connected
from kidbot.core.wifi_setup import AccessPointConfig, WiFiActionResult, start_access_point

logger = logging.getLogger("kidbot.network")


@dataclass(frozen=True)
class NetworkRecoveryResult:
    success: bool
    action: str
    message: str


def ensure_setup_access_point(
    config: Mapping[str, Any],
    *,
    is_wifi_connected_fn: Callable[[], bool] = is_wifi_connected,
    start_access_point_fn: Callable[..., WiFiActionResult] = start_access_point,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> NetworkRecoveryResult:
    setup_ap_config = _setup_ap_config(config)
    if not bool(setup_ap_config.get("enabled", True)) or not bool(setup_ap_config.get("auto_start_when_no_wifi", True)):
        return NetworkRecoveryResult(True, "disabled", "Setup access point auto-start is disabled.")

    wait_seconds = max(0.0, float(setup_ap_config.get("boot_check_wait_seconds", 45)))
    poll_seconds = max(1.0, float(setup_ap_config.get("boot_check_poll_seconds", 3)))

    if wait_for_wifi(is_wifi_connected_fn, wait_seconds, poll_seconds, sleeper=sleeper, monotonic=monotonic):
        return NetworkRecoveryResult(True, "wifi-connected", "Wi-Fi is already connected; setup access point is not needed.")

    access_point = build_access_point_config(setup_ap_config)
    result = start_access_point_fn(access_point, use_sudo=True)
    if result.success:
        return NetworkRecoveryResult(True, "started", result.message)
    return NetworkRecoveryResult(False, "failed", result.message)


def wait_for_wifi(
    is_wifi_connected_fn: Callable[[], bool],
    wait_seconds: float,
    poll_seconds: float,
    *,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> bool:
    deadline = monotonic() + max(0.0, wait_seconds)
    while True:
        if is_wifi_connected_fn():
            return True
        remaining = deadline - monotonic()
        if remaining <= 0:
            return False
        sleeper(min(max(1.0, poll_seconds), remaining))


def build_access_point_config(setup_ap_config: Mapping[str, Any]) -> AccessPointConfig:
    return AccessPointConfig(
        ssid=str(setup_ap_config.get("ssid", "KidBot-Setup")),
        password=str(setup_ap_config.get("password", "kidbot1234")),
        interface=str(setup_ap_config.get("interface", "wlan0")),
        address=str(setup_ap_config.get("address", "192.168.4.1/24")),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start KidBot setup AP if saved Wi-Fi does not connect after boot.")
    parser.add_argument("--config", type=Path, default=None, help="Path to config.yaml")
    parser.add_argument("--wait-seconds", type=float, default=None, help="Override setup_ap.boot_check_wait_seconds")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    config = load_config(args.config)
    if args.wait_seconds is not None:
        setup_ap_config = dict(_setup_ap_config(config))
        setup_ap_config["boot_check_wait_seconds"] = args.wait_seconds
        config["setup_ap"] = setup_ap_config

    result = ensure_setup_access_point(config)
    log_method = logger.info if result.success else logger.error
    log_method("network recovery: %s - %s", result.action, result.message)
    print(result.message)
    return 0 if result.success else 1


def _setup_ap_config(config: Mapping[str, Any]) -> Mapping[str, Any]:
    setup_ap_config = config.get("setup_ap", {})
    return setup_ap_config if isinstance(setup_ap_config, Mapping) else {}
