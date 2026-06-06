"""Локальные секреты KidBot, которые нельзя класть в git."""

from __future__ import annotations

import os
import stat
from pathlib import Path


def load_env_file(env_path: Path) -> dict[str, str]:
    env_path = Path(env_path)
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _unquote_env_value(value.strip())
    return values


def apply_env_file(env_path: Path) -> None:
    for key, value in load_env_file(env_path).items():
        os.environ.setdefault(key, value)


def save_openai_api_key(env_path: Path, api_key: str) -> None:
    env_path = Path(env_path)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    values = load_env_file(env_path)
    values["OPENAI_API_KEY"] = api_key.strip()

    lines = [f"{key}={_quote_env_value(value)}" for key, value in sorted(values.items())]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    os.environ["OPENAI_API_KEY"] = values["OPENAI_API_KEY"]


def openai_key_status(env_path: Path) -> dict[str, str]:
    key = os.environ.get("OPENAI_API_KEY") or load_env_file(env_path).get("OPENAI_API_KEY", "")
    return {"state": "set" if key else "not set", "masked": mask_secret(key)}


def mask_secret(value: str) -> str:
    if not value:
        return "not set"
    if len(value) < 10:
        return "set"
    return f"{value[:4]}...{value[-4:]}"


def _quote_env_value(value: str) -> str:
    if any(character.isspace() for character in value) or '"' in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _unquote_env_value(value: str) -> str:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value

