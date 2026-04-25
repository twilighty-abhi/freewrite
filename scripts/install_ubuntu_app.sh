#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="$ROOT_DIR/Freewrite-ubuntu"

if [[ ! -d "$BUNDLE_DIR/Freewrite" ]]; then
  echo "Bundle not found. Run scripts/package_ubuntu.sh first."
  exit 1
fi

INSTALL_DIR="$HOME/.local/opt/freewrite"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/freewrite.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/1024x1024/apps"
ICON_FILE="$ICON_DIR/freewrite.png"

mkdir -p "$INSTALL_DIR"
TEMP_INSTALL_DIR="$INSTALL_DIR/Freewrite.new"
rm -rf "$TEMP_INSTALL_DIR"
cp -R "$BUNDLE_DIR/Freewrite" "$TEMP_INSTALL_DIR"

if [[ ! -x "$TEMP_INSTALL_DIR/Freewrite" ]]; then
  echo "Install failed: packaged executable is missing or not executable." >&2
  exit 1
fi

rm -rf "$INSTALL_DIR/Freewrite"
mv "$TEMP_INSTALL_DIR" "$INSTALL_DIR/Freewrite"

cat > "$INSTALL_DIR/launch-freewrite.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$INSTALL_DIR/Freewrite/Freewrite" "\$@"
EOF
chmod +x "$INSTALL_DIR/launch-freewrite.sh"

mkdir -p "$DESKTOP_DIR"
mkdir -p "$ICON_DIR"
cp "$ROOT_DIR/ubuntu_freewrite/assets/freewrite.png" "$ICON_FILE"
sed \
  -e "s|@EXEC_PATH@|$INSTALL_DIR/launch-freewrite.sh|" \
  -e "s|@ICON_PATH@|freewrite|" \
  "$ROOT_DIR/packaging/linux/freewrite.desktop.template" > "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Installed Freewrite launcher: $DESKTOP_FILE"
