#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)

ICON_SRC="$REPO_ROOT/assets/icons/inkotter.svg"
DESKTOP_SRC="$REPO_ROOT/packaging/linux/inkotter.desktop"

ICON_DST_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
DESKTOP_DST_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_DST="$DESKTOP_DST_DIR/inkotter.desktop"

mkdir -p "$ICON_DST_DIR" "$DESKTOP_DST_DIR"
cp "$ICON_SRC" "$ICON_DST_DIR/inkotter.svg"
cp "$DESKTOP_SRC" "$DESKTOP_DST"

printf '%s\n' "Installed icon to: $ICON_DST_DIR/inkotter.svg"
printf '%s\n' "Installed desktop file to: $DESKTOP_DST"
printf '%s\n' "Ensure 'inkotter-gui' is available on PATH for the launcher to work."
