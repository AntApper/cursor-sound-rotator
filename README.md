<p align="center">
  <img src="assets/banner-8bit.jpg" alt="Cursor Sound Rotator" width="100%">
</p>

<p align="center">
  <a href="#requirements"><img src="https://img.shields.io/badge/platform-macOS-black?style=flat-square" alt="macOS"></a>
  <a href="#cli-reference"><img src="https://img.shields.io/badge/runtime-Python%203-blue?style=flat-square" alt="Python 3"></a>
  <a href="#how-it-works"><img src="https://img.shields.io/badge/target-Cursor%20IDE-7B61FF?style=flat-square" alt="Cursor IDE"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License"></a>
</p>

# Cursor Sound Rotator

Randomized completion chimes for Cursor IDE, implemented without patching Cursor,
injecting code, or changing its application signature.

Cursor can play a custom sound when an agent finishes or needs attention, but its
settings accept only one file. This project keeps that one configured path and
safely replaces its contents with another clip after playback is detected.

## Highlights

- Works with any homogeneous pack of MP3, WAV, OGG, M4A, AAC, or FLAC files.
- Avoids immediate repeats when a pack contains two or more clips.
- Rescans the pack on every rotation, so same-format clips can be added live.
- Stages complete copies before using atomic per-file replacement.
- Uses only the Python 3 standard library.
- Runs as a user-level macOS LaunchAgent and starts at login.
- Creates an original, redistributable chiptune starter pack on first install.
- Backs up Cursor settings and never overwrites JSON it cannot parse safely.

## Requirements

- macOS
- Cursor IDE with the Completion Sound feature
- Python 3

Tested with Cursor 3.19.13 on macOS 26.6.2. Cursor internals can change; see
[Compatibility and limitations](#compatibility-and-limitations).

## Quick start

```bash
git clone https://github.com/AntApper/cursor-sound-rotator.git
cd cursor-sound-rotator
./install.sh
```

If `~/.cursor-sounds/clips` is empty, the installer generates six original WAV
chiptune notifications. It then:

1. Validates that the pack uses one audio format.
2. Initializes the active sound and Cursor cache.
3. Generates and validates a user LaunchAgent plist.
4. Safely updates strict-JSON Cursor settings, with a backup and restoration state.
5. Starts the rotator in the current GUI login session.

If Cursor's `settings.json` contains JSONC comments or cannot be parsed safely,
the installer does not modify it. It prints the exact active sound path for you
to select under **Cursor Settings > General > Completion Sound**.

### Verify it

Click **Preview**, wait approximately two seconds, then click it again. With two
or more clips installed, the next clip will differ from the previous one.

```bash
launchctl print gui/$(id -u)/io.github.antapper.cursor-sound-rotator
tail -f ~/Library/Logs/CursorSoundRotator/rotator.log
```

## Install your own sound pack

Pass any directory containing supported audio files:

```bash
./install.sh /path/to/my-sound-pack
```

A pack must use one format because Cursor is configured with one stable filename
and extension. Unsupported files are ignored; installation fails safely if no
supported audio remains or multiple supported formats are mixed.

To add clips later, copy files with the pack's existing extension:

```bash
cp /path/to/more-sounds/*.mp3 ~/.cursor-sounds/clips/
```

The daemon rescans before every rotation. It retries safely if the directory is
temporarily empty or a source file disappears.

### Supported formats

| Format | Extensions |
|---|---|
| MPEG Audio Layer III | `.mp3` |
| Waveform Audio | `.wav` |
| Ogg Vorbis | `.ogg` |
| Advanced Audio Coding | `.aac`, `.m4a` |
| Free Lossless Audio Codec | `.flac` |

## Optional Simpsons example

The six Homer Simpson clips used during development are documented under
[`soundpacks/simpsons-homer-mmmm`](soundpacks/simpsons-homer-mmmm). They are not
redistributed in this repository because they are third-party copyrighted media.
An optional helper downloads them directly from the source site:

```bash
./soundpacks/simpsons-homer-mmmm/download.sh
./install.sh ./soundpacks/simpsons-homer-mmmm/downloads/wav
```

Review the source site's terms and use third-party media only where you have
permission. Those recordings are not covered by this project's MIT license.

## How it works

Inspection of Cursor 3.19.13's `workbench.desktop.main.js` showed that custom
chimes are fetched from disk and decoded through Chromium's Web Audio API.
Cursor also keeps an internal copied sound under its profile storage.

```text
Agent finishes or Preview is clicked
                 |
                 v
Cursor reads its cached custom sound
                 |
                 v
Rotator observes a newer access time
                 |
          waits for streaming
                 |
                 v
Rescans pack and selects a non-repeating clip
                 |
                 v
Stages complete copies beside both destinations
                 |
                 v
Atomically replaces each destination file
```

The two destination replacements are individually atomic; no filesystem can
make replacements in separate directories one transaction. Both copies are
fully staged before either destination is changed.

## Compatibility and limitations

- Playback detection uses file access timestamps (`st_atime`). It works on the
  tested default APFS configuration, but filesystems can disable or coalesce
  access-time updates. A 60-second idle rotation provides a fallback, so strict
  per-event rotation is best effort rather than a universal guarantee.
- Cursor's private cache path and internal playback implementation are not a
  public API and may change in future versions.
- The automatic installer currently targets macOS. The Python rotator can be
  adapted to other platforms with an equivalent service manager and cache path.
- Cursor may show Background Items or privacy notifications for user LaunchAgents.
- Runtime files are stored in `~/.cursor-sounds` because macOS can restrict
  background access to protected folders such as Downloads, Documents, and Desktop.

## CLI reference

```bash
python3 cursor_sound_rotator.py [OPTIONS]
```

| Option | Default | Purpose |
|---|---|---|
| `--sounds-dir PATH` | `~/.cursor-sounds/clips` | Homogeneous sound pack |
| `--target-file PATH` | `~/.cursor-sounds/cursor-completion-sound.mp3` | Path selected in Cursor |
| `--cursor-cache PATH` | Cursor profile `customSounds/custom-chime.mp3` | Cursor's copied sound |
| `--delay SECONDS` | `2.0` | Guard time after a detected read |
| `--idle-interval SECONDS` | `60.0` | Fallback rotation; `0` disables it |
| `--poll-interval SECONDS` | `1.0` | Access-time polling interval |
| `--once` | disabled | Rotate once and exit |

The target and cache extensions must match the clips in the active pack.

## Installer options

```bash
./install.sh [--no-start] [--no-configure] [SOUND_DIRECTORY]
```

- `--no-start` installs and validates everything without loading the service.
- `--no-configure` leaves Cursor settings untouched and prints the path to select.

## Uninstall

Stop the service and preserve the runtime clips:

```bash
./uninstall.sh
```

Restore saved Cursor settings and remove runtime files and logs:

```bash
./uninstall.sh --purge
```

The restorer changes only values still owned by this installation. If you changed
a setting afterward, that newer user value is left alone.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile cursor_sound_rotator.py tools/*.py
bash -n install.sh uninstall.sh soundpacks/simpsons-homer-mmmm/download.sh
```

The included test suite covers syntax, unit, integration, generated-audio, and
plist validation on macOS.

## Trademark notice

This is an unofficial community project and is not affiliated with, sponsored by,
or endorsed by Anysphere. Cursor and the Cursor logo are trademarks of their
respective owner. The banner uses the logo solely to identify compatibility.

## License

The software and original generated chiptune pack are available under the
[MIT License](LICENSE). Third-party media downloaded through optional example
helpers is excluded from that license.
