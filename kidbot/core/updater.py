"""Маленький git-обновлятор для update.sh и ручных проверок."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("kidbot.updater")


def run_update(repo_dir: Path) -> bool:
    repo_dir = Path(repo_dir)
    before = _git(repo_dir, ["rev-parse", "HEAD"]).strip()
    _git(repo_dir, ["fetch"])
    local = _git(repo_dir, ["rev-parse", "@"]).strip()
    remote = _git(repo_dir, ["rev-parse", "@{u}"]).strip()
    if local == remote:
        logger.info("already up to date")
        return False

    try:
        _run(repo_dir, ["git", "pull", "--ff-only"])
        _run(repo_dir, ["python3", "-m", "pip", "install", "-r", "requirements.txt"])
        return True
    except subprocess.CalledProcessError:
        logger.exception("update failed; returning to previous commit %s", before)
        _run(repo_dir, ["git", "checkout", before])
        raise


def _git(repo_dir: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _run(repo_dir: Path, command: list[str]) -> None:
    subprocess.run(command, cwd=repo_dir, check=True)
