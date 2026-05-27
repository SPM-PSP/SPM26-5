from __future__ import annotations

import hashlib
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

        self._sync_note_record(workspace_context, note_path, content, note_title)

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

        self._sync_note_record(workspace_context, target_path, content, title)
        if renamed:
            self._delete_note_record(workspace_context, current_path.stem)

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

        self._delete_note_record(workspace_context, resolved_note.stem)

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
        planets_by_note_id = self._load_note_planets(workspace_context)
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
                    "planet": planets_by_note_id.get(note_path.stem),
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

    def _sync_note_record(
        self,
        workspace_context,
        note_path: Path,
        content: str,
        title: str,
    ) -> None:
        relative_path = str(note_path.relative_to(workspace_context.notes_path))
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        links = self._extract_note_links(content)

        with self.workspace_service.connect_workspace_database(workspace_context) as connection:
            existing_planet_row = connection.execute(
                """
                SELECT planet
                FROM object_planets
                WHERE object_kind = 'note' AND object_key = ?
                """,
                (note_path.stem,),
            ).fetchone()
            planet = (
                str(existing_planet_row["planet"])
                if existing_planet_row is not None and existing_planet_row["planet"] is not None
                else self._infer_planet_from_path(note_path)
            )

            connection.execute(
                """
                INSERT INTO notes(note_id, relative_path, title, content, planet, content_hash, updated_at, file_mtime)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)
                ON CONFLICT(note_id) DO UPDATE SET
                    relative_path = excluded.relative_path,
                    title = excluded.title,
                    content = excluded.content,
                    planet = excluded.planet,
                    content_hash = excluded.content_hash,
                    updated_at = excluded.updated_at,
                    file_mtime = excluded.file_mtime
                """,
                (
                    note_path.stem,
                    relative_path,
                    title,
                    content,
                    planet,
                    content_hash,
                    note_path.stat().st_mtime,
                ),
            )
            connection.execute(
                """
                INSERT INTO object_planets(object_kind, object_key, planet, updated_at)
                VALUES ('note', ?, ?, datetime('now'))
                ON CONFLICT(object_kind, object_key) DO UPDATE SET
                    planet = excluded.planet,
                    updated_at = excluded.updated_at
                """,
                (note_path.stem, planet),
            )
            connection.execute(
                "DELETE FROM notes_fts WHERE note_id = ?",
                (note_path.stem,),
            )
            connection.execute(
                """
                INSERT INTO notes_fts(note_id, relative_path, title, content)
                VALUES (?, ?, ?, ?)
                """,
                (note_path.stem, relative_path, title, content),
            )
            connection.execute(
                "DELETE FROM note_links WHERE source_note_id = ?",
                (note_path.stem,),
            )
            if links:
                connection.executemany(
                    """
                    INSERT INTO note_links(source_note_id, target_title, target_heading, alias, raw_link)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            note_path.stem,
                            link["target_title"],
                            link["target_heading"],
                            link["alias"],
                            link["raw"],
                        )
                        for link in links
                    ],
                )
            connection.commit()

    def _delete_note_record(self, workspace_context, note_id: str) -> None:
        with self.workspace_service.connect_workspace_database(workspace_context) as connection:
            connection.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))
            connection.execute("DELETE FROM notes_fts WHERE note_id = ?", (note_id,))
            connection.execute(
                "DELETE FROM object_planets WHERE object_kind = 'note' AND object_key = ?",
                (note_id,),
            )
            connection.commit()

    def _extract_note_links(self, content: str) -> list[dict[str, str | None]]:
        links: list[dict[str, str | None]] = []
        pattern = re.compile(
            r"\[\[(?P<title>[^\]#|]+?)(?:#(?P<heading>[^\]|]+))?(?:\|(?P<alias>[^\]]+))?\]\]"
        )
        for match in pattern.finditer(content):
            links.append(
                {
                    "raw": match.group(0),
                    "target_title": match.group("title").strip(),
                    "target_heading": match.group("heading").strip() if match.group("heading") else None,
                    "alias": match.group("alias").strip() if match.group("alias") else None,
                }
            )
        return links

    def _infer_planet_from_path(self, note_path: Path) -> str:
        lowered = str(note_path).casefold()
        if "inbox" in lowered:
            return "Inbox"
        if "reading" in lowered or "paper" in lowered or "pdf" in lowered:
            return "Reading"
        if "research" in lowered or "project" in lowered:
            return "Research"
        return "Unassigned"

    def _load_note_planets(self, workspace_context) -> dict[str, str]:
        with self.workspace_service.connect_workspace_database(workspace_context) as connection:
            rows = connection.execute(
                """
                SELECT object_key, planet
                FROM object_planets
                WHERE object_kind = 'note'
                """
            ).fetchall()
        return {
            str(row["object_key"]): str(row["planet"])
            for row in rows
            if row["planet"] is not None
        }
