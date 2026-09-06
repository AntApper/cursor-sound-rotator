from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import cursor_sound_rotator as rotator
import generate_example_pack
import pack_manager
import settings_manager


class RotatorTests(unittest.TestCase):
    def test_rotation_avoids_immediate_repeat_and_rescans(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clips = root / "clips"
            clips.mkdir()
            first = clips / "first.mp3"
            second = clips / "second.mp3"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            target = root / "active.mp3"
            cache = root / "cache.mp3"

            current, count = rotator.rotate_sound(clips, target, cache, None)
            self.assertEqual(count, 2)
            self.assertEqual(target.read_bytes(), current.read_bytes())
            self.assertEqual(cache.read_bytes(), current.read_bytes())

            following, count = rotator.rotate_sound(clips, target, cache, current)
            self.assertEqual(count, 2)
            self.assertNotEqual(current, following)

            third = clips / "third.mp3"
            third.write_bytes(b"third")
            _, count = rotator.rotate_sound(clips, target, cache, following)
            self.assertEqual(count, 3)

    def test_rotation_requires_matching_extensions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clips = root / "clips"
            clips.mkdir()
            (clips / "sound.wav").write_bytes(b"wav")
            with self.assertRaises(rotator.RotationError):
                rotator.rotate_sound(
                    clips, root / "active.mp3", root / "cache.mp3", None
                )

    def test_atomic_replace_leaves_no_temporary_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.mp3"
            source.write_bytes(b"new content")
            first = root / "first.mp3"
            second = root / "second.mp3"
            first.write_bytes(b"old")
            second.write_bytes(b"old")

            rotator.atomic_replace_from_source(source, (first, second))
            self.assertEqual(first.read_bytes(), b"new content")
            self.assertEqual(second.read_bytes(), b"new content")
            self.assertEqual(list(root.glob(".*.tmp")), [])

    def test_invalid_numeric_arguments_are_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                rotator.parse_args(["--poll-interval", "0"])
            with self.assertRaises(SystemExit):
                rotator.parse_args(["--delay", "-1"])


class PackManagerTests(unittest.TestCase):
    def test_install_stages_homogeneous_pack(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            destination.mkdir()
            (destination / "old.mp3").write_bytes(b"old")
            (source / "one.mp3").write_bytes(b"one")
            (source / "two.mp3").write_bytes(b"two")
            (source / "notes.txt").write_text("ignored", encoding="utf-8")

            suffix, count = pack_manager.install(source, destination)
            self.assertEqual((suffix, count), (".mp3", 2))
            self.assertEqual(sorted(path.name for path in destination.iterdir()), [
                "one.mp3",
                "two.mp3",
            ])

    def test_mixed_pack_is_rejected_without_deleting_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            destination.mkdir()
            (source / "one.mp3").write_bytes(b"one")
            (source / "two.wav").write_bytes(b"two")
            preserved = destination / "preserved.mp3"
            preserved.write_bytes(b"preserved")

            with self.assertRaises(pack_manager.PackError):
                pack_manager.install(source, destination)
            self.assertEqual(preserved.read_bytes(), b"preserved")


class SettingsManagerTests(unittest.TestCase):
    def test_configure_and_restore_preserve_unrelated_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = root / "settings.json"
            state = root / "state.json"
            sound = root / "active.wav"
            original = {
                "editor.fontSize": 15,
                settings_manager.CHIME_ENABLED_KEY: False,
            }
            settings.write_text(json.dumps(original), encoding="utf-8")

            settings_manager.configure(settings, state, sound)
            configured = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(configured["editor.fontSize"], 15)
            self.assertEqual(configured[settings_manager.CUSTOM_PATH_KEY], str(sound))
            self.assertTrue(configured[settings_manager.CHIME_ENABLED_KEY])
            self.assertTrue(settings.with_name("settings.json.cursor-sound-rotator.bak").exists())

            settings_manager.restore(settings, state)
            self.assertEqual(json.loads(settings.read_text(encoding="utf-8")), original)

    def test_jsonc_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = root / "settings.json"
            state = root / "state.json"
            original = '{\n  // user comment\n  "editor.fontSize": 15,\n}\n'
            settings.write_text(original, encoding="utf-8")

            with self.assertRaises(settings_manager.SettingsError):
                settings_manager.configure(settings, state, root / "active.wav")
            self.assertEqual(settings.read_text(encoding="utf-8"), original)
            self.assertFalse(state.exists())

    def test_restore_does_not_overwrite_later_user_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = root / "settings.json"
            state = root / "state.json"
            settings.write_text("{}", encoding="utf-8")
            sound = root / "active.wav"
            settings_manager.configure(settings, state, sound)

            current = json.loads(settings.read_text(encoding="utf-8"))
            current[settings_manager.CUSTOM_PATH_KEY] = "/user/changed.wav"
            settings.write_text(json.dumps(current), encoding="utf-8")
            settings_manager.restore(settings, state)

            restored = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(
                restored[settings_manager.CUSTOM_PATH_KEY], "/user/changed.wav"
            )


class GeneratedPackTests(unittest.TestCase):
    def test_generated_pack_contains_valid_wav_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            count = generate_example_pack.generate_pack(destination)
            self.assertEqual(count, 6)
            files = sorted(destination.glob("*.wav"))
            self.assertEqual(len(files), 6)
            for path in files:
                with wave.open(str(path), "rb") as audio:
                    self.assertEqual(audio.getnchannels(), 1)
                    self.assertEqual(audio.getsampwidth(), 2)
                    self.assertEqual(audio.getframerate(), generate_example_pack.SAMPLE_RATE)
                    self.assertGreater(audio.getnframes(), 0)


if __name__ == "__main__":
    unittest.main()
