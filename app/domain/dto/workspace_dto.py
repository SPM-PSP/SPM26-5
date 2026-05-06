from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkspaceContextDTO:
    root_path: Path
    agni_dir: Path
    database_path: Path
    settings_path: Path
    notes_path: Path
    references_path: Path
    attachments_path: Path
    cache_path: Path
    inbox_note_path: Path
    created_paths: tuple[Path, ...] = field(default_factory=tuple)

    def as_payload(self) -> dict[str, object]:
        return {
            "root_path": str(self.root_path),
            "agni_dir": str(self.agni_dir),
            "database_path": str(self.database_path),
            "settings_path": str(self.settings_path),
            "notes_path": str(self.notes_path),
            "references_path": str(self.references_path),
            "attachments_path": str(self.attachments_path),
            "cache_path": str(self.cache_path),
            "inbox_note_path": str(self.inbox_note_path),
            "created_paths": [str(path) for path in self.created_paths],
        }
