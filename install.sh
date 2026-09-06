#!/usr/bin/env bash
# Install Cursor Sound Rotator as a per-user macOS LaunchAgent.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.cursor-sounds"
CLIPS_DIR="$INSTALL_DIR/clips"
STATE_PATH="$INSTALL_DIR/settings-state.json"
CURSOR_SETTINGS="$HOME/Library/Application Support/Cursor/User/settings.json"
CURSOR_CACHE_DIR="$HOME/Library/Application Support/Cursor/User/globalStorage/customSounds"
LOG_DIR="$HOME/Library/Logs/CursorSoundRotator"
LOG_PATH="$LOG_DIR/rotator.log"
PLIST_LABEL="io.github.antapper.cursor-sound-rotator"
PLIST_DEST="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
DOMAIN="gui/$(id -u)"
CUSTOM_PACK=""
START_SERVICE=true
CONFIGURE_CURSOR=true

show_help() {
    cat <<EOF
Usage: ./install.sh [OPTIONS] [SOUND_DIRECTORY]

Install the rotator with an existing homogeneous sound pack. If no pack and no
existing clips are supplied, the installer generates an original WAV chiptune
starter pack.

Options:
  --no-start       Install files and plist without loading the LaunchAgent
  --no-configure   Do not edit Cursor settings.json
  -h, --help       Show this help

Examples:
  ./install.sh
  ./install.sh /path/to/my-mp3-pack
  ./install.sh --no-start --no-configure /path/to/test-pack
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        --no-start)
            START_SERVICE=false
            shift
            ;;
        --no-configure)
            CONFIGURE_CURSOR=false
            shift
            ;;
        --*)
            echo "Error: Unknown option: $1" >&2
            show_help >&2
            exit 2
            ;;
        *)
            if [[ -n "$CUSTOM_PACK" ]]; then
                echo "Error: Only one sound directory may be supplied." >&2
                exit 2
            fi
            CUSTOM_PACK="$1"
            shift
            ;;
    esac
done

PYTHON_BIN="$(command -v python3 || true)"
if [[ -z "$PYTHON_BIN" ]]; then
    echo "Error: python3 was not found in PATH." >&2
    exit 1
fi
if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Error: The automatic installer currently supports macOS only." >&2
    exit 1
fi

printf '%s\n' "Cursor Sound Rotator installer" "------------------------------"
echo "[OK] Python: $PYTHON_BIN"

mkdir -p "$INSTALL_DIR" "$CURSOR_CACHE_DIR" "$LOG_DIR" "$HOME/Library/LaunchAgents"
chmod 700 "$INSTALL_DIR" "$LOG_DIR"

if [[ -n "$CUSTOM_PACK" ]]; then
    echo "[*] Validating and staging custom sound pack..."
    PACK_INFO="$($PYTHON_BIN "$SCRIPT_DIR/tools/pack_manager.py" install "$CUSTOM_PACK" "$CLIPS_DIR")"
