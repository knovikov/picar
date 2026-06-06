"""Загрузка настроек KidBot."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Mapping


DEFAULT_CONFIG: dict[str, Any] = {
    "robot": {
        "name": "KidBot",
        "child_name": "",
        "child_age": 7,
        "version": "0.1.0",
        "mock": False,
    },
    "paths": {
        "photos": "photos",
        "logs": "logs",
        "sounds": "assets/sounds",
        "music": "assets/music",
        "stories": "assets/stories",
    },
    "controller": {
        "device_index": 0,
        "poll_hz": 30,
        "watchdog_timeout_seconds": 1.0,
        "axes": {"steering": 0, "throttle": 3},
        "buttons": {
            "a": 0,
            "b": 1,
            "x": 2,
            "y": 3,
            "l1": 4,
            "r1": 5,
            "l2": 6,
            "r2": 7,
            "select": 8,
            "start": 9,
        },
        "dpad": {"hat_index": 0},
    },
    "steering": {"deadzone": 0.1, "max_angle": 30, "curve": 1.6, "smoothing_alpha": 0.25},
    "speed": {
        "deadzone": 0.1,
        "max_forward": 100,
        "max_reverse": 100,
        "acceleration_per_second": 180,
        "braking_per_second": 260,
    },
    "head": {"pan_min": -45, "pan_max": 45, "tilt_min": -30, "tilt_max": 30, "step": 5},
    "front_sensor": {"poll_hz": 10, "stop_distance_cm": 10},
    "web": {"host": "0.0.0.0", "port": 8080},
    "openai": {
        "chat_model": "gpt-5-mini",
        "vision_model": "gpt-5-mini",
        "stt_model": "gpt-4o-mini-transcribe",
        "tts_model": "gpt-4o-mini-tts",
    },
    "voice": {"espeak_voice": "ru", "espeak_speed": 150, "use_openai_tts": True},
    "setup_ap": {
        "enabled": True,
        "auto_start_when_no_wifi": True,
        "boot_check_wait_seconds": 45,
        "boot_check_poll_seconds": 3,
        "ssid": "KidBot-Setup",
        "password": "kidbot1234",
        "interface": "wlan0",
        "address": "192.168.4.1/24",
    },
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path or os.environ.get("KIDBOT_CONFIG", "config.yaml"))
    if not config_path.is_absolute():
        config_path = project_root() / config_path

    config = copy.deepcopy(DEFAULT_CONFIG)
    if config_path.exists():
        config = deep_merge(config, _read_yaml(config_path))

    if os.environ.get("KIDBOT_MOCK") == "1":
        config["robot"]["mock"] = True

    return config


def deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def resolve_path(config: Mapping[str, Any], key: str) -> Path:
    paths = config.get("paths", {})
    raw = paths.get(key, key) if isinstance(paths, Mapping) else key
    path = Path(str(raw))
    if path.is_absolute():
        return path
    return project_root() / path


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        return _read_simple_yaml(path)

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a YAML mapping.")
    return data


def _read_simple_yaml(path: Path) -> dict[str, Any]:
    """Читает простой YAML, если PyYAML еще не установлен."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if ":" not in raw_line:
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        key, raw_value = raw_line.strip().split(":", 1)
        value_text = raw_value.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if value_text == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_simple_yaml_value(value_text)

    return root


def _parse_simple_yaml_value(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value
