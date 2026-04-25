from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime

ENTRY_TIMESTAMP_FORMAT = "%Y-%m-%d-%H-%M-%S"
DISPLAY_DATE_FORMAT = "%b %-d"


class EntryType(str, Enum):
    TEXT = "text"
    VIDEO = "video"


@dataclass(slots=True)
class HumanEntry:
    id: UUID
    date_label: str
    filename: str
    preview_text: str
    entry_type: EntryType
    video_filename: Optional[str] = None

    @property
    def base_name(self) -> str:
        return self.filename.removesuffix(".md")

    @property
    def video_path_name(self) -> Optional[str]:
        return self.video_filename

    @classmethod
    def create_new(cls, now: Optional[datetime] = None) -> "HumanEntry":
        now = now or datetime.now()
        entry_id = uuid4()
        timestamp = now.strftime(ENTRY_TIMESTAMP_FORMAT)
        display_date = now.strftime(DISPLAY_DATE_FORMAT).replace(" 0", " ")
        return cls(
            id=entry_id,
            date_label=display_date,
            filename=f"[{entry_id}]-[{timestamp}].md",
            preview_text="",
            entry_type=EntryType.TEXT,
            video_filename=None,
        )

    @classmethod
    def create_video_entry(cls, now: Optional[datetime] = None) -> "HumanEntry":
        now = now or datetime.now()
        entry_id = uuid4()
        timestamp = now.strftime(ENTRY_TIMESTAMP_FORMAT)
        display_date = now.strftime(DISPLAY_DATE_FORMAT).replace(" 0", " ")
        video_filename = f"[{entry_id}]-[{timestamp}].mov"
        return cls(
            id=entry_id,
            date_label=display_date,
            filename=f"[{entry_id}]-[{timestamp}].md",
            preview_text="Video Entry",
            entry_type=EntryType.VIDEO,
            video_filename=video_filename,
        )
