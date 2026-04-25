# Freewrite

Freewrite is a distraction-free writing app for Linux. It is built with Python, PySide6, and Qt, and keeps your writing local in plain Markdown files.

The app is designed for fast, low-friction writing sessions: open it, write, and let autosave handle the rest.

## Credits

This Linux port is based on the original **Freewrite** app by **farza**.

- Website: `https://freewrite.io/`
- Upstream repository: `https://github.com/farzaa/freewrite`

## Features

- Local-first Markdown entries stored in `~/Documents/Freewrite/`
- Automatic daily entry creation
- Continuous autosave
- History sidebar with entry previews
- Focus timer with configurable duration
- Optional backspace/delete lock for forward-only writing
- Light and dark themes
- Font family and size controls
- Fullscreen writing mode
- Markdown support (toggle)
  - Live Markdown highlighting while typing
  - Right-click the “Markdown is On/Off” button for a pure rendered Markdown view (no symbols)
- PDF export for text entries
- Browser handoff for ChatGPT prompts
- Video entry playback and transcript copying for existing video assets

Video recording is not yet implemented in the Linux app. The current video button shows a placeholder while that feature is being built.

## Requirements

- Python 3.12 or newer
- Linux desktop environment with Qt runtime support
- `pip`

On minimal Ubuntu installs, Qt may require:

```bash
sudo apt-get install -y libxcb-cursor0
```

PyInstaller builds may also require:

```bash
sudo apt-get install -y libtiff5
```

## Run From Source

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m ubuntu_freewrite
```

You can also run:

```bash
.venv/bin/python run_freewrite.py
```

## Package For Ubuntu

Build a portable app bundle with PyInstaller:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
chmod +x scripts/package_ubuntu.sh scripts/install_ubuntu_app.sh scripts/uninstall_ubuntu_app.sh
scripts/package_ubuntu.sh
```

This creates ignored local build artifacts:

- `dist/`
- `build/`
- `Freewrite-ubuntu/`
- `Freewrite-ubuntu.tar.gz`

Install the packaged app into your user profile:

```bash
scripts/install_ubuntu_app.sh
```

After installation, launch Freewrite from your app menu or run:

```bash
~/.local/opt/freewrite/launch-freewrite.sh
```

Uninstall the user-level app files and desktop launcher:

```bash
scripts/uninstall_ubuntu_app.sh
```

Single line command after edits: `chmod +x scripts/package_ubuntu.sh scripts/uninstall_ubuntu_app.sh scripts/install_ubuntu_app.sh && scripts/package_ubuntu.sh && scripts/uninstall_ubuntu_app.sh && scripts/install_ubuntu_app.sh`

## Build a .deb (for shipping)

Build a Debian package that users can install:

```bash
chmod +x scripts/package_deb.sh
scripts/package_deb.sh
```

Output:

- `dist-deb/freewrite_<version>_<arch>.deb`

Install locally for testing:

```bash
sudo apt install ./dist-deb/freewrite_*.deb
```

If you see missing library errors on user machines, install:

```bash
sudo apt-get install -y libxcb-cursor0 libtiff5
```

## Project Layout

```text
ubuntu_freewrite/              Python package for the Qt desktop app
ubuntu_freewrite/assets/       App icon and bundled static assets
packaging/linux/               Desktop launcher template
scripts/                       Build, install, and uninstall helpers
ubuntu_freewrite.spec          PyInstaller spec
run_freewrite.py               Script entry point for PyInstaller and local runs
requirements.txt               Python dependencies
```

## Data Storage

Freewrite stores entries under:

```text
~/Documents/Freewrite/
```

Text entries use this filename format:

```text
[UUID]-[YYYY-MM-DD-HH-MM-SS].md
```

Video assets, when present, are expected under:

```text
~/Documents/Freewrite/Videos/[UUID]-[YYYY-MM-DD-HH-MM-SS]/
```

That directory can contain the video file, `thumbnail.jpg`, and `transcript.md`.

## Development Notes

- Keep user data local and human-readable.
- Do not commit generated bundles, PyInstaller output, virtual environments, or Python bytecode.
- `AGENTS.md` and `CLAUDE.md` are mirrored technical notes for AI coding agents. Update both together when architecture or workflows change.

## License

MIT. See `LICENSE`.