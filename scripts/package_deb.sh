#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "Error: dpkg-deb is required to build a .deb." >&2
  echo "Install it with: sudo apt-get update && sudo apt-get install -y dpkg-dev" >&2
  exit 1
fi

ARCH="$(dpkg --print-architecture)"

VERSION="${FREEWRITE_VERSION:-}"
if [[ -z "$VERSION" ]]; then
  if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    VERSION="$(git describe --tags --always --dirty 2>/dev/null || true)"
  fi
fi
if [[ -z "$VERSION" ]]; then
  VERSION="$(date +%Y.%m.%d)"
fi

# Debian version rules:
# - must start with a digit
# - allowed chars: [0-9A-Za-z.+:~-]
# We sanitize git describe output to be dpkg-compatible.
VERSION="${VERSION#v}"
VERSION="$(echo "$VERSION" | tr '/_' '..')"
VERSION="$(echo "$VERSION" | tr '-' '.')"
VERSION="$(echo "$VERSION" | sed -E 's/[^0-9A-Za-z.+:~]/./g; s/\\.{2,}/./g; s/^\\.+//; s/\\.+$//')"
if [[ ! "$VERSION" =~ ^[0-9] ]]; then
  VERSION="0.${VERSION}"
fi

echo "[deb] Building PyInstaller bundle"
"$ROOT_DIR/scripts/package_ubuntu.sh"

BUNDLE_DIR="$ROOT_DIR/Freewrite-ubuntu/Freewrite"
ICON_SRC="$ROOT_DIR/ubuntu_freewrite/assets/freewrite.png"
DESKTOP_TEMPLATE="$ROOT_DIR/packaging/linux/freewrite.desktop.template"

if [[ ! -d "$BUNDLE_DIR" ]]; then
  echo "Error: bundle not found at $BUNDLE_DIR" >&2
  exit 1
fi
if [[ ! -f "$ICON_SRC" ]]; then
  echo "Error: icon not found at $ICON_SRC" >&2
  exit 1
fi
if [[ ! -f "$DESKTOP_TEMPLATE" ]]; then
  echo "Error: desktop template not found at $DESKTOP_TEMPLATE" >&2
  exit 1
fi

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

PKGROOT="$WORK_DIR/pkgroot"
mkdir -p "$PKGROOT/DEBIAN"
mkdir -p "$PKGROOT/opt/freewrite"
mkdir -p "$PKGROOT/usr/bin"
mkdir -p "$PKGROOT/usr/share/applications"
mkdir -p "$PKGROOT/usr/share/icons/hicolor/1024x1024/apps"

cp -R "$BUNDLE_DIR" "$PKGROOT/opt/freewrite/Freewrite"
install -m 0644 "$ICON_SRC" "$PKGROOT/usr/share/icons/hicolor/1024x1024/apps/freewrite.png"

cat > "$PKGROOT/usr/bin/freewrite" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec /opt/freewrite/Freewrite/Freewrite "$@"
EOF
chmod 0755 "$PKGROOT/usr/bin/freewrite"

sed \
  -e "s|@EXEC_PATH@|/usr/bin/freewrite|" \
  -e "s|@ICON_PATH@|freewrite|" \
  "$DESKTOP_TEMPLATE" > "$PKGROOT/usr/share/applications/freewrite.desktop"

cat > "$PKGROOT/DEBIAN/control" <<EOF
Package: freewrite
Version: $VERSION
Section: editors
Priority: optional
Architecture: $ARCH
Maintainer: Freewrite <noreply@example.com>
Description: Freewrite - distraction-free writing app
 A minimalist, local-first writing app for focused sessions.
EOF

cat > "$PKGROOT/DEBIAN/postinst" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi
exit 0
EOF
chmod 0755 "$PKGROOT/DEBIAN/postinst"

cat > "$PKGROOT/DEBIAN/prerm" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF
chmod 0755 "$PKGROOT/DEBIAN/prerm"

OUT_DIR="$ROOT_DIR/dist-deb"
mkdir -p "$OUT_DIR"
OUT_DEB="$OUT_DIR/freewrite_${VERSION}_${ARCH}.deb"

echo "[deb] Building $OUT_DEB"
dpkg-deb --build "$PKGROOT" "$OUT_DEB" >/dev/null

echo "[deb] Done: $OUT_DEB"

