#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)

ICON_SRC="$REPO_ROOT/assets/icons/inkotter.svg"
DESKTOP_SRC="$REPO_ROOT/packaging/linux/inkotter.desktop"
VENV_EXEC="$REPO_ROOT/.venv/bin/inkotter-gui"

ICON_DST_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
DESKTOP_DST_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_DST="$DESKTOP_DST_DIR/inkotter.desktop"

if [ -x "$VENV_EXEC" ]; then
  EXEC_PATH="$VENV_EXEC"
elif command -v inkotter-gui >/dev/null 2>&1; then
  EXEC_PATH=$(command -v inkotter-gui)
else
  printf '%s\n' "Error: no executable inkotter-gui found."
  printf '%s\n' "Expected one of:"
  printf '  %s\n' "$VENV_EXEC"
  printf '%s\n' "or an installed inkotter-gui on PATH."
  exit 1
fi

mkdir -p "$ICON_DST_DIR" "$DESKTOP_DST_DIR"
cp "$ICON_SRC" "$ICON_DST_DIR/inkotter.svg"
sed \
  -e "s|^Exec=.*$|Exec=$EXEC_PATH %F|" \
  -e "s|^Icon=.*$|Icon=inkotter|" \
  "$DESKTOP_SRC" >"$DESKTOP_DST"

printf '%s\n' "Installed icon to: $ICON_DST_DIR/inkotter.svg"
printf '%s\n' "Installed desktop file to: $DESKTOP_DST"
printf '%s\n' "Configured launcher Exec: $EXEC_PATH"
printf '%s\n' "If the application menu does not refresh immediately, run: kbuildsycoca6"
