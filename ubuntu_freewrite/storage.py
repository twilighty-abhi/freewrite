from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from uuid import UUID

from .models import ENTRY_TIMESTAMP_FORMAT, EntryType, HumanEntry

CANONICAL_ENTRY_PATTERN = re.compile(r"^\[(?P<uuid>[0-9A-Fa-f-]{36})\]-\[(?P<timestamp>\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})\]\.md$")


@dataclass(slots=True)
class LoadedEntry:
    entry: HumanEntry
    file_path: Path
    content: str


class StorageService:
    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or Path.home() / "Documents" / "Freewrite"
        self.videos_root = self.root / "Videos"
        self.root.mkdir(parents=True, exist_ok=True)
        self.videos_root.mkdir(parents=True, exist_ok=True)

    def entry_path(self, entry: HumanEntry) -> Path:
        return self.root / entry.filename

    def video_entry_dir(self, video_filename: str) -> Path:
        return self.videos_root / Path(video_filename).stem

    def managed_video_path(self, video_filename: str) -> Path:
        return self.video_entry_dir(video_filename) / video_filename

    def thumbnail_path(self, video_filename: str) -> Path:
        return self.video_entry_dir(video_filename) / "thumbnail.jpg"

    def transcript_path(self, video_filename: str) -> Path:
        return self.video_entry_dir(video_filename) / "transcript.md"

    def ensure_video_entry_dir(self, video_filename: str) -> Path:
        directory = self.video_entry_dir(video_filename)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def parse_canonical_entry_filename(self, filename: str) -> Optional[tuple[UUID, str]]:
        match = CANONICAL_ENTRY_PATTERN.match(filename)
        if not match:
            return None
        try:
            return UUID(match.group("uuid")), match.group("timestamp")
        except ValueError:
            return None

    def is_canonical_entry_filename(self, filename: str) -> bool:
        return self.parse_canonical_entry_filename(filename) is not None

    def video_candidates(self, video_filename: str) -> list[Path]:
        return [
            self.managed_video_path(video_filename),
            self.videos_root / video_filename,
            self.root / video_filename,
        ]

    def load_video_path(self, video_filename: str) -> Optional[Path]:
        for candidate in self.video_candidates(video_filename):
            if candidate.exists():
                return candidate
        return None

    def has_video_asset(self, video_filename: str) -> bool:
        return self.load_video_path(video_filename) is not None

    def read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"Failed to read {path}: {exc}") from exc

    def write_text(self, path: Path, content: str) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"Failed to write {path}: {exc}") from exc

    def remove_file(self, path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except OSError as exc:
            raise RuntimeError(f"Failed to remove file {path}: {exc}") from exc

    def remove_tree(self, path: Path) -> None:
        try:
            if path.exists():
                for child in path.iterdir():
                    if child.is_dir():
                        self.remove_tree(child)
                    else:
                        child.unlink()
                path.rmdir()
        except OSError as exc:
            raise RuntimeError(f"Failed to remove directory {path}: {exc}") from exc

    def scan_entries(self) -> list[LoadedEntry]:
        loaded: list[LoadedEntry] = []
        for file_path in self.root.glob("*.md"):
            parsed = self.parse_canonical_entry_filename(file_path.name)
            if parsed is None:
                continue
            entry_id, timestamp = parsed
            content = self.read_text(file_path)
            preview = self.preview_text_from_content(content)
            video_filename = f"[{entry_id}]-[{timestamp}].mov"
            has_video = self.has_video_asset(video_filename)
            display_date = self.display_date_from_timestamp(timestamp)
            entry = HumanEntry(
                id=entry_id,
                date_label=display_date,
                filename=file_path.name,
                preview_text=self.preview_text_for_entry(content, video_filename if has_video else None),
                entry_type=EntryType.VIDEO if has_video else EntryType.TEXT,
                video_filename=video_filename if has_video else None,
            )
            loaded.append(LoadedEntry(entry=entry, file_path=file_path, content=content))
        loaded.sort(key=lambda item: self.sort_key(item.entry.filename), reverse=True)
        return loaded

    def sort_key(self, filename: str) -> tuple[str, str]:
        parsed = self.parse_canonical_entry_filename(filename)
        if parsed is None:
            return ("", "")
        _, timestamp = parsed
        return timestamp, filename

    def display_date_from_timestamp(self, timestamp: str) -> str:
        from datetime import datetime

        dt = datetime.strptime(timestamp, ENTRY_TIMESTAMP_FORMAT)
        return f"{dt.strftime('%b')} {dt.day}"

    def preview_text_from_content(self, content: str) -> str:
        normalized = re.sub(r"\s+", " ", content.replace("\n", " ")).strip()
        if not normalized:
            return ""
        if len(normalized) > 30:
            return normalized[:30].rstrip() + "..."
        return normalized

    def preview_text_for_entry(self, content: str, video_filename: Optional[str]) -> str:
        if video_filename is not None:
            transcript = self.read_transcript(video_filename)
            if transcript:
                return self.preview_text_from_content(transcript)
            return "Video Entry"
        return self.preview_text_from_content(content)

    def read_transcript(self, video_filename: str) -> Optional[str]:
        transcript_path = self.transcript_path(video_filename)
        if not transcript_path.exists():
            return None
        transcript = self.read_text(transcript_path).strip()
        return transcript or None

    def delete_entry(self, entry: HumanEntry) -> None:
        self.remove_file(self.entry_path(entry))
        if entry.video_filename:
            self.delete_video_assets(entry.video_filename)

    def delete_video_assets(self, video_filename: str) -> None:
        managed_dir = self.video_entry_dir(video_filename)
        for candidate in [
            managed_dir / video_filename,
            managed_dir / "thumbnail.jpg",
            managed_dir / "transcript.md",
            self.videos_root / video_filename,
            self.root / video_filename,
        ]:
            self.remove_file(candidate)
        if managed_dir.exists():
            self.remove_tree(managed_dir)

    def create_text_entry(self, content: str = "") -> HumanEntry:
        entry = HumanEntry.create_new()
        self.write_text(self.entry_path(entry), content)
        return entry

    def save_entry(self, entry: HumanEntry, content: str) -> None:
        self.write_text(self.entry_path(entry), content)

    def save_video_entry_metadata(self, entry: HumanEntry) -> None:
        self.write_text(self.entry_path(entry), "Video Entry")

    def migrate_existing_video_entry(self, entry: HumanEntry, video_source: Path, transcript: Optional[str] = None) -> None:
        if entry.video_filename is None:
            raise ValueError("video entry requires video_filename")
        target_dir = self.ensure_video_entry_dir(entry.video_filename)
        target_video = target_dir / entry.video_filename
        if target_video.exists():
            target_video.unlink()
        target_video.write_bytes(video_source.read_bytes())
        if transcript and transcript.strip():
            self.write_text(self.transcript_path(entry.video_filename), transcript.strip())
        self.save_video_entry_metadata(entry)
