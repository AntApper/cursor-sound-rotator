#!/usr/bin/env python3
"""Generate an original, redistributable chiptune notification sound pack."""

from __future__ import annotations

import argparse
import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 22_050
AMPLITUDE = 0.28

MELODIES = {
    "checkpoint.wav": [(523.25, 0.09), (659.25, 0.09), (783.99, 0.18)],
    "complete.wav": [(392.00, 0.08), (523.25, 0.08), (659.25, 0.08), (783.99, 0.20)],
    "data-ready.wav": [(659.25, 0.07), (0.0, 0.03), (659.25, 0.07), (987.77, 0.18)],
    "level-up.wav": [(261.63, 0.07), (329.63, 0.07), (392.00, 0.07), (523.25, 0.20)],
    "signal.wav": [(880.00, 0.06), (0.0, 0.04), (1_174.66, 0.14)],
    "success.wav": [(440.00, 0.08), (554.37, 0.08), (659.25, 0.16)],
}


def envelope(sample_index: int, sample_count: int) -> float:
    attack = max(1, int(sample_count * 0.08))
    release = max(1, int(sample_count * 0.30))
    if sample_index < attack:
        return sample_index / attack
    if sample_index >= sample_count - release:
        return max(0.0, (sample_count - sample_index - 1) / release)
    return 1.0


def square_sample(frequency: float, time_value: float) -> float:
    if frequency <= 0:
        return 0.0
    return 1.0 if math.sin(2 * math.pi * frequency * time_value) >= 0 else -1.0


def render_melody(notes: list[tuple[float, float]]) -> bytes:
    frames = bytearray()
    for frequency, duration in notes:
        count = max(1, int(SAMPLE_RATE * duration))
        for index in range(count):
            value = square_sample(frequency, index / SAMPLE_RATE)
            value *= envelope(index, count) * AMPLITUDE
            frames.extend(struct.pack("<h", int(value * 32_767)))
    return bytes(frames)


def generate_pack(destination: Path) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    for name, notes in MELODIES.items():
        output_path = destination / name
        with wave.open(str(output_path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(SAMPLE_RATE)
            output.writeframes(render_melody(notes))
    return len(MELODIES)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    count = generate_pack(args.destination.expanduser())
    print(f"Generated {count} original WAV clips in {args.destination.expanduser()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
