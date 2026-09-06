#!/usr/bin/env python3
"""Safely configure and restore Cursor's strict-JSON settings file."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

CUSTOM_PATH_KEY = "cursor.composer.customChimeSoundPath"
CHIME_ENABLED_KEY = "cursor.composer.shouldChimeAfterChatFinishes"
MISSING = object()


class SettingsError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SettingsError(
            f"'{path}' is not strict JSON (it may contain JSONC comments). "
            "No settings were changed; select the sound manually in Cursor."
        ) from error
    if not isinstance(value, dict):
        raise SettingsError(f"Expected a JSON object in '{path}'")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, indent=4)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        if path.exists():
            os.chmod(temporary, path.stat().st_mode & 0o777)
        else:
            os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def encode_prior(value: object) -> dict[str, Any]:
    return {"present": value is not MISSING, "value": None if value is MISSING else value}


def configure(settings_path: Path, state_path: Path, sound_path: Path) -> None:
    if not settings_path.is_file():
        raise SettingsError(
            f"Cursor settings file not found at '{settings_path}'. "
            f"Select '{sound_path}' manually in Cursor after installation."
        )

    settings = read_json(settings_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    if state_path.exists():
        state = read_json(state_path)
    else:
        previous_custom = settings.get(CUSTOM_PATH_KEY, MISSING)
        # Treat earlier releases of this tool as tool-managed, not user-owned state.
        if isinstance(previous_custom, str) and previous_custom.startswith(
            str(Path.home() / ".cursor-sounds" / "cursor-completion-sound.")
        ):
            previous_custom = MISSING
        state = {
            "version": 1,
            "settings_path": str(settings_path),
            "previous": {
                CUSTOM_PATH_KEY: encode_prior(previous_custom),
                CHIME_ENABLED_KEY: encode_prior(settings.get(CHIME_ENABLED_KEY, MISSING)),
            },
        }
        atomic_write_json(state_path, state)

    backup = settings_path.with_name(f"{settings_path.name}.cursor-sound-rotator.bak")
    if not backup.exists():
        shutil.copy2(settings_path, backup)

    settings[CUSTOM_PATH_KEY] = str(sound_path)
    settings[CHIME_ENABLED_KEY] = True
    atomic_write_json(settings_path, settings)

    state["installed"] = {
        CUSTOM_PATH_KEY: str(sound_path),
        CHIME_ENABLED_KEY: True,
    }
    atomic_write_json(state_path, state)


def restore(settings_path: Path, state_path: Path) -> None:
    if not state_path.exists():
        raise SettingsError("No saved pre-install settings state was found")
    if not settings_path.is_file():
        raise SettingsError(f"Cursor settings file not found at '{settings_path}'")

    state = read_json(state_path)
    settings = read_json(settings_path)
    previous = state.get("previous", {})
    installed = state.get("installed", {})

    for key in (CUSTOM_PATH_KEY, CHIME_ENABLED_KEY):
        prior = previous.get(key)
        if not isinstance(prior, dict):
            continue
        # Do not overwrite a value the user changed after installation.
        if key in installed and settings.get(key, MISSING) != installed[key]:
            continue
        if prior.get("present"):
            settings[key] = prior.get("value")
        else:
            settings.pop(key, None)

    atomic_write_json(settings_path, settings)
    state_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    configure_parser = subparsers.add_parser("configure")
    configure_parser.add_argument("--settings", required=True, type=Path)
    configure_parser.add_argument("--state", required=True, type=Path)
    configure_parser.add_argument("--sound", required=True, type=Path)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("--settings", required=True, type=Path)
    restore_parser.add_argument("--state", required=True, type=Path)

    args = parser.parse_args()
    try:
        if args.command == "configure":
            configure(
                args.settings.expanduser(),
                args.state.expanduser(),
                args.sound.expanduser(),
            )
        else:
            restore(args.settings.expanduser(), args.state.expanduser())
    except (OSError, SettingsError) as error:
        parser.exit(2, f"Warning: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
