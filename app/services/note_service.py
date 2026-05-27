from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.services.workspace_service import WorkspaceService


class NoteService:
    def __init__(self, workspace_service: WorkspaceService) -> None:
        self.workspace_service = workspace_service

    def create_note(
        self,
        workspace_root: str | Path,
        title: str,
        markdown_content: str | None = None,
    ) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        note_title = title.strip() or "Untitled"
        note_path = self._build_unique_note_path(workspace_context.notes_path, note_title)
        content = markdown_content if markdown_content is not None else f"# {note_title}\n\n"

        try:
            note_path.write_text(content, encoding="utf-8")
        except OSError as error:
            return self._failure(f"Failed to create note: {error}")

        return self._success(
            "Note created successfully.",
            note=self._build_note_data(note_path, content, title=note_title),
        )

    def open_note(self, workspace_root: str | Path, note_path: str | Path) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        resolved_note = self._resolve_note_path(
            workspace_context.notes_path,
            note_path,
            require_existing=True,
        )
        if resolved_note is None:
            return self._failure("Note path must point to a Markdown file inside workspace/notes.")

        try:
            content = resolved_note.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return self._failure("Note is not a UTF-8 Markdown file.")
        except OSError as error:
            return self._failure(f"Failed to open note: {error}")

        return self._success(
            "Note opened successfully.",
            note=self._build_note_data(
                resolved_note,
                content,
                title=self._derive_title(content, resolved_note),
            ),
        )

    def save_note(self, workspace_root: str | Path, payload: dict[str, Any]) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        note_payload = dict(payload or {})
        content = str(note_payload.get("markdown_content") or "")
        title = str(note_payload.get("title") or "").strip() or self._derive_title(content, None)
        current_path_value = note_payload.get("file_path")

        if current_path_value:
            current_path = self._resolve_note_path(
                workspace_context.notes_path,
                current_path_value,
                require_existing=False,
            )
            if current_path is None:
                return self._failure(
                    "Note path must stay inside workspace/notes and use the .md extension."
                )
        else:
            current_path = self._build_unique_note_path(workspace_context.notes_path, title)

        target_path = self._target_note_path_for_title(current_path, title)
        renamed = current_path.resolve() != target_path.resolve()

        try:
            target_path.write_text(content, encoding="utf-8")
            if renamed and current_path.exists():
                current_path.unlink()
        except OSError as error:
            return self._failure(f"Failed to save note: {error}")

        version = int(note_payload.get("version") or 0) + 1
        return self._success(
            "Note saved successfully.",
            note=self._build_note_data(
                target_path,
                content,
                title=title,
                cursor_position=int(note_payload.get("cursor_position") or 0),
                version=version,
            ),
            renamed=renamed,
        )

    def delete_note(self, workspace_root: str | Path, note_path: str | Path) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        resolved_note = self._resolve_note_path(
            workspace_context.notes_path,
            note_path,
            require_existing=True,
        )
        if resolved_note is None:
            return self._failure("Note path must point to an existing Markdown file inside workspace/notes.")

        try:
            resolved_note.unlink()
        except OSError as error:
            return self._failure(f"Failed to delete note: {error}")

        return self._success(
            "Note deleted successfully.",
            note={
                "note_id": resolved_note.stem,
                "title": resolved_note.stem,
                "file_path": str(resolved_note),
            },
        )

    def list_notes(self, workspace_root: str | Path) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        notes = []
        for note_path in sorted(workspace_context.notes_path.rglob("*.md"), key=lambda item: item.name.lower()):
            try:
                content = note_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                content = ""
            notes.append(
                {
                    "note_id": note_path.stem,
                    "title": self._derive_title(content, note_path),
                    "file_path": str(note_path),
                    "relative_path": str(note_path.relative_to(workspace_context.notes_path)),
                }
            )

        return self._success("Notes listed successfully.", notes=tuple(notes))

    def _resolve_note_path(
        self,
        notes_dir: Path,
        note_path: str | Path,
        *,
        require_existing: bool,
    ) -> Path | None:
        candidate = Path(note_path)
        if not candidate.is_absolute():
            candidate = notes_dir / candidate

        resolved_notes_dir = notes_dir.resolve()
        resolved_note = candidate.resolve()

        try:
            resolved_note.relative_to(resolved_notes_dir)
        except ValueError:
            return None

        if resolved_note.suffix.lower() != ".md":
            return None

        if require_existing and (not resolved_note.exists() or not resolved_note.is_file()):
            return None

        return resolved_note

    def _build_unique_note_path(self, notes_dir: Path, title: str) -> Path:
        safe_title = self._safe_filename(title)
        candidate = notes_dir / f"{safe_title}.md"
        counter = 2
        while candidate.exists():
            candidate = notes_dir / f"{safe_title}-{counter}.md"
            counter += 1
        return candidate

    def _target_note_path_for_title(self, current_path: Path, title: str) -> Path:
        safe_title = self._safe_filename(title)
        if not safe_title or safe_title == current_path.stem:
            return current_path

        candidate = current_path.with_name(f"{safe_title}.md")
        if not candidate.exists() or candidate.resolve() == current_path.resolve():
            return candidate

        counter = 2
        while True:
            next_candidate = current_path.with_name(f"{safe_title}-{counter}.md")
            if not next_candidate.exists() or next_candidate.resolve() == current_path.resolve():
                return next_candidate
            counter += 1

    def _safe_filename(self, title: str) -> str:
        cleaned = "".join(char for char in title.strip() if char not in r'\/:*?"<>|')
        cleaned = "-".join(cleaned.split())
        return cleaned or "Untitled"

    def _derive_title(self, content: str, note_path: Path | None) -> str:
        for line in content.splitlines():
            match = re.match(r"^#\s+(.+?)\s*$", line)
            if match:
                return match.group(1).strip()

        for line in content.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:80]

        if note_path is not None:
            return note_path.stem
        return "Untitled"

    def _build_note_data(
        self,
        note_path: Path,
        content: str,
        *,
        title: str,
        cursor_position: int = 0,
        version: int = 1,
    ) -> dict[str, object]:
        return {
            "note_id": note_path.stem,
            "title": title,
            "file_path": str(note_path),
            "markdown_content": content,
            "cursor_position": max(0, cursor_position),
            "file_mtime": note_path.stat().st_mtime,
            "version": version,
        }

    def _success(self, message: str, **data: object) -> dict[str, object]:
        return {
            "success": True,
            "message": message,
            "data": data,
        }

    def _failure(self, message: str, **data: object) -> dict[str, object]:
        return {
            "success": False,
            "message": message,
            "data": data,
        }
