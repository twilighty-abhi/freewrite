from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox


def app_icon() -> QIcon:
    icon_path = Path(__file__).with_name("assets") / "freewrite.png"
    return QIcon(str(icon_path))


def main() -> int:
    app = QApplication(sys.argv)
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    try:
        # Import inside try so import-time errors show up too (common when packaged/launched via desktop).
        from .main_window import FreewriteMainWindow

        window = FreewriteMainWindow()
        if not icon.isNull():
            window.setWindowIcon(icon)
        window.show()
    except Exception:
        tb = traceback.format_exc()
        # Persist crash log for launcher-based runs (no terminal output).
        log_dir = Path.home() / ".local" / "share" / "freewrite"
        log_dir.mkdir(parents=True, exist_ok=True)
        crash_log = log_dir / "crash.log"
        try:
            crash_log.write_text(tb, encoding="utf-8")
        except Exception:
            crash_log = None

        print(tb, file=sys.stderr)
        QMessageBox.critical(
            None,
            "Freewrite failed to start",
            "Freewrite crashed during startup.\n\n"
            + (
                f"A crash log was written to:\n{crash_log}\n\n" if crash_log is not None else ""
            )
            + "Traceback:\n\n"
            + tb[-6000:],
        )
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
