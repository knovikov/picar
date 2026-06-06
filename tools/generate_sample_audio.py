#!/usr/bin/env python3
"""Generate original WAV effects without copyrighted samples."""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_RATE = 44100
TAU = math.pi * 2.0


def main() -> None:
    sounds = ROOT / "assets" / "sounds"
    music = ROOT / "assets" / "music"
    sounds.mkdir(parents=True, exist_ok=True)
    music.mkdir(parents=True, exist_ok=True)

    write_sequence(sounds / "robot_ready.wav", [(660, 0.11), (880, 0.11), (1320, 0.16)], amplitude=0.32)
    write_sequence(sounds / "photo_done.wav", [(880, 0.07), (1175, 0.08), (1568, 0.13)], amplitude=0.30)
    write_sequence(sounds / "no_internet.wav", [(330, 0.18), (262, 0.25), (196, 0.2)], amplitude=0.34)
    write_sequence(sounds / "error.wav", [(220, 0.1), (170, 0.13), (130, 0.22)], amplitude=0.38)
    write_fart(sounds / "fart_1.wav", seed=11, duration=1.05, base=92, wetness=0.45, pressure=1.0)
    write_fart(sounds / "fart_2.wav", seed=29, duration=1.45, base=76, wetness=0.78, pressure=1.16)
    write_engine_idle(sounds / "engine_idle.wav")
    write_engine_rev(sounds / "engine_rev.wav")
    write_horn(sounds / "horn.wav")
    write_sequence(
        music / "sample_song_1.wav",
        [(523, 0.18), (659, 0.18), (784, 0.18), (1046, 0.28), (784, 0.18), (659, 0.18)],
        amplitude=0.26,
    )
    write_sequence(
        music / "sample_song_2.wav",
        [(392, 0.16), (494, 0.16), (587, 0.16), (494, 0.16), (659, 0.25), (587, 0.18)],
        amplitude=0.26,
    )

    print("Sample audio generated.")


def write_sequence(path: Path, notes: list[tuple[float, float]], amplitude: float = 0.35) -> None:
    samples: list[float] = []
    for frequency, duration in notes:
        samples.extend(tone_samples(frequency, duration, amplitude))
        samples.extend([0.0] * int(SAMPLE_RATE * 0.035))
    write_wav(path, samples)


def write_fart(path: Path, seed: int, duration: float, base: float, wetness: float, pressure: float) -> None:
    rng = random.Random(seed)
    total_samples = int(SAMPLE_RATE * duration)
    samples: list[float] = []
    phase = 0.0
    noise_lp = 0.0
    rumble_lp = 0.0
    grit_lp = 0.0
    bubbles = [
        (rng.uniform(0.12, duration * 0.82), rng.uniform(0.06, 0.15), rng.uniform(115, 210))
        for _ in range(7 if wetness > 0.6 else 4)
    ]

    for index in range(total_samples):
        t = index / SAMPLE_RATE
        p = t / duration
        envelope = (math.sin(math.pi * min(1.0, p)) ** 0.42) * (1.05 - p * 0.22) * pressure
        if p < 0.045:
            envelope *= p / 0.045

        freq = base * (1.03 - p * 0.46) + 7.0 * math.sin(TAU * 2.1 * t) + 4.0 * math.sin(TAU * 7.3 * t)
        phase += TAU * max(34.0, freq) / SAMPLE_RATE
        membrane = math.sin(phase) + 0.48 * math.sin(phase * 2.01 + 0.7) + 0.18 * math.sin(phase * 3.97)
        rasp = math.tanh(membrane * (2.1 + 0.8 * math.sin(TAU * 9.0 * t)))

        raw_noise = rng.uniform(-1.0, 1.0)
        noise_lp += 0.045 * (raw_noise - noise_lp)
        rumble_lp += 0.012 * (raw_noise - rumble_lp)
        grit_lp += 0.14 * (raw_noise - grit_lp)
        gritty_air = grit_lp - noise_lp * 0.45

        bubble_mix = 0.0
        for center, width, frequency in bubbles:
            distance = abs(t - center)
            if distance < width:
                local = 1.0 - distance / width
                bubble_mix += (local**2) * math.sin(TAU * frequency * (t - center)) * (0.55 + 0.45 * wetness)

        tail_chuff = 0.0
        if p > 0.72:
            tail = (p - 0.72) / 0.28
            tail_chuff = (1.0 - tail) * math.sin(TAU * (44 + 9 * math.sin(t * 40)) * t) * rng.uniform(0.2, 0.8)

        sample = envelope * (0.48 * rasp + 0.26 * noise_lp + 0.18 * rumble_lp + 0.16 * gritty_air)
        sample += wetness * 0.22 * bubble_mix + 0.16 * tail_chuff
        samples.append(soft_clip(sample * 1.85))

    write_wav(path, fade(normalize(samples, peak=0.9), 0.01, 0.08))


def write_engine_idle(path: Path) -> None:
    duration = 4.0
    samples = synth_engine(duration=duration, rpm_start=1180, rpm_end=1320, throttle=0.36, seed=71, revving=False)
    write_wav(path, fade(normalize(samples, peak=0.86), 0.02, 0.05))


