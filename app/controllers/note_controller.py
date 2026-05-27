from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.note_service import NoteService


class NoteController:
    def __init__(self, note_service: NoteService) -> None:
        self.note_service = note_service

    def create_note(
        self,
        workspace_root: str | Path,
        title: str,
        markdown_content: str | None = None,
    ) -> dict[str, object]:
        return self.note_service.create_note(workspace_root, title, markdown_content)

    def open_note(self, workspace_root: str | Path, note_path: str | Path) -> dict[str, object]:
        return self.note_service.open_note(workspace_root, note_path)

    def save_note(
        self,
        workspace_root: str | Path,
        payload: dict[str, Any],
    ) -> dict[str, object]:
        return self.note_service.save_note(workspace_root, payload)

    def delete_note(self, workspace_root: str | Path, note_path: str | Path) -> dict[str, object]:
        return self.note_service.delete_note(workspace_root, note_path)

    def list_notes(self, workspace_root: str | Path) -> dict[str, object]:
        return self.note_service.list_notes(workspace_root)
