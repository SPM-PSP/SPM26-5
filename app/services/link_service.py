from __future__ import annotations

import re
from pathlib import Path

from app.services.workspace_service import WorkspaceService


WIKILINK_PATTERN = re.compile(
    r"\[\[(?P<title>[^\]#|]+?)(?:#(?P<heading>[^\]|]+))?(?:\|(?P<alias>[^\]]+))?\]\]"
)


class LinkService:
    def __init__(self, workspace_service: WorkspaceService) -> None:
        self.workspace_service = workspace_service

    def list_note_links(self, workspace_root: str | Path, note_path: str | Path) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        notes_dir = workspace_context.notes_path
        resolved_note = self._resolve_note_path(notes_dir, note_path)
        if resolved_note is None:
            return self._failure("Note path must point to a Markdown file inside workspace/notes.")

        try:
            text = resolved_note.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return self._failure("Note is not a UTF-8 Markdown file.")
        except OSError as error:
            return self._failure(f"Failed to read note links: {error}")

        note_id = resolved_note.stem
        with self.workspace_service.connect_workspace_database(workspace_context) as connection:
            rows = connection.execute(
                """
                SELECT raw_link, target_title, target_heading, alias
                FROM note_links
                WHERE source_note_id = ?
                ORDER BY id ASC
                """,
                (note_id,),
            ).fetchall()
        links = (
            tuple(
                {
                    "raw": str(row["raw_link"]),
                    "target_title": str(row["target_title"]),
                    "target_heading": str(row["target_heading"]) if row["target_heading"] is not None else None,
                    "alias": str(row["alias"]) if row["alias"] is not None else None,
                }
                for row in rows
            )
            if rows
            else tuple(self._parse_wikilinks(text))
        )
        return self._success(
            "Note links listed successfully.",
            note={
                "title": self._derive_note_title(text, resolved_note),
                "file_path": str(resolved_note),
            },
            links=links,
        )

    def find_backlinks(
        self,
        workspace_root: str | Path,
        target_title: str,
        current_note_path: str | Path | None = None,
    ) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        notes_dir = workspace_context.notes_path
        normalized_title = self._normalize_title(target_title)
        current_path = (
            self._resolve_note_path(notes_dir, current_note_path)
            if current_note_path is not None
            else None
        )

        backlinks: list[dict[str, object]] = []
        with self.workspace_service.connect_workspace_database(workspace_context) as connection:
            note_rows = connection.execute(
                """
                SELECT notes.note_id, notes.relative_path, notes.title, notes.content
                FROM note_links
                JOIN notes ON notes.note_id = note_links.source_note_id
                WHERE lower(trim(note_links.target_title)) = ?
                GROUP BY notes.note_id, notes.relative_path, notes.title, notes.content
                ORDER BY notes.title COLLATE NOCASE ASC
                """,
                (normalized_title,),
            ).fetchall()

            for note_row in note_rows:
                note_path = notes_dir / str(note_row["relative_path"])
                if current_path is not None and note_path.resolve() == current_path.resolve():
                    continue
                link_rows = connection.execute(
                    """
                    SELECT raw_link, target_title, target_heading, alias
                    FROM note_links
                    WHERE source_note_id = ?
                      AND lower(trim(target_title)) = ?
                    ORDER BY id ASC
                    """,
                    (str(note_row["note_id"]), normalized_title),
                ).fetchall()
                matched_links = tuple(
                    {
                        "raw": str(row["raw_link"]),
                        "target_title": str(row["target_title"]),
                        "target_heading": str(row["target_heading"]) if row["target_heading"] is not None else None,
                        "alias": str(row["alias"]) if row["alias"] is not None else None,
                    }
                    for row in link_rows
                )
                backlinks.append(
                    {
                        "source_title": str(note_row["title"] or note_path.stem),
                        "file_path": str(note_path),
                        "context": self._build_backlink_context(str(note_row["content"] or ""), list(matched_links)),
                        "matched_links": matched_links,
                    }
                )

        return self._success(
            "Backlinks listed successfully.",
            target_title=target_title,
            backlinks=tuple(backlinks),
        )

    def _parse_wikilinks(self, text: str) -> list[dict[str, object]]:
        links: list[dict[str, object]] = []
        for match in WIKILINK_PATTERN.finditer(text):
            title = match.group("title").strip()
            heading = match.group("heading")
            alias = match.group("alias")
            links.append(
                {
                    "raw": match.group(0),
                    "target_title": title,
                    "target_heading": heading.strip() if heading else None,
                    "alias": alias.strip() if alias else None,
                }
            )
        return links

    def _resolve_note_path(self, notes_dir: Path, note_path: str | Path | None) -> Path | None:
        if note_path is None:
            return None

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
        if not resolved_note.exists() or not resolved_note.is_file():
            return None
        return resolved_note

    def _derive_note_title(self, text: str, note_path: Path) -> str:
        for line in text.splitlines():
            match = re.match(r"^#\s+(.+?)\s*$", line)
            if match:
                return match.group(1).strip()
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:80]
        return note_path.stem

    def _build_backlink_context(
        self,
        text: str,
        matched_links: list[dict[str, object]],
    ) -> str:
        raw = str(matched_links[0]["raw"])
        index = text.find(raw)
        if index < 0:
            return text[:220].strip()

        start = max(0, index - 80)
        end = min(len(text), index + len(raw) + 140)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        return f"{prefix}{text[start:end].strip()}{suffix}"

    def _normalize_title(self, title: str) -> str:
        return " ".join(title.strip().casefold().split())

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