def write_engine_rev(path: Path) -> None:
    duration = 4.4
    samples = synth_engine(duration=duration, rpm_start=1500, rpm_end=5200, throttle=0.88, seed=83, revving=True)
    write_wav(path, fade(normalize(samples, peak=0.92), 0.025, 0.12))


def synth_engine(duration: float, rpm_start: float, rpm_end: float, throttle: float, seed: int, revving: bool) -> list[float]:
    rng = random.Random(seed)
    total_samples = int(SAMPLE_RATE * duration)
    samples: list[float] = []
    crank_phase = 0.0
    rumble = 0.0
    hiss = 0.0

    for index in range(total_samples):
        t = index / SAMPLE_RATE
        p = t / duration
        if revving:
            climb = min(1.0, p / 0.74)
            rpm = rpm_start + (rpm_end - rpm_start) * (climb**1.55)
            if p > 0.76:
                rpm -= (rpm_end - 3600) * ((p - 0.76) / 0.24) ** 1.2
            envelope = min(1.0, p * 6.0) * (1.0 - max(0.0, p - 0.9) * 2.4)
        else:
            rpm = rpm_start + 80 * math.sin(TAU * 0.7 * t) + 45 * math.sin(TAU * 1.9 * t)
            envelope = 0.82 + 0.08 * math.sin(TAU * 0.5 * t)

        fire_hz = max(20.0, rpm / 60.0 * 2.0)
        crank_phase = (crank_phase + fire_hz / SAMPLE_RATE) % 1.0
        pulse = math.exp(-crank_phase * (22.0 if revving else 16.0))
        pulse += 0.45 * math.exp(-((crank_phase - 0.5) % 1.0) * (28.0 if revving else 18.0))
        crank_radians = TAU * crank_phase
        harmonic = (
            math.sin(crank_radians)
            + 0.58 * math.sin(crank_radians * 2.0 + 0.35)
            + 0.28 * math.sin(crank_radians * 3.0 + 1.2)
        )

        noise = rng.uniform(-1.0, 1.0)
        rumble += 0.009 * (noise - rumble)
        hiss += 0.16 * (noise - hiss)
        high = hiss - rumble
        drivetrain = math.sin(TAU * (rpm / 60.0 * 0.55) * t) * (0.22 if revving else 0.14)

        sample = envelope * (
            0.58 * pulse * harmonic
            + 0.24 * rumble
            + 0.14 * high * throttle
            + drivetrain
        )
        sample *= throttle
        samples.append(soft_clip(sample * 1.75))

    return samples


def write_horn(path: Path) -> None:
    samples: list[float] = []
    samples.extend(horn_tone(392, 0.24))
    samples.extend([0.0] * int(SAMPLE_RATE * 0.045))
    samples.extend(horn_tone(392, 0.35))
    write_wav(path, fade(normalize(samples, peak=0.84), 0.01, 0.04))


def horn_tone(frequency: float, duration: float) -> list[float]:
    samples = []
    total_samples = int(SAMPLE_RATE * duration)
    for index in range(total_samples):
        t = index / SAMPLE_RATE
        attack = min(1.0, index / max(1, SAMPLE_RATE * 0.018))
        release = min(1.0, (total_samples - index) / max(1, SAMPLE_RATE * 0.04))
        mod = 1.0 + 0.018 * math.sin(TAU * 5.5 * t)
        sample = (
            math.sin(TAU * frequency * mod * t)
            + 0.42 * math.sin(TAU * frequency * 1.51 * t + 0.3)
            + 0.18 * math.sin(TAU * frequency * 2.02 * t)
        ) * 0.44 * attack * release
        samples.append(soft_clip(sample))
    return samples


def tone_samples(frequency: float, duration: float, amplitude: float) -> list[float]:
    samples: list[float] = []
    total_samples = int(SAMPLE_RATE * duration)
    for index in range(total_samples):
        if frequency <= 0:
            sample = 0.0
        else:
            t = index / SAMPLE_RATE
            attack = min(1.0, index / max(1, SAMPLE_RATE * 0.018))
            release = min(1.0, (total_samples - index) / max(1, SAMPLE_RATE * 0.025))
            sample = math.sin(TAU * frequency * t) * amplitude * attack * release
        samples.append(sample)
    return samples


def fade(samples: list[float], fade_in_seconds: float, fade_out_seconds: float) -> list[float]:
    result = list(samples)
    fade_in_count = min(len(result), int(SAMPLE_RATE * fade_in_seconds))
    fade_out_count = min(len(result), int(SAMPLE_RATE * fade_out_seconds))
    for index in range(fade_in_count):
        result[index] *= index / max(1, fade_in_count)
    for index in range(fade_out_count):
        result[-index - 1] *= index / max(1, fade_out_count)
    return result


def normalize(samples: list[float], peak: float = 0.92) -> list[float]:
    current_peak = max((abs(sample) for sample in samples), default=0.0)
    if current_peak <= 0:
        return samples
    gain = peak / current_peak
    return [sample * gain for sample in samples]


def soft_clip(sample: float) -> float:
    return math.tanh(sample * 1.35) / math.tanh(1.35)


def pack_sample(sample: float) -> bytes:
    sample = max(-1.0, min(1.0, sample))
    return struct.pack("<h", int(sample * 32767))


def write_wav(path: Path, samples: list[float]) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(b"".join(pack_sample(sample) for sample in samples))


if __name__ == "__main__":
    main()