elif [[ -d "$CLIPS_DIR" && -n "$(find "$CLIPS_DIR" -type f -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
    echo "[*] Validating existing sound pack..."
    PACK_INFO="$($PYTHON_BIN "$SCRIPT_DIR/tools/pack_manager.py" inspect "$CLIPS_DIR")"
else
    echo "[*] Generating the original chiptune starter pack..."
    rm -rf "$CLIPS_DIR"
    "$PYTHON_BIN" "$SCRIPT_DIR/tools/generate_example_pack.py" "$CLIPS_DIR"
    PACK_INFO="$($PYTHON_BIN "$SCRIPT_DIR/tools/pack_manager.py" inspect "$CLIPS_DIR")"
fi
read -r PACK_EXT CLIP_COUNT <<<"$PACK_INFO"
echo "[OK] Sound pack: $CLIP_COUNT .$PACK_EXT clips"

TARGET_SOUND="$INSTALL_DIR/cursor-completion-sound.$PACK_EXT"
CURSOR_CACHE="$CURSOR_CACHE_DIR/custom-chime.$PACK_EXT"

cp -f "$SCRIPT_DIR/cursor_sound_rotator.py" "$INSTALL_DIR/cursor_sound_rotator.py"
cp -f "$SCRIPT_DIR/tools/settings_manager.py" "$INSTALL_DIR/settings_manager.py"
chmod 755 "$INSTALL_DIR/cursor_sound_rotator.py" "$INSTALL_DIR/settings_manager.py"

"$PYTHON_BIN" "$INSTALL_DIR/cursor_sound_rotator.py" \
    --sounds-dir "$CLIPS_DIR" \
    --target-file "$TARGET_SOUND" \
    --cursor-cache "$CURSOR_CACHE" \
    --once
[[ -s "$TARGET_SOUND" && -s "$CURSOR_CACHE" ]] || {
    echo "Error: Initial sound rotation did not create valid output files." >&2
    exit 1
}
echo "[OK] Initialized active sound: $TARGET_SOUND"

"$PYTHON_BIN" - "$PLIST_DEST" "$PLIST_LABEL" "$PYTHON_BIN" \
    "$INSTALL_DIR/cursor_sound_rotator.py" "$CLIPS_DIR" "$TARGET_SOUND" \
    "$CURSOR_CACHE" "$LOG_PATH" <<'PY'
import plistlib
import sys
from pathlib import Path

(
    plist_path,
    label,
    python_path,
    script_path,
    clips_path,
    target_path,
    cache_path,
    log_path,
) = map(Path, sys.argv[1:])

payload = {
    "Label": str(label),
    "ProgramArguments": [
        str(python_path),
        str(script_path),
        "--sounds-dir",
        str(clips_path),
        "--target-file",
        str(target_path),
        "--cursor-cache",
        str(cache_path),
    ],
    "RunAtLoad": True,
    "KeepAlive": True,
    "ThrottleInterval": 10,
    "ProcessType": "Background",
    "StandardOutPath": str(log_path),
    "StandardErrorPath": str(log_path),
}
with plist_path.open("wb") as output:
    plistlib.dump(payload, output, sort_keys=False)
PY
plutil -lint "$PLIST_DEST" >/dev/null
echo "[OK] LaunchAgent: $PLIST_DEST"

if [[ "$CONFIGURE_CURSOR" == true ]]; then
    if "$PYTHON_BIN" "$INSTALL_DIR/settings_manager.py" configure \
        --settings "$CURSOR_SETTINGS" \
        --state "$STATE_PATH" \
        --sound "$TARGET_SOUND"; then
        echo "[OK] Cursor settings configured safely."
    else
        echo "[!] Automatic settings update skipped."
        echo "    In Cursor, choose this custom sound manually:"
        echo "    $TARGET_SOUND"
    fi
else
    echo "[!] Cursor settings were not changed (--no-configure)."
    echo "    Select this sound manually: $TARGET_SOUND"
fi

if [[ "$START_SERVICE" == true ]]; then
    echo "[*] Starting LaunchAgent..."
    for OLD_LABEL in \
        "$PLIST_LABEL" \
        "com.cursor.sound-rotator" \
        "com.ant.cursor-sound-rotator"; do
        launchctl bootout "$DOMAIN/$OLD_LABEL" 2>/dev/null || true
    done
    rm -f \
        "$HOME/Library/LaunchAgents/com.cursor.sound-rotator.plist" \
        "$HOME/Library/LaunchAgents/com.ant.cursor-sound-rotator.plist"

    launchctl bootstrap "$DOMAIN" "$PLIST_DEST"
    launchctl kickstart -k "$DOMAIN/$PLIST_LABEL"
    launchctl print "$DOMAIN/$PLIST_LABEL" >/dev/null
    echo "[OK] Service started: $PLIST_LABEL"
else
    echo "[!] Service was not started (--no-start)."
fi

cat <<EOF

Installation complete.
  Active sound: $TARGET_SOUND
  Clips:        $CLIPS_DIR
  Log:          $LOG_PATH
EOF
