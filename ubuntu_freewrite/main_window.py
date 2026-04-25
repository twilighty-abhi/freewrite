from __future__ import annotations

import webbrowser
from dataclasses import replace
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEvent, QSettings, QTimer, Qt, QUrl
from PySide6.QtGui import (
    QCloseEvent,
    QDesktopServices,
    QFont,
    QKeyEvent,
    QKeySequence,
    QShortcut,
    QTextOption,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTextBrowser,
    QSplitter,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .models import EntryType, HumanEntry
from .pdf_export import export_text_to_pdf, extract_title_from_content
from .markdown_highlighter import MarkdownHighlighter
from .prompts import AI_CHAT_PROMPT, CLAUDE_PROMPT
from .storage import StorageService


class FreewriteMainWindow(QMainWindow):
    def __init__(self, storage: Optional[StorageService] = None) -> None:
        super().__init__()
        self.storage = storage or StorageService()
        self.settings = QSettings("Freewrite", "FreewriteUbuntu")
        self.entries: list[HumanEntry] = []
        self.selected_entry_id: Optional[str] = None
        self.backspace_disabled = self.settings.value("backspaceDisabled", False, type=bool)
        self.timer_running = False
        self.time_remaining = self.settings.value("timeRemaining", 900, type=int)
        self.current_font_family = self.settings.value("fontFamily", "Sans Serif", type=str)
        self.font_size = self.settings.value("fontSize", 18, type=int)
        self.color_scheme = self.settings.value("colorScheme", "light", type=str)
        self.fullscreen_enabled = False
        self.sidebar_was_visible = True
        self.did_copy_prompt = False
        self.did_copy_transcript = False
        self.current_video_url: Optional[Path] = None
        self.selected_video_has_transcript = False
        self.showing_video = False
        self.current_text = ""
        self.last_saved_text = ""
        self.markdown_enabled = self.settings.value("markdownEnabled", False, type=bool)
        self.markdown_rendered_view_enabled = self.settings.value("markdownRenderedViewEnabled", False, type=bool)
        self.placeholder_text = "Begin writing"
        self.placeholder_options = [
            "Begin writing",
            "Pick a thought and go",
            "Start typing",
            "What's on your mind",
            "Just start",
            "Type your first thought",
            "Start with one sentence",
            "Just say it",
        ]
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick_timer)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(1000)
        self.autosave_timer.timeout.connect(self.autosave_current_text)
        self.autosave_timer.start()
        self.update_countdown = QTimer(self)
        self.update_countdown.setInterval(250)
        self.update_countdown.timeout.connect(self.refresh_timer_label)
        self.update_countdown.start()
        self.markdown_render_timer = QTimer(self)
        self.markdown_render_timer.setInterval(120)
        self.markdown_render_timer.setSingleShot(True)
        self.markdown_render_timer.timeout.connect(self.refresh_rendered_markdown_view)
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.errorOccurred.connect(self.on_media_error)

        self.setWindowTitle("Freewrite")
        self.resize(1100, 600)
        self.setMinimumSize(980, 600)

        self._build_ui()
        self._build_shortcuts()
        self.load_existing_entries()
        self.apply_theme()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal, root)
        splitter.setChildrenCollapsible(False)

        self.editor_stack = QStackedWidget(splitter)
        self.plain_editor = QPlainTextEdit()
        self.plain_editor.setFrameShape(QFrame.NoFrame)
        self.plain_editor.setPlaceholderText(self.placeholder_text)
        self.plain_editor.setLayoutDirection(Qt.LeftToRight)
        text_option = self.plain_editor.document().defaultTextOption()
        text_option.setTextDirection(Qt.LeftToRight)
        text_option.setAlignment(Qt.AlignLeft)
        self.plain_editor.document().setDefaultTextOption(text_option)
        self.plain_editor.textChanged.connect(self.on_text_changed)
        self.plain_editor.installEventFilter(self)
        self.plain_editor.viewport().installEventFilter(self)

        self.markdown_highlighter: MarkdownHighlighter | None = None

        self.markdown_rendered_view = QTextBrowser()
        self.markdown_rendered_view.setFrameShape(QFrame.NoFrame)
        self.markdown_rendered_view.setOpenExternalLinks(True)
        self.markdown_rendered_view.setReadOnly(True)

        self.video_placeholder = QWidget()
        video_layout = QVBoxLayout(self.video_placeholder)
        video_layout.addStretch(1)
        self.video_widget = QVideoWidget()
        self.media_player.setVideoOutput(self.video_widget)
        video_layout.addWidget(self.video_widget)
        self.video_title_label = QLabel("Video playback will appear here.")
        self.video_title_label.setAlignment(Qt.AlignCenter)
        self.video_title_label.setWordWrap(True)
        video_layout.addWidget(self.video_title_label)
        video_layout.addStretch(1)

        # Index 0: editor, Index 1: rendered markdown view, Index 2: video placeholder
        self.editor_stack.addWidget(self.plain_editor)
        self.editor_stack.addWidget(self.markdown_rendered_view)
        self.editor_stack.addWidget(self.video_placeholder)

        self.sidebar = QWidget(splitter)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(8)

        header_row = QHBoxLayout()
        self.history_button = QPushButton("History")
        self.history_button.clicked.connect(self.open_documents_folder)
        self.history_path_label = QLabel(str(self.storage.root))
        self.history_path_label.setWordWrap(True)
        header_row.addWidget(self.history_button)
        header_row.addWidget(self.history_path_label, 1)
        sidebar_layout.addLayout(header_row)

        self.entry_list = QListWidget()
        self.entry_list.currentItemChanged.connect(self.on_entry_selected)
        sidebar_layout.addWidget(self.entry_list, 1)

        splitter.addWidget(self.editor_stack)
        splitter.addWidget(self.sidebar)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([820, 280])

        root_layout.addWidget(splitter, 1)
        self.bottom_bar = self._build_bottom_bar()
        root_layout.addWidget(self.bottom_bar)
        self.setCentralWidget(root)
        self.apply_markdown_mode()

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget(self)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(12, 10, 12, 10)
        bar_layout.setSpacing(8)

        self.font_size_button = QPushButton(self.font_size_label())
        self.font_size_button.clicked.connect(self.cycle_font_size)
        bar_layout.addWidget(self.font_size_button)

        for label, handler in [
            ("Lato", lambda: self.set_font_family("Lato")),
            ("Arial", lambda: self.set_font_family("Arial")),
            ("System", lambda: self.set_font_family("Sans Serif")),
            ("Serif", lambda: self.set_font_family("Times New Roman")),
            ("Random", self.random_font),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            bar_layout.addWidget(button)

        bar_layout.addStretch(1)

        self.timer_button = QPushButton(self.timer_label())
        self.timer_button.clicked.connect(self.toggle_timer)
        self.timer_button.installEventFilter(self)
        bar_layout.addWidget(self.timer_button)

        self.video_button = QPushButton("Video")
        self.video_button.clicked.connect(self.start_video_recording_placeholder)
        bar_layout.addWidget(self.video_button)

        self.chat_button = QPushButton("Chat")
        self.chat_button.clicked.connect(self.open_chat_menu)
        bar_layout.addWidget(self.chat_button)

        self.copy_transcript_button = QPushButton("Copy Transcript")
        self.copy_transcript_button.clicked.connect(self.copy_video_transcript)
        bar_layout.addWidget(self.copy_transcript_button)

        self.markdown_button = QPushButton(self.markdown_label())
        self.markdown_button.clicked.connect(self.toggle_markdown)
        self.markdown_button.installEventFilter(self)
        bar_layout.addWidget(self.markdown_button)

        self.backspace_button = QPushButton(self.backspace_label())
        self.backspace_button.clicked.connect(self.toggle_backspace)
        bar_layout.addWidget(self.backspace_button)

        self.fullscreen_button = QPushButton("Fullscreen")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        bar_layout.addWidget(self.fullscreen_button)

        self.new_entry_button = QPushButton("New Entry")
        self.new_entry_button.clicked.connect(self.create_new_entry)
        bar_layout.addWidget(self.new_entry_button)

        self.theme_button = QPushButton(self.theme_label())
        self.theme_button.clicked.connect(self.toggle_theme)
        bar_layout.addWidget(self.theme_button)

        self.history_toggle_button = QPushButton("History")
        self.history_toggle_button.clicked.connect(self.toggle_sidebar)
        bar_layout.addWidget(self.history_toggle_button)

        return bar

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self.save_current_entry)
        QShortcut(QKeySequence.StandardKey.Copy, self, activated=self.copy_prompt_to_clipboard)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.toggle_sidebar)
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.exit_fullscreen_if_needed)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.create_new_entry)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_selected_entry_pdf)

    def exit_fullscreen_if_needed(self) -> None:
        if self.fullscreen_enabled:
            self.toggle_fullscreen()

    def apply_theme(self) -> None:
        if self.color_scheme == "dark":
            self.setStyleSheet(
                """
                QMainWindow, QWidget { background: #0f0f10; color: #efefef; }
                QPlainTextEdit { background: #0f0f10; color: #efefef; selection-background-color: #3c3c3c; }
                QTextEdit { background: #0f0f10; color: #efefef; selection-background-color: #3c3c3c; }
                QListWidget { background: #111113; border: 1px solid #232326; }
                QPushButton { background: #1a1a1d; border: 1px solid #2b2b31; padding: 6px 10px; border-radius: 6px; }
                QPushButton:hover { background: #242428; }
                """
            )
        else:
            self.setStyleSheet(
                """
                QMainWindow, QWidget { background: #ffffff; color: #161616; }
                QPlainTextEdit { background: #ffffff; color: #161616; selection-background-color: #dcdcdc; }
                QTextEdit { background: #ffffff; color: #161616; selection-background-color: #dcdcdc; }
                QListWidget { background: #ffffff; border: 1px solid #e8e8e8; }
                QPushButton { background: #f5f5f5; border: 1px solid #d5d5d5; padding: 6px 10px; border-radius: 6px; }
                QPushButton:hover { background: #ebebeb; }
                """
            )
        self.apply_editor_font()
        self.refresh_timer_label()
        self.refresh_bottom_buttons()
        if self.markdown_highlighter is not None:
            self.markdown_highlighter.set_dark_mode(self.color_scheme == "dark")

    def apply_editor_font(self) -> None:
        font = QFont(self.current_font_family, self.font_size)
        self.plain_editor.setFont(font)
        self.markdown_rendered_view.setFont(font)
        self.video_title_label.setFont(font)
        self.font_size_button.setText(self.font_size_label())
        if self.markdown_highlighter is not None:
            self.markdown_highlighter.set_base_font_size(self.font_size)

    def refresh_bottom_buttons(self) -> None:
        self.timer_button.setText(self.timer_label())
        self.backspace_button.setText(self.backspace_label())
        self.theme_button.setText(self.theme_label())
        self.markdown_button.setText(self.markdown_label())
        self.copy_transcript_button.setVisible(self.selected_video_has_transcript)
        self.copy_transcript_button.setEnabled(self.selected_video_has_transcript)

    def refresh_timer_label(self) -> None:
        self.timer_button.setText(self.timer_label())

    def font_size_label(self) -> str:
        return f"{self.font_size}px"

    def timer_label(self) -> str:
        if not self.timer_running and self.time_remaining == 900:
            return "15:00"
        minutes, seconds = divmod(max(self.time_remaining, 0), 60)
        return f"{minutes}:{seconds:02d}"

    def backspace_label(self) -> str:
        return "Backspace is Off" if self.backspace_disabled else "Backspace is On"

    def markdown_label(self) -> str:
        return "Markdown is On" if self.markdown_enabled else "Markdown is Off"

    def theme_label(self) -> str:
        return "Light" if self.color_scheme == "dark" else "Dark"

    def load_existing_entries(self) -> None:
        loaded = self.storage.scan_entries()
        self.entries = [item.entry for item in loaded]
        self.populate_sidebar()
        today_entry = self.pick_entry_on_startup()
        if today_entry is None:
            self.create_new_entry()
        else:
            self.select_entry(today_entry)

    def pick_entry_on_startup(self) -> Optional[HumanEntry]:
        if not self.entries:
            return None
        if self.entries[0].entry_type == EntryType.VIDEO:
            return None
        today = date.today()
        for entry in self.entries:
            if self.entry_is_from_today(entry, today):
                return entry
        return self.entries[0]

    def entry_is_from_today(self, entry: HumanEntry, today: date) -> bool:
        try:
            timestamp = datetime.strptime(self.extract_timestamp(entry.filename), "%Y-%m-%d-%H-%M-%S")
            return timestamp.date() == today
        except ValueError:
            return False

    def extract_timestamp(self, filename: str) -> str:
        stem = Path(filename).stem
        start = stem.find("-[")
        end = stem.rfind("]")
        if start == -1 or end == -1:
            return ""
        return stem.split("]-[", 1)[1].rstrip("]")

    def populate_sidebar(self) -> None:
        self.entry_list.blockSignals(True)
        self.entry_list.clear()
        for entry in self.entries:
            label = f"{entry.preview_text or ' '}\n{entry.date_label}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, entry.id)
            self.entry_list.addItem(item)
        self.entry_list.blockSignals(False)
        self.highlight_selected_entry()

    def highlight_selected_entry(self) -> None:
        for index in range(self.entry_list.count()):
            item = self.entry_list.item(index)
            if self.selected_entry_id is not None and str(item.data(Qt.UserRole)) == self.selected_entry_id:
                self.entry_list.setCurrentItem(item)
                break

    def current_entry(self) -> Optional[HumanEntry]:
        if self.selected_entry_id is None:
            return None
        for entry in self.entries:
            if str(entry.id) == self.selected_entry_id:
                return entry
        return None

    def select_entry(self, entry: HumanEntry) -> None:
        self.selected_entry_id = str(entry.id)
        if entry.entry_type == EntryType.VIDEO and entry.video_filename:
            self.show_video_entry(entry)
        else:
            self.show_text_entry(entry)
        self.highlight_selected_entry()

    def show_text_entry(self, entry: HumanEntry) -> None:
        self.showing_video = False
        self.current_video_url = None
        self.media_player.stop()
        self.apply_markdown_mode()
        content = self.read_entry_text(entry)
        self.plain_editor.blockSignals(True)
        self.plain_editor.setPlainText(content)
        self.plain_editor.blockSignals(False)
        self.last_saved_text = self.current_editor_text()
        self.current_text = self.last_saved_text
        self.placeholder_text = self.random_placeholder()
        self.selected_video_has_transcript = False
        self.did_copy_transcript = False
        self.apply_editor_font()
        self.refresh_bottom_buttons()

    def show_video_entry(self, entry: HumanEntry) -> None:
        self.showing_video = True
        self.editor_stack.setCurrentWidget(self.video_placeholder)
        self.media_player.stop()
        self.video_title_label.setText(
            f"Video entry selected\n{entry.video_filename or entry.filename}"
        )
        self.current_video_url = self.storage.load_video_path(entry.video_filename or "")
        self.selected_video_has_transcript = bool(entry.video_filename and self.storage.read_transcript(entry.video_filename))
        self.did_copy_transcript = False
        self.refresh_bottom_buttons()
        if self.current_video_url is not None:
            self.media_player.setSource(QUrl.fromLocalFile(str(self.current_video_url)))
            self.media_player.play()
        else:
            self.video_title_label.setText(
                f"Video file missing for entry\n{entry.video_filename or entry.filename}"
            )

    def read_entry_text(self, entry: HumanEntry) -> str:
        path = self.storage.entry_path(entry)
        if not path.exists():
            return ""
        try:
            content = self.storage.read_text(path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Load failed", str(exc))
            return ""
        return content.lstrip("\n")

    def save_current_entry(self) -> None:
        entry = self.current_entry()
        if entry is None or entry.entry_type != EntryType.TEXT:
            return
        text = self.current_editor_text()
        if text == self.last_saved_text:
            return
        try:
            self.storage.save_entry(entry, text)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self.last_saved_text = text
        self.update_preview(entry.id, text)

    def autosave_current_text(self) -> None:
        entry = self.current_entry()
        if entry is None or entry.entry_type != EntryType.TEXT:
            return
        text = self.current_editor_text()
        if text == self.last_saved_text:
            return
        try:
            self.storage.save_entry(entry, text)
        except RuntimeError:
            # Keep autosave silent; explicit save surfaces errors to users.
            return
        self.last_saved_text = text
        self.update_preview(entry.id, text)

    def update_preview(self, entry_id, content: str) -> None:
        preview = self.storage.preview_text_from_content(content)
        updated_entry: Optional[HumanEntry] = None
        for index, entry in enumerate(self.entries):
            if entry.id == entry_id:
                self.entries[index] = replace(entry, preview_text=preview)
                updated_entry = self.entries[index]
                break

        if updated_entry is None:
            return

        # Do not rebuild the whole sidebar during typing; that can retrigger
        # selection callbacks and reset the editor cursor to the start.
        for row in range(self.entry_list.count()):
            item = self.entry_list.item(row)
            if item is None:
                continue
            if str(item.data(Qt.UserRole)) == str(entry_id):
                item.setText(f"{updated_entry.preview_text or ' '}\n{updated_entry.date_label}")
                break

    def on_text_changed(self) -> None:
        self.current_text = self.current_editor_text()
        if not self.current_text:
            self.placeholder_text = self.random_placeholder()
        if self.markdown_rendered_view_enabled and not self.showing_video:
            self.markdown_render_timer.start()
        self.autosave_current_text()

    def random_placeholder(self) -> str:
        import random

        placeholder = random.choice(self.placeholder_options)
        self.plain_editor.setPlaceholderText(placeholder)
        return placeholder

    def toggle_sidebar(self) -> None:
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def open_documents_folder(self) -> None:
        self.storage.root.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.storage.root)))

    def create_new_entry(self) -> None:
        entry = HumanEntry.create_new()
        self.entries.insert(0, entry)
        try:
            self.storage.write_text(self.storage.entry_path(entry), "")
        except RuntimeError as exc:
            QMessageBox.warning(self, "Create entry failed", str(exc))
            self.entries = [item for item in self.entries if item.id != entry.id]
            return
        self.populate_sidebar()
        self.select_entry(entry)
        default_md = Path(__file__).with_name("default.md")
        if default_md.exists():
            content = default_md.read_text(encoding="utf-8")
            self.plain_editor.setPlainText(content)
        else:
            self.plain_editor.setPlainText("")
        self.last_saved_text = ""
        self.save_current_entry()

    def on_entry_selected(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        if current is None:
            return
        entry_id = current.data(Qt.UserRole)
        selected = next((entry for entry in self.entries if str(entry.id) == str(entry_id)), None)
        if selected is not None:
            if self.selected_entry_id == str(selected.id):
                return
            self.select_entry(selected)

    def cycle_font_size(self) -> None:
        sizes = [16, 18, 20, 22, 24, 26]
        try:
            index = sizes.index(self.font_size)
        except ValueError:
            index = 1
        self.font_size = sizes[(index + 1) % len(sizes)]
        self.settings.setValue("fontSize", self.font_size)
        self.apply_editor_font()

    def set_font_family(self, family: str) -> None:
        self.current_font_family = family
        self.settings.setValue("fontFamily", family)
        self.apply_editor_font()

    def random_font(self) -> None:
        import random

        self.set_font_family(random.choice(["Lato", "Arial", "Sans Serif", "Times New Roman"]))

    def toggle_timer(self) -> None:
        if self.timer_running:
            self.timer.stop()
            self.timer_running = False
        else:
            if self.time_remaining <= 0:
                self.time_remaining = 900
                self.settings.setValue("timeRemaining", self.time_remaining)
            self.timer_running = True
            self.timer.start()
        self.refresh_timer_label()

    def show_timer_context_menu(self, position=None) -> None:
        if position is None:
            position = self.timer_button.rect().center()
        menu = QMenu(self)
        change_action = menu.addAction("Change time...")
        reset_action = menu.addAction("Reset to 15:00")
        selected_action = menu.exec(self.timer_button.mapToGlobal(position))
        if selected_action == change_action:
            self.prompt_timer_duration()
        elif selected_action == reset_action:
            self.reset_timer_duration()

    def prompt_timer_duration(self) -> None:
        current_minutes = max(1, self.time_remaining // 60)
        minutes, accepted = QInputDialog.getInt(
            self,
            "Change Timer",
            "Set timer minutes:",
            value=current_minutes,
            minValue=1,
            maxValue=180,
            step=1,
        )
        if accepted:
            self.set_timer_duration_minutes(minutes)

    def set_timer_duration_minutes(self, minutes: int) -> None:
        self.timer.stop()
        self.timer_running = False
        self.time_remaining = max(1, minutes) * 60
        self.settings.setValue("timeRemaining", self.time_remaining)
        self.refresh_timer_label()

    def reset_timer_duration(self) -> None:
        self.set_timer_duration_minutes(15)

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is self.plain_editor
            and event.type() == QEvent.KeyPress
            and self.backspace_disabled
            and event.key() in (Qt.Key_Backspace, Qt.Key_Delete)
        ):
            return True

        if hasattr(self, "timer_button") and watched is self.timer_button and event.type() == QEvent.MouseButtonPress and event.button() == Qt.RightButton:
            self.show_timer_context_menu(event.position().toPoint())
            return True
        if hasattr(self, "timer_button") and watched is self.timer_button and event.type() == QEvent.ContextMenu:
            self.show_timer_context_menu(event.pos())
            return True
        if hasattr(self, "markdown_button") and watched is self.markdown_button and event.type() == QEvent.ContextMenu:
            self.show_markdown_context_menu(event.pos())
            return True
        return super().eventFilter(watched, event)

    def tick_timer(self) -> None:
        if self.time_remaining <= 0:
            self.timer.stop()
            self.timer_running = False
            self.time_remaining = 900
            self.settings.setValue("timeRemaining", self.time_remaining)
            self.refresh_timer_label()
            return
        self.time_remaining -= 1
        self.settings.setValue("timeRemaining", self.time_remaining)
        self.refresh_timer_label()

    def toggle_backspace(self) -> None:
        self.backspace_disabled = not self.backspace_disabled
        self.settings.setValue("backspaceDisabled", self.backspace_disabled)
        self.refresh_bottom_buttons()

    def toggle_markdown(self) -> None:
        self.markdown_enabled = not self.markdown_enabled
        self.settings.setValue("markdownEnabled", self.markdown_enabled)
        self.apply_markdown_mode()
        self.refresh_bottom_buttons()

    def apply_markdown_mode(self) -> None:
        if self.showing_video:
            self.editor_stack.setCurrentWidget(self.video_placeholder)
            return
        if self.markdown_rendered_view_enabled:
            self.editor_stack.setCurrentWidget(self.markdown_rendered_view)
        else:
            self.editor_stack.setCurrentWidget(self.plain_editor)
        if self.markdown_enabled:
            if self.markdown_highlighter is None:
                self.markdown_highlighter = MarkdownHighlighter(
                    self.plain_editor.document(),
                    dark_mode=(self.color_scheme == "dark"),
                    base_font_size=self.font_size,
                )
            else:
                self.markdown_highlighter.setDocument(self.plain_editor.document())
                self.markdown_highlighter.set_dark_mode(self.color_scheme == "dark")
                self.markdown_highlighter.set_base_font_size(self.font_size)
            self.markdown_highlighter.rehighlight()
        else:
            if self.markdown_highlighter is not None:
                self.markdown_highlighter.setDocument(None)
                self.markdown_highlighter = None
        if self.markdown_rendered_view_enabled:
            self.refresh_rendered_markdown_view()

    def current_editor_text(self) -> str:
        return self.plain_editor.toPlainText()

    def refresh_rendered_markdown_view(self) -> None:
        if self.showing_video or not self.markdown_rendered_view_enabled:
            return
        # Keep rendering permissive; if parsing fails, show plain text.
        try:
            self.markdown_rendered_view.setMarkdown(self.plain_editor.toPlainText())
        except Exception:
            self.markdown_rendered_view.setPlainText(self.plain_editor.toPlainText())

    def show_markdown_context_menu(self, position=None) -> None:
        if position is None:
            position = self.markdown_button.rect().center()
        menu = QMenu(self)
        rendered = menu.addAction("Rendered view (no symbols)")
        rendered.setCheckable(True)
        rendered.setChecked(self.markdown_rendered_view_enabled)
        selected = menu.exec(self.markdown_button.mapToGlobal(position))
        if selected == rendered:
            self.markdown_rendered_view_enabled = not self.markdown_rendered_view_enabled
            self.settings.setValue("markdownRenderedViewEnabled", self.markdown_rendered_view_enabled)
            self.apply_markdown_mode()
            self.refresh_bottom_buttons()

    def toggle_theme(self) -> None:
        self.color_scheme = "light" if self.color_scheme == "dark" else "dark"
        self.settings.setValue("colorScheme", self.color_scheme)
        self.apply_theme()

    def toggle_fullscreen(self) -> None:
        self.fullscreen_enabled = not self.fullscreen_enabled
        if self.fullscreen_enabled:
            self.sidebar_was_visible = self.sidebar.isVisible()
            self.sidebar.setVisible(False)
            self.bottom_bar.setVisible(False)
            self.showFullScreen()
        else:
            self.sidebar.setVisible(self.sidebar_was_visible)
            self.bottom_bar.setVisible(True)
            self.showNormal()

    def open_chat_menu(self) -> None:
        content = self.current_chat_source_text()
        prompt = f"{AI_CHAT_PROMPT}\n\n{content}"
        if len(prompt) > 6000:
            self.copy_prompt_to_clipboard()
            QMessageBox.information(
                self,
                "Prompt copied",
                "Your entry is too long for direct URL handoff.\n"
                "The full prompt is copied to clipboard. Paste it into ChatGPT or Claude.",
            )
            return
        # Browser handoff only for Ubuntu parity.
        if self.ask_chat_provider() == "Claude":
            webbrowser.open(f"https://claude.ai/new?q={self.encode_prompt(CLAUDE_PROMPT + '\n\n' + content)}")
        else:
            webbrowser.open(f"https://chat.openai.com/?prompt={self.encode_prompt(prompt)}")

    def ask_chat_provider(self) -> str:
        return "ChatGPT"

    def encode_prompt(self, prompt: str) -> str:
        from urllib.parse import quote

        return quote(prompt, safe="")

    def copy_prompt_to_clipboard(self) -> None:
        prompt = f"{AI_CHAT_PROMPT}\n\n{self.current_chat_source_text()}"
        QApplication.clipboard().setText(prompt)
        self.did_copy_prompt = True

    def copy_video_transcript(self) -> None:
        entry = self.current_entry()
        if entry is None or entry.entry_type != EntryType.VIDEO or not entry.video_filename:
            return
        transcript = self.storage.read_transcript(entry.video_filename)
        if not transcript:
            return
        QApplication.clipboard().setText(transcript)
        self.did_copy_transcript = True

    def current_chat_source_text(self) -> str:
        entry = self.current_entry()
        if entry and entry.entry_type == EntryType.VIDEO and entry.video_filename:
            transcript = self.storage.read_transcript(entry.video_filename)
            if transcript:
                return transcript.strip()
        return self.current_editor_text().strip()

    def export_selected_entry_pdf(self) -> None:
        entry = self.current_entry()
        if entry is None:
            return
        if entry.entry_type != EntryType.TEXT:
            QMessageBox.information(self, "Export unavailable", "Video entries are not exported yet.")
            return
        self.save_current_entry()
        content = self.read_entry_text(entry)
        suggested = extract_title_from_content(content, entry.date_label) + ".pdf"
        file_path, _ = QFileDialog.getSaveFileName(self, "Export as PDF", str(self.storage.root / suggested), "PDF Files (*.pdf)")
        if not file_path:
            return
        try:
            export_text_to_pdf(content, Path(file_path), font_name=self.current_font_family, font_size=self.font_size)
        except Exception as exc:
            QMessageBox.warning(self, "Export failed", f"Could not export PDF: {exc}")

    def start_video_recording_placeholder(self) -> None:
        QMessageBox.information(self, "Video recording", "Video recording is being implemented in the next slice.")

    def read_entry_text_for_export(self, entry: HumanEntry) -> str:
        return self.read_entry_text(entry)

    def delete_selected_entry(self) -> None:
        entry = self.current_entry()
        if entry is None:
            return
        try:
            self.storage.delete_entry(entry)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Delete failed", str(exc))
            return
        self.entries = [item for item in self.entries if item.id != entry.id]
        self.populate_sidebar()
        if self.entries:
            self.select_entry(self.entries[0])
        else:
            self.create_new_entry()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.backspace_disabled and event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            event.accept()
            return
        if event.key() == Qt.Key_Escape and self.fullscreen_enabled:
            self.toggle_fullscreen()
            event.accept()
            return
        if event.key() == Qt.Key_F11:
            self.toggle_fullscreen()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.save_current_entry()
        self.settings.setValue("timeRemaining", self.time_remaining)
        self.settings.setValue("backspaceDisabled", self.backspace_disabled)
        self.settings.setValue("fontFamily", self.current_font_family)
        self.settings.setValue("fontSize", self.font_size)
        self.settings.setValue("colorScheme", self.color_scheme)
        self.settings.setValue("markdownEnabled", self.markdown_enabled)
        super().closeEvent(event)

    def on_media_error(self, error, error_string: str) -> None:
        if error_string:
            self.video_title_label.setText(f"Video playback error\n{error_string}")
