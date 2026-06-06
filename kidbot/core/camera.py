"""Съемка камерой с mock-режимом для компьютеров без робота."""

from __future__ import annotations

import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("kidbot.camera")

MOCK_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
    "////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////////////"
    "//////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/"
    "xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/Aaf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/"
    "9oACAECAQE/Aaf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Aqf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IV//2gAMAwEA"
    "AhEDEQA/AJf/2Q=="
)


class Camera:
    def __init__(self, photo_dir: Path, mock: bool = False):
        self.photo_dir = Path(photo_dir)
        self.photo_dir.mkdir(parents=True, exist_ok=True)
        self.mock = mock
        self._picamera2 = None

        if not mock:
            self._connect_camera()
        if self.mock:
            logger.info("Camera is running in mock mode")

    def _connect_camera(self) -> None:
        try:
            from picamera2 import Picamera2

            self._picamera2 = Picamera2()
            self._picamera2.configure(self._picamera2.create_still_configuration())
            self._picamera2.start()
        except Exception as exc:
            logger.warning("camera unavailable; switching to mock mode: %s", exc)
            self.mock = True

    def capture_photo(self, prefix: str = "photo") -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.photo_dir / f"{prefix}_{timestamp}.jpg"

        if self.mock:
            path.write_bytes(MOCK_JPEG)
        else:
            assert self._picamera2 is not None
            self._picamera2.capture_file(str(path))

        logger.info("photo saved: %s", path)
        return path

    def close(self) -> None:
        if self._picamera2 is not None:
            self._picamera2.stop()
            self._picamera2 = None
