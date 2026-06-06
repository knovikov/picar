"""Manual git updater with stable build rollback support."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("kidbot.updater")

CommandRunner = Callable[..., object]


@dataclass(frozen=True)
class StableBuild:
    commit: str
    branch: str
    saved_at: str
    reason: str


@dataclass(frozen=True)
class UpdateStatus:
    success: bool
    message: str
    current: str = ""
    upstream: str = ""
    branch: str = ""
    stable: str = ""
    update_available: bool = False
    can_fast_forward: bool = False
    dirty: bool = False


@dataclass(frozen=True)
class UpdateResult:
    success: bool
    message: str
    changed: bool = False
    current: str = ""
    stable: str = ""
    stdout: str = ""
    stderr: str = ""


class UpdateManager:
    """Runs update and rollback jobs in the background for the web UI."""

    def __init__(self, repo_dir: Path):
        self.repo_dir = Path(repo_dir)
        self._lock = threading.Lock()
        self._running = False
        self._action = ""
        self._last_result = UpdateResult(True, "Обновления еще не запускались.")
        self._last_status: Optional[UpdateStatus] = None

    def status_payload(self) -> dict[str, object]:
        with self._lock:
            status = self._last_status or check_update_status(self.repo_dir, fetch=False)
            stable = load_stable_build(self.repo_dir)
            return {
                "running": self._running,
                "action": self._action,
                "last_result": asdict(self._last_result),
                "status": asdict(status),
                "stable_build": asdict(stable) if stable else None,
            }

    def check(self) -> dict[str, object]:
        status = check_update_status(self.repo_dir)
        with self._lock:
            self._last_status = status
            self._last_result = UpdateResult(status.success, status.message)
        return self.status_payload()

    def start_update(self) -> dict[str, object]:
        return self._start_job("update", lambda: apply_update(self.repo_dir))

    def start_rollback(self) -> dict[str, object]:
        return self._start_job("rollback", lambda: rollback_to_stable(self.repo_dir))

    def _start_job(self, action: str, job: Callable[[], UpdateResult]) -> dict[str, object]:
        with self._lock:
            if self._running:
                already_running = True
            else:
                already_running = False
                self._running = True
                self._action = action
                self._last_result = UpdateResult(True, f"{action} запущен.")
        if already_running:
            return self.status_payload()

        def run() -> None:
            try:
                result = job()
            except Exception as exc:  # pragma: no cover - defensive guard for live robot jobs
                logger.exception("%s failed", action)
                result = UpdateResult(False, f"{action} упал: {exc}")
            with self._lock:
                self._last_result = result
                self._last_status = check_update_status(self.repo_dir, fetch=False)
                self._running = False
                self._action = ""

        threading.Thread(target=run, daemon=True).start()
        return self.status_payload()


def stable_build_path(repo_dir: Path) -> Path:
    return Path(repo_dir) / ".kidbot" / "stable-build.json"


def save_stable_build(repo_dir: Path, commit: str, branch: str = "", reason: str = "before-update") -> StableBuild:
    build = StableBuild(
        commit=commit.strip(),
        branch=branch.strip(),
        saved_at=datetime.now(timezone.utc).isoformat(),
        reason=reason,
    )
    path = stable_build_path(repo_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(build), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return build


def load_stable_build(repo_dir: Path) -> Optional[StableBuild]:
    path = stable_build_path(repo_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return StableBuild(
            commit=str(data.get("commit", "")),
            branch=str(data.get("branch", "")),
            saved_at=str(data.get("saved_at", "")),
            reason=str(data.get("reason", "")),
        )
    except (OSError, json.JSONDecodeError, TypeError):
        logger.exception("stable build file is broken: %s", path)
        return None


def check_update_status(
    repo_dir: Path,
    runner: CommandRunner = subprocess.run,
    fetch: bool = True,
) -> UpdateStatus:
    repo_dir = Path(repo_dir)
    try:
        current = _git(repo_dir, ["rev-parse", "HEAD"], runner=runner)
        branch = _git(repo_dir, ["rev-parse", "--abbrev-ref", "HEAD"], runner=runner)
        upstream_name = _git(repo_dir, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], runner=runner)
        dirty = is_worktree_dirty(repo_dir, runner=runner)
        if fetch:
            _run(repo_dir, ["git", "fetch"], runner=runner, timeout=120)
        local = _git(repo_dir, ["rev-parse", "@"], runner=runner)
        upstream = _git(repo_dir, ["rev-parse", "@{u}"], runner=runner)
        base = _git(repo_dir, ["merge-base", "@", "@{u}"], runner=runner)
    except subprocess.CalledProcessError as exc:
        return UpdateStatus(False, "Не могу проверить обновления: git не готов.", stderr_from(exc))

    stable = load_stable_build(repo_dir)
    update_available = local != upstream
    can_fast_forward = update_available and local == base
    if dirty:
        return UpdateStatus(
            False,
            "Есть локальные изменения. Обновление остановлено, чтобы не потерять код.",
            current=current,
            upstream=upstream,
            branch=branch,
            stable=stable.commit if stable else "",
            update_available=update_available,
            can_fast_forward=can_fast_forward,
            dirty=True,
        )
    if update_available and not can_fast_forward:
        return UpdateStatus(
            False,
            "Локальная ветка отличается от GitHub. Авто-обновление небезопасно.",
            current=current,
            upstream=upstream,
            branch=branch,
            stable=stable.commit if stable else "",
            update_available=True,
            can_fast_forward=False,
        )
    if update_available:
        message = f"Есть обновление: {current[:7]} -> {upstream[:7]}."
    else:
        message = "Уже стоит последняя версия."
    return UpdateStatus(
        True,
        message,
        current=current,
        upstream=upstream,
        branch=branch or upstream_name,
        stable=stable.commit if stable else "",
        update_available=update_available,
        can_fast_forward=can_fast_forward,
        dirty=False,
    )


def apply_update(
    repo_dir: Path,
    runner: CommandRunner = subprocess.run,
    restart_service: bool = True,
) -> UpdateResult:
    repo_dir = Path(repo_dir)
    status = check_update_status(repo_dir, runner=runner)
    if not status.success:
        return UpdateResult(False, status.message, current=status.current, stable=status.stable)
    if not status.update_available:
        return UpdateResult(True, "Уже стоит последняя версия.", changed=False, current=status.current, stable=status.stable)

    stable = save_stable_build(repo_dir, status.current, branch=status.branch, reason="before-update")
    try:
        pull_result = _run(repo_dir, ["git", "pull", "--ff-only"], runner=runner, timeout=120)
        _run(repo_dir, ["python3", "-m", "pip", "install", "-r", "requirements.txt"], runner=runner, timeout=300)
        _run(repo_dir, ["python3", "tools/generate_sample_audio.py"], runner=runner, timeout=120)
        if restart_service:
            restart_kidbot_service(repo_dir, runner=runner)
        return UpdateResult(
            True,
            "Обновление применено. Робот перезапускается.",
            changed=True,
            current=status.upstream,
            stable=stable.commit,
            stdout=getattr(pull_result, "stdout", ""),
        )
    except subprocess.CalledProcessError as exc:
        logger.exception("update failed; rolling back to %s", stable.commit)
        _run(repo_dir, ["git", "reset", "--hard", stable.commit], runner=runner, timeout=120)
        return UpdateResult(False, "Обновление не получилось. Вернулся на стабильную версию.", current=status.current, stable=stable.commit, stderr=stderr_from(exc))


def rollback_to_stable(
    repo_dir: Path,
    runner: CommandRunner = subprocess.run,
    restart_service: bool = True,
) -> UpdateResult:
    repo_dir = Path(repo_dir)
    stable = load_stable_build(repo_dir)
    if stable is None or not stable.commit:
        return UpdateResult(False, "Стабильная версия еще не сохранена.")

    current = ""
    try:
        current = _git(repo_dir, ["rev-parse", "HEAD"], runner=runner)
        _run(repo_dir, ["git", "reset", "--hard", stable.commit], runner=runner, timeout=120)
        _run(repo_dir, ["python3", "-m", "pip", "install", "-r", "requirements.txt"], runner=runner, timeout=300)
        _run(repo_dir, ["python3", "tools/generate_sample_audio.py"], runner=runner, timeout=120)
        if restart_service:
            restart_kidbot_service(repo_dir, runner=runner)
    except subprocess.CalledProcessError as exc:
        return UpdateResult(False, "Откат не получился.", current=current, stable=stable.commit, stderr=stderr_from(exc))
    return UpdateResult(True, "Откатился на стабильную версию. Робот перезапускается.", changed=current != stable.commit, current=stable.commit, stable=stable.commit)


def is_worktree_dirty(repo_dir: Path, runner: CommandRunner = subprocess.run) -> bool:
    status = _run(repo_dir, ["git", "status", "--porcelain", "--untracked-files=all"], runner=runner, timeout=30)
    return bool(getattr(status, "stdout", "").strip())


def restart_kidbot_service(repo_dir: Path, runner: CommandRunner = subprocess.run) -> None:
    if shutil.which("systemctl") is None:
        return
    _run(repo_dir, ["sudo", "-n", "systemctl", "restart", "kidbot.service"], runner=runner, timeout=30)


def run_update(repo_dir: Path) -> bool:
    """Compatibility wrapper for older callers."""
    return apply_update(repo_dir).changed


def _git(repo_dir: Path, args: list[str], runner: CommandRunner = subprocess.run) -> str:
    result = _run(repo_dir, ["git", *args], runner=runner, timeout=60)
    return getattr(result, "stdout", "").strip()


def _run(repo_dir: Path, command: list[str], runner: CommandRunner = subprocess.run, timeout: int = 60) -> object:
    try:
        result = runner(command, cwd=repo_dir, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise subprocess.CalledProcessError(127, command, "", str(exc)) from exc
    if getattr(result, "returncode", 1) != 0:
        raise subprocess.CalledProcessError(
            getattr(result, "returncode", 1),
            command,
            getattr(result, "stdout", ""),
            getattr(result, "stderr", ""),
        )
    return result


def stderr_from(error: subprocess.CalledProcessError) -> str:
    return str(error.stderr or error.output or error)
