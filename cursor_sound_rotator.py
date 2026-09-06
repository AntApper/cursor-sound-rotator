#!/usr/bin/env python3
"""Rotate Cursor completion sounds without modifying Cursor itself.

The daemon watches the access times of Cursor's configured sound and cached
sound. After a read is observed, it stages and atomically replaces both files
with a different clip from the configured directory.
"""

from __future__ import annotations

import argparse
import filecmp
import os
import random
import shutil
import signal
import sys
import tempfile
import time
from pathlib import Path
from typing import Sequence

DEFAULT_SOUNDS_DIR = Path.home() / ".cursor-sounds" / "clips"
DEFAULT_TARGET_FILE = Path.home() / ".cursor-sounds" / "cursor-completion-sound.mp3"
DEFAULT_CURSOR_CACHE = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Cursor"
    / "User"
    / "globalStorage"
    / "customSounds"
    / "custom-chime.mp3"
)
SUPPORTED_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}


class RotationError(RuntimeError):
    """Raised when a sound rotation cannot be completed safely."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Randomized completion sound daemon for Cursor AI IDE."
    )
    parser.add_argument(
        "--sounds-dir",
        type=Path,
        default=DEFAULT_SOUNDS_DIR,
        help=f"Directory containing sound clips (default: {DEFAULT_SOUNDS_DIR})",
    )
    parser.add_argument(
        "--target-file",
        type=Path,
        default=DEFAULT_TARGET_FILE,
        help=f"Sound path configured in Cursor (default: {DEFAULT_TARGET_FILE})",
    )
    parser.add_argument(
        "--cursor-cache",
        type=Path,
        default=DEFAULT_CURSOR_CACHE,
        help=f"Cursor's cached custom sound (default: {DEFAULT_CURSOR_CACHE})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to wait after a detected read before swapping (default: 2.0)",
    )
    parser.add_argument(
        "--idle-interval",
        type=float,
        default=60.0,
        help="Idle fallback rotation interval in seconds; 0 disables it (default: 60)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Seconds between access-time checks (default: 1.0)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Rotate once and immediately exit",
    )
    args = parser.parse_args(argv)

    if args.delay < 0:
        parser.error("--delay must be zero or greater")
    if args.idle_interval < 0:
        parser.error("--idle-interval must be zero or greater")
    if args.poll_interval <= 0:
        parser.error("--poll-interval must be greater than zero")
    return args


def get_clips(sounds_dir: Path, required_suffix: str | None = None) -> list[Path]:
    """Return supported, visible regular files, optionally filtered by suffix."""
    if not sounds_dir.is_dir():
        return []

    normalized_suffix = required_suffix.lower() if required_suffix else None
    return sorted(
        path
        for path in sounds_dir.iterdir()
        if path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and (normalized_suffix is None or path.suffix.lower() == normalized_suffix)
    )


def get_atime(path: Path) -> float:
    try:
        return path.stat().st_atime
    except OSError:
        return 0.0


def find_current_clip(target_file: Path, clips: Sequence[Path]) -> Path | None:
    """Find a source clip identical to the existing target, if one exists."""
    if not target_file.is_file():
        return None
    for clip in clips:
        try:
            if target_file.stat().st_size == clip.stat().st_size and filecmp.cmp(
                target_file, clip, shallow=False
            ):
                return clip
        except OSError:
            continue
    return None


def choose_next_clip(clips: Sequence[Path], current_clip: Path | None) -> Path:
    if not clips:
        raise RotationError("No compatible audio clips are available")
    candidates = [clip for clip in clips if clip != current_clip]
    return random.choice(candidates if candidates else list(clips))


def stage_copy(source: Path, destination: Path) -> Path:
    """Fully copy a source into a temporary file beside destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as output, source.open("rb") as input_file:
            shutil.copyfileobj(input_file, output)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary_path, 0o644)
        return temporary_path
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def atomic_replace_from_source(source: Path, destinations: Sequence[Path]) -> None:
    """Stage all copies first, then atomically replace each destination file."""
    staged: list[tuple[Path, Path]] = []
    try:
        for destination in destinations:
            staged.append((stage_copy(source, destination), destination))
        for temporary_path, destination in staged:
            os.replace(temporary_path, destination)
    finally:
        for temporary_path, _ in staged:
            temporary_path.unlink(missing_ok=True)


def rotate_sound(
    sounds_dir: Path,
    target_file: Path,
    cursor_cache: Path,
    current_clip: Path | None,
) -> tuple[Path, int]:
    """Rescan, select a non-repeating clip, and replace active sound files."""
    target_suffix = target_file.suffix.lower()
    if target_suffix not in SUPPORTED_EXTENSIONS:
        raise RotationError(
            f"Target extension '{target_suffix}' is not supported; use one of "
            f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    if cursor_cache.suffix.lower() != target_suffix:
        raise RotationError("Target and Cursor cache must use the same extension")

    clips = get_clips(sounds_dir, target_suffix)
    if not clips:
        raise RotationError(
            f"No '{target_suffix}' clips found in '{sounds_dir}'. "
            "Keep one audio format per sound pack."
        )

    next_clip = choose_next_clip(clips, current_clip)
    atomic_replace_from_source(next_clip, (target_file, cursor_cache))
    return next_clip, len(clips)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    sounds_dir = args.sounds_dir.expanduser().resolve()
    target_file = args.target_file.expanduser().resolve()
    cursor_cache = args.cursor_cache.expanduser().resolve()

    initial_clips = get_clips(sounds_dir, target_file.suffix)
    current_clip = find_current_clip(target_file, initial_clips)

    def swap_sound() -> None:
        nonlocal current_clip
        current_clip, clip_count = rotate_sound(
            sounds_dir, target_file, cursor_cache, current_clip
        )
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"[{timestamp}] Active chime: {current_clip.name} "
            f"({clip_count} clips available)",
            flush=True,
        )

    def handle_shutdown(_signum: int, _frame: object) -> None:
        print("Daemon stopped.", flush=True)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        swap_sound()
    except (OSError, RotationError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if args.once:
        return 0

    last_cache_atime = get_atime(cursor_cache)
    last_target_atime = get_atime(target_file)
    last_rotate_time = time.monotonic()
    print(f"Monitoring '{sounds_dir}' for Cursor chime reads.", flush=True)

    while True:
        try:
            time.sleep(args.poll_interval)
            cache_atime = get_atime(cursor_cache)
            target_atime = get_atime(target_file)
            read_detected = (
                cache_atime > last_cache_atime + 0.1
                or target_atime > last_target_atime + 0.1
            )
            idle_rotation_due = args.idle_interval > 0 and (
                time.monotonic() - last_rotate_time >= args.idle_interval
            )

            if read_detected:
                time.sleep(args.delay)
            if read_detected or idle_rotation_due:
                swap_sound()
                last_cache_atime = get_atime(cursor_cache)
                last_target_atime = get_atime(target_file)
                last_rotate_time = time.monotonic()
        except (OSError, RotationError) as error:
            print(f"Warning: {error}; retrying in 2 seconds.", file=sys.stderr, flush=True)
            time.sleep(2.0)


if __name__ == "__main__":
    raise SystemExit(main())
