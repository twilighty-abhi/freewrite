# Freewrite - Technical Notes For AI Agents

> `AGENTS.md` and `CLAUDE.md` are mirrors. If you make a substantial architecture, workflow, storage, packaging, or user-facing behavior change, update both files together.

## Product

Freewrite is a local-first, distraction-free writing app for Linux. It is built with Python 3.12, PySide6, and Qt.

## Credits

This repository is a Linux/PySide6 port of the original **Freewrite** app by **farza**.

- Website: `https://freewrite.io/`
- Upstream repository: `https://github.com/farzaa/freewrite`

The core experience is intentionally simple:

1. Open the app and start writing.
2. Entries are saved continuously as Markdown files.
3. The interface stays quiet during focused writing.
4. User data remains on disk in a readable format.

## Active Stack

- Runtime: Python 3.12+
- UI: PySide6 / Qt 6
- Packaging: PyInstaller
- PDF export: ReportLab
- Storage: local filesystem under `~/Documents/Freewrite/`

There is no backend service, sync layer, database, or cloud dependency.

## Project Layout

```text
ubuntu_freewrite/
  __main__.py        Module entry point
  main.py            QApplication startup
  main_window.py     Main Qt window, UI wiring, app behavior
  assets/            App icon and bundled static assets
  models.py          Entry dataclasses and naming helpers
  storage.py         Filesystem persistence and entry scanning
  pdf_export.py      ReportLab PDF export helpers
  prompts.py         ChatGPT/Claude prompt text
  default.md         Template content for new entries

packaging/linux/
  freewrite.desktop.template

scripts/
  package_ubuntu.sh
  install_ubuntu_app.sh
  uninstall_ubuntu_app.sh

run_freewrite.py
ubuntu_freewrite.spec
requirements.txt
```

## Run And Package

Run from source:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m ubuntu_freewrite
```

Build the local Ubuntu bundle:

```bash
scripts/package_ubuntu.sh
```

Install the user-level launcher:

```bash
scripts/install_ubuntu_app.sh
```

Generated output is ignored by git: `build/`, `dist/`, `Freewrite-ubuntu/`, and `Freewrite-ubuntu.tar.gz`.

## Data Model

Entries are represented by `HumanEntry` in `ubuntu_freewrite/models.py`.

Important fields:

- `id`: UUID for the entry.
- `date_label`: display date such as `Apr 26`.
- `filename`: canonical Markdown filename.
- `preview_text`: sidebar preview.
- `entry_type`: `EntryType.TEXT` or `EntryType.VIDEO`.
- `video_filename`: optional `.mov` filename for video entries.

Canonical entry filenames follow:

```text
[UUID]-[YYYY-MM-DD-HH-MM-SS].md
```

The parser in `StorageService.parse_canonical_entry_filename()` intentionally ignores non-canonical Markdown files in the documents folder.

## Storage Layout

Default root:

```text
~/Documents/Freewrite/
```

Text entry:

```text
~/Documents/Freewrite/[UUID]-[timestamp].md
```

Video entry assets, when present:

```text
~/Documents/Freewrite/Videos/[UUID]-[timestamp]/
  [UUID]-[timestamp].mov
  thumbnail.jpg
  transcript.md
```

`StorageService.video_candidates()` also checks older flat video locations for compatibility with migrated local data.

## Startup Behavior

`FreewriteMainWindow.__init__()` builds the UI, loads entries, and applies the saved theme.

On launch:

1. `StorageService.scan_entries()` loads canonical Markdown files.
2. Entries are sorted newest first by timestamp.
3. `pick_entry_on_startup()` selects an existing empty entry for today when possible.
4. If no suitable entry exists, `create_new_entry()` creates a new Markdown file.

## Autosave

Text entries autosave from `on_text_changed()` and the periodic `autosave_timer`.

Important behavior:

- `save_current_entry()` skips video entries.
- `autosave_current_text()` suppresses transient write errors to avoid interrupting typing.
- Explicit save paths can show `QMessageBox` warnings.
- `update_preview()` mutates only the matching sidebar row during typing to avoid cursor resets.

## UI Features

The main window provides:

- Plain text editor with optional Markdown highlighting.
- History sidebar.
- Font size cycling and basic font family selection.
- Focus timer with right-click context menu.
- Backspace/delete lock implemented through Qt key event filtering.
- Theme toggle persisted through `QSettings`.
- Fullscreen mode that temporarily hides the sidebar and bottom bar.
- PDF export for text entries.
- Chat browser handoff for ChatGPT, with clipboard fallback for long prompts.

## Video Status

Linux video recording is not implemented yet. `start_video_recording_placeholder()` shows an informational dialog.

Existing video entries can still be displayed if compatible assets are already present on disk. The app can:

- Resolve video files through `StorageService.load_video_path()`.
- Play video with `QMediaPlayer` and `QVideoWidget`.
- Read `transcript.md`.
- Copy a selected video transcript to the clipboard.
- Use transcript text as the chat prompt source when available.

## Packaging Notes

`scripts/package_ubuntu.sh` uses PyInstaller and `ubuntu_freewrite.spec`. The spec includes `ubuntu_freewrite/default.md` as package data.

The app icon lives at `ubuntu_freewrite/assets/freewrite.png`. It is used as the Qt window icon, included in the PyInstaller bundle, copied beside the portable launcher, and installed into the user icon theme for the desktop entry.

`scripts/install_ubuntu_app.sh` installs to:

```text
~/.local/opt/freewrite/
~/.local/share/applications/freewrite.desktop
```

`scripts/uninstall_ubuntu_app.sh` removes those user-level install paths.

## Maintenance Rules

- Keep user data local and human-readable.
- Do not commit generated bundles, PyInstaller output, Python bytecode, or virtual environments.
- Keep public docs focused on the Linux/Python app.
- Keep `AGENTS.md` and `CLAUDE.md` in sync.
- Prefer small, direct changes in the existing Qt/Python style over introducing new abstractions.
