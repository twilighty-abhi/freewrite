#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$HOME/.local/opt/freewrite"
DESKTOP_FILE="$HOME/.local/share/applications/freewrite.desktop"
ICON_FILE="$HOME/.local/share/icons/hicolor/1024x1024/apps/freewrite.png"

rm -rf "$INSTALL_DIR"
rm -f "$DESKTOP_FILE"
rm -f "$ICON_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$HOME/.local/share/applications" || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Freewrite uninstalled from user profile."
