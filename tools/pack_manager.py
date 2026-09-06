#!/usr/bin/env python3
"""Validate and safely install homogeneous Cursor sound packs."""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path

SUPPORTED_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}


class PackError(RuntimeError):
    pass


def discover(source: Path) -> list[Path]:
    if not source.is_dir():
        raise PackError(f"Sound pack directory does not exist: {source}")
    clips = sorted(
        path
        for path in source.iterdir()
        if path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not clips:
        raise PackError(f"No supported audio files found in {source}")
    suffixes = {clip.suffix.lower() for clip in clips}
    if len(suffixes) != 1:
        listed = ", ".join(sorted(suffixes))
        raise PackError(
            f"A sound pack must use one audio format; found: {listed}. "
            "Split mixed formats into separate packs."
        )
    return clips


def install(source: Path, destination: Path) -> tuple[str, int]:
    clips = discover(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.stage.", dir=destination.parent)
    )
    backup = destination.with_name(f".{destination.name}.backup")
    try:
        for clip in clips:
            shutil.copy2(clip, stage / clip.name)
        discover(stage)

        if backup.exists():
            shutil.rmtree(backup)
        if destination.exists():
            os.replace(destination, backup)
        try:
            os.replace(stage, destination)
        except Exception:
            if backup.exists() and not destination.exists():
                os.replace(backup, destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if stage.exists():
            shutil.rmtree(stage)

    return clips[0].suffix.lower(), len(clips)


def inspect_pack(source: Path) -> tuple[str, int]:
    clips = discover(source)
    return clips[0].suffix.lower(), len(clips)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("source", type=Path)

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("source", type=Path)
    install_parser.add_argument("destination", type=Path)

    args = parser.parse_args()
    try:
        if args.command == "inspect":
            suffix, count = inspect_pack(args.source.expanduser())
        else:
            suffix, count = install(
                args.source.expanduser(), args.destination.expanduser()
            )
    except (OSError, PackError) as error:
        parser.exit(1, f"Error: {error}\n")

    print(f"{suffix[1:]} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
