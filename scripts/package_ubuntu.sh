#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif [[ -x "$ROOT_DIR/../.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/../.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

if ! "$PYTHON_BIN" -m pip show pyinstaller >/dev/null 2>&1; then
  echo "Error: pyinstaller is not installed in the selected Python environment." >&2
  echo "Run: $PYTHON_BIN -m pip install -r requirements.txt" >&2
  exit 1
fi

echo "[package] Building standalone binary with PyInstaller"
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean "$ROOT_DIR/ubuntu_freewrite.spec"

BUNDLE_DIR="$ROOT_DIR/Freewrite-ubuntu"
APP_SRC_DIR="$ROOT_DIR/dist/Freewrite"
ICON_SRC="$ROOT_DIR/ubuntu_freewrite/assets/freewrite.png"

if [[ ! -d "$APP_SRC_DIR" ]]; then
  echo "Error: Expected PyInstaller output at $APP_SRC_DIR was not found." >&2
  exit 1
fi

[[ -d "$BUNDLE_DIR" ]] && rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR"
cp -R "$APP_SRC_DIR" "$BUNDLE_DIR/"
cp "$ICON_SRC" "$BUNDLE_DIR/freewrite.png"

cat > "$BUNDLE_DIR/launch-freewrite.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$BASE_DIR/Freewrite/Freewrite" "$@"
EOF
chmod +x "$BUNDLE_DIR/launch-freewrite.sh"

cp "$ROOT_DIR/packaging/linux/freewrite.desktop.template" "$BUNDLE_DIR/freewrite.desktop"
sed -i \
  -e "s|@EXEC_PATH@|$BUNDLE_DIR/launch-freewrite.sh|" \
  -e "s|@ICON_PATH@|$BUNDLE_DIR/freewrite.png|" \
  "$BUNDLE_DIR/freewrite.desktop"

tar -C "$ROOT_DIR" -czf "$ROOT_DIR/Freewrite-ubuntu.tar.gz" "Freewrite-ubuntu"

echo "[package] Bundle ready: $BUNDLE_DIR"
echo "[package] Archive ready: $ROOT_DIR/Freewrite-ubuntu.tar.gz"