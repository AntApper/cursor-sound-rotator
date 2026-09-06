#!/usr/bin/env bash
# Stop Cursor Sound Rotator and optionally remove its files and settings changes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.cursor-sounds"
STATE_PATH="$INSTALL_DIR/settings-state.json"
CURSOR_SETTINGS="$HOME/Library/Application Support/Cursor/User/settings.json"
LOG_DIR="$HOME/Library/Logs/CursorSoundRotator"
PLIST_LABEL="io.github.antapper.cursor-sound-rotator"
PLIST_DEST="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
DOMAIN="gui/$(id -u)"
PURGE=false

case "${1:-}" in
    "") ;;
    --purge) PURGE=true ;;
    -h|--help)
        echo "Usage: ./uninstall.sh [--purge]"
        echo "  --purge  Also restore saved Cursor settings and delete runtime files"
        exit 0
        ;;
    *)
        echo "Error: Unknown option: $1" >&2
        exit 2
        ;;
esac

printf '%s\n' "Cursor Sound Rotator uninstaller" "--------------------------------"
echo "[*] Stopping LaunchAgent..."
for LABEL in \
    "$PLIST_LABEL" \
    "com.cursor.sound-rotator" \
    "com.ant.cursor-sound-rotator"; do
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
done
rm -f \
    "$PLIST_DEST" \
    "$HOME/Library/LaunchAgents/com.cursor.sound-rotator.plist" \
    "$HOME/Library/LaunchAgents/com.ant.cursor-sound-rotator.plist"
echo "[OK] LaunchAgent removed."

if [[ "$PURGE" == true ]]; then
    PYTHON_BIN="$(command -v python3 || true)"
    SETTINGS_HELPER="$INSTALL_DIR/settings_manager.py"
    if [[ ! -f "$SETTINGS_HELPER" ]]; then
        SETTINGS_HELPER="$SCRIPT_DIR/tools/settings_manager.py"
    fi

    if [[ -f "$STATE_PATH" ]]; then
        if [[ -z "$PYTHON_BIN" || ! -f "$CURSOR_SETTINGS" ]]; then
            echo "Error: Saved settings state exists, but Cursor settings cannot be restored." >&2
            echo "Runtime files were preserved to avoid leaving a broken sound path." >&2
            exit 1
        fi
        if "$PYTHON_BIN" "$SETTINGS_HELPER" restore \
            --settings "$CURSOR_SETTINGS" \
            --state "$STATE_PATH"; then
            echo "[OK] Restored pre-install Cursor settings."
        else
            echo "Error: Cursor settings could not be restored automatically." >&2
            echo "A backup may exist beside settings.json; runtime files were preserved." >&2
            exit 1
        fi
    else
        echo "[!] No saved settings state found; Cursor settings were left unchanged."
    fi

    rm -rf "$INSTALL_DIR" "$LOG_DIR"
    echo "[OK] Removed runtime files and logs."
else
    echo "[OK] Runtime files preserved at $INSTALL_DIR."
    echo "     Use './uninstall.sh --purge' for complete removal."
fi

printf '%s\n' "" "Uninstallation complete."
