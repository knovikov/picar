#!/usr/bin/env python3
"""Создает маленькие WAV-звуки без чужих авторских прав."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_RATE = 22050


def main() -> None:
    sounds = ROOT / "assets" / "sounds"
    music = ROOT / "assets" / "music"
    sounds.mkdir(parents=True, exist_ok=True)
    music.mkdir(parents=True, exist_ok=True)

    write_sequence(sounds / "robot_ready.wav", [(660, 0.12), (880, 0.12), (990, 0.18)])
    write_sequence(sounds / "photo_done.wav", [(880, 0.08), (1175, 0.08), (1568, 0.12)])
    write_sequence(sounds / "no_internet.wav", [(330, 0.18), (262, 0.22)])
    write_sequence(sounds / "error.wav", [(220, 0.12), (180, 0.12), (140, 0.2)])
    write_funny_buzz(sounds / "fart_1.wav", base=95)
    write_funny_buzz(sounds / "fart_2.wav", base=125)
    write_sequence(
        music / "sample_song_1.wav",
        [(523, 0.18), (659, 0.18), (784, 0.18), (1046, 0.28), (784, 0.18), (659, 0.18)],
    )
    write_sequence(
        music / "sample_song_2.wav",
        [(392, 0.16), (494, 0.16), (587, 0.16), (494, 0.16), (659, 0.25), (587, 0.18)],
    )

    print("Sample audio generated.")


def write_sequence(path: Path, notes: list[tuple[float, float]], amplitude: float = 0.35) -> None:
    if path.exists():
        return

    frames = bytearray()
    for frequency, duration in notes:
        frames.extend(tone(frequency, duration, amplitude))
        frames.extend(tone(0, 0.04, 0))
    write_wav(path, frames)


def write_funny_buzz(path: Path, base: float) -> None:
    if path.exists():
        return

    frames = bytearray()
    total_samples = int(SAMPLE_RATE * 0.45)
    for index in range(total_samples):
        t = index / SAMPLE_RATE
        frequency = base + 25 * math.sin(t * 22)
        envelope = max(0.0, 1.0 - t / 0.45)
        sample = math.sin(2 * math.pi * frequency * t) * 0.35 * envelope
        frames.extend(pack_sample(sample))
    write_wav(path, frames)


def tone(frequency: float, duration: float, amplitude: float) -> bytes:
    frames = bytearray()
    total_samples = int(SAMPLE_RATE * duration)
    for index in range(total_samples):
        if frequency <= 0:
            sample = 0.0
        else:
            t = index / SAMPLE_RATE
            envelope = min(1.0, index / max(1, SAMPLE_RATE * 0.02))
            sample = math.sin(2 * math.pi * frequency * t) * amplitude * envelope
        frames.extend(pack_sample(sample))
    return bytes(frames)


def pack_sample(sample: float) -> bytes:
    sample = max(-1.0, min(1.0, sample))
    return struct.pack("<h", int(sample * 32767))


def write_wav(path: Path, frames: bytes | bytearray) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(bytes(frames))


if __name__ == "__main__":
    main()
