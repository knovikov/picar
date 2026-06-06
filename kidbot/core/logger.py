"""Настройка логов KidBot."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_FILES = {
    "kidbot": "kidbot.log",
    "errors": "errors.log",
    "controller": "controller.log",
    "network": "network.log",
    "ai": "ai.log",
}


def setup_logging(log_dir: Path, console: bool = True) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    main_handler = _rotating_handler(log_dir / LOG_FILES["kidbot"], logging.DEBUG, formatter)
    error_handler = _rotating_handler(log_dir / LOG_FILES["errors"], logging.ERROR, formatter)
    root.addHandler(main_handler)
    root.addHandler(error_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    for logger_name in ("kidbot.controller", "kidbot.network", "kidbot.ai"):
        log = logging.getLogger(logger_name)
        log.setLevel(logging.DEBUG)
        log.propagate = True

    logging.getLogger("uvicorn.access").setLevel(logging.INFO)


def attach_named_file_logger(name: str, log_dir: Path, filename: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if any(isinstance(handler, RotatingFileHandler) and handler.baseFilename.endswith(filename) for handler in logger.handlers):
        return logger

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    logger.addHandler(_rotating_handler(log_dir / filename, logging.DEBUG, formatter))
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def _rotating_handler(path: Path, level: int, formatter: logging.Formatter) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler
