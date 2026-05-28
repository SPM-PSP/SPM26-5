from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.bootstrap.config import AppConfig, WorkspaceConfig
from app.bootstrap.paths import resolve_workspace_paths
from database.tool import connect_to_database


@dataclass(slots=True)
class WorkspaceContext:
    root_path: Path
    notes_path: Path
    references_path: Path
    attachments_path: Path
    exports_path: Path
    agni_dir: Path
    cache_path: Path
    db_path: Path
    state_path: Path
    inbox_note_path: Path
    created_paths: tuple[Path, ...]

    @property
    def workspace_root(self) -> Path:
        return self.root_path

    @property
    def database_path(self) -> Path:
        return self.db_path


class WorkspaceService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def validate_workspace(self, workspace_path: str | Path) -> dict[str, object]:
        raw_path = str(workspace_path).strip()
        if not raw_path:
            return self._failure("Workspace path cannot be empty.")

        candidate = Path(raw_path).expanduser()
        if candidate.exists() and candidate.is_file():
            return self._failure("Workspace path must be a directory, not a file.")

        return self._success(
            "Workspace path is valid.",
            workspace_path=candidate.resolve(),
        )

    def ensure_workspace_structure(self, workspace_path: str | Path) -> dict[str, object]:
        validation_result = self.validate_workspace(workspace_path)
        if not validation_result["success"]:
            return validation_result

        resolved_path = validation_result["data"]["workspace_path"]
        workspace_config = resolve_workspace_paths(resolved_path)
        created_paths = self._ensure_workspace_layout(workspace_config)
        workspace_context = self.build_workspace_context(workspace_config, created_paths)

        return self._success(
            "Workspace structure is ready.",
            workspace_context=workspace_context,
            workspace_root=workspace_context.root_path,
            created_paths=workspace_context.created_paths,
        )

    def initialize_workspace(self, workspace_path: str | Path) -> dict[str, object]:
        structure_result = self.ensure_workspace_structure(workspace_path)
        if not structure_result["success"]:
            return structure_result

        workspace_context = structure_result["data"]["workspace_context"]
        return self._success(
            "Workspace initialized successfully.",
            workspace_context=workspace_context,
            workspace_root=workspace_context.root_path,
            created_paths=workspace_context.created_paths,
        )

    def build_workspace_context(
        self, workspace_config: WorkspaceConfig, created_paths: tuple[Path, ...]
    ) -> WorkspaceContext:
        references_path = workspace_config.workspace_root / "references"
        inbox_note_path = workspace_config.notes_dir / "Inbox.md"
        return WorkspaceContext(
            root_path=workspace_config.workspace_root,
            notes_path=workspace_config.notes_dir,
            references_path=references_path,
            attachments_path=workspace_config.attachments_dir,
            exports_path=workspace_config.exports_dir,
            agni_dir=workspace_config.agni_dir,
            cache_path=workspace_config.cache_dir,
            db_path=workspace_config.db_path,
            state_path=workspace_config.state_path,
            inbox_note_path=inbox_note_path,
            created_paths=created_paths,
        )

    def _ensure_workspace_layout(self, workspace_config: WorkspaceConfig) -> tuple[Path, ...]:
        created_paths: list[Path] = []
        references_path = workspace_config.workspace_root / "references"
        inbox_note_path = workspace_config.notes_dir / "Inbox.md"

        for directory in (
            workspace_config.workspace_root,
            workspace_config.notes_dir,
            references_path,
            workspace_config.attachments_dir,
            workspace_config.exports_dir,
            workspace_config.agni_dir,
            workspace_config.cache_dir,
        ):
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                created_paths.append(directory)

        if not workspace_config.state_path.exists():
            workspace_config.state_path.write_text(
                json.dumps(
                    {
                        "recent_notes": [],
                        "last_opened_note_id": None,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            created_paths.append(workspace_config.state_path)

        if not inbox_note_path.exists():
            inbox_note_path.write_text("# Inbox\n\n", encoding="utf-8")
            created_paths.append(inbox_note_path)

        if not workspace_config.db_path.exists():
            workspace_config.db_path.touch()
            created_paths.append(workspace_config.db_path)
        self._initialize_database(workspace_config.db_path)
        self._synchronize_workspace_database(workspace_config)

        return tuple(created_paths)

    def connect_workspace_database(self, workspace_context: WorkspaceContext):
        return connect_to_database(workspace_context.db_path)

    def _initialize_database(self, db_path: Path) -> None:
        with sqlite3.connect(db_path) as connection:
            connection.execute("PRAGMA journal_mode=WAL;")
            connection.execute("PRAGMA foreign_keys=ON;")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS app_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                INSERT OR REPLACE INTO app_metadata(key, value)
                VALUES ('workspace_version', '2');

                CREATE TABLE IF NOT EXISTS notes (
                    note_id TEXT PRIMARY KEY,
                    relative_path TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    planet TEXT,
                    content_hash TEXT NOT NULL DEFAULT '',
                    updated_at TEXT,
                    file_mtime REAL
                );

                CREATE TABLE IF NOT EXISTS note_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_note_id TEXT NOT NULL,
                    target_title TEXT NOT NULL,
                    target_heading TEXT,
                    alias TEXT,
                    raw_link TEXT NOT NULL,
                    FOREIGN KEY(source_note_id) REFERENCES notes(note_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_note_links_source_note_id
                ON note_links(source_note_id);

                CREATE INDEX IF NOT EXISTS idx_note_links_target_title
                ON note_links(target_title);

                CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                    note_id UNINDEXED,
                    relative_path UNINDEXED,
                    title,
                    content
                );

                CREATE TABLE IF NOT EXISTS object_planets (
                    object_kind TEXT NOT NULL,
                    object_key TEXT NOT NULL,
                    planet TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(object_kind, object_key)
                );

                CREATE TABLE IF NOT EXISTS references_catalog (
                    reference_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    authors_json TEXT NOT NULL DEFAULT '[]',
                    year INTEGER,
                    entry_type TEXT,
                    source_format TEXT,
                    source_path TEXT,
                    pdf_path TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS pdf_annotations (
                    annotation_id TEXT PRIMARY KEY,
                    reference_id TEXT NOT NULL,
                    pdf_path TEXT NOT NULL,
                    text TEXT NOT NULL,
                    page_number INTEGER,
                    page_label TEXT,
                    rects_json TEXT NOT NULL DEFAULT '[]',
                    comment TEXT,
                    color TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_pdf_annotations_reference_id
                ON pdf_annotations(reference_id);

                CREATE TABLE IF NOT EXISTS citations_catalog (
                    citation_id TEXT PRIMARY KEY,
                    reference_id TEXT NOT NULL,
                    annotation_id TEXT,
                    token TEXT NOT NULL,
                    page_label TEXT,
                    note_path TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_citations_reference_id
                ON citations_catalog(reference_id);
                """
            )
            connection.commit()

    def _synchronize_workspace_database(self, workspace_config: WorkspaceConfig) -> None:
        references_path = workspace_config.workspace_root / "references"
        manifest_path = workspace_config.agni_dir / "references_manifest.json"
        annotations_manifest_path = workspace_config.agni_dir / "pdf_annotations_manifest.json"
        citations_manifest_path = workspace_config.agni_dir / "citations_manifest.json"

        with sqlite3.connect(workspace_config.db_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON;")

            existing_planets = {
                (str(row["object_kind"]), str(row["object_key"])): str(row["planet"])
                for row in connection.execute(
                    "SELECT object_kind, object_key, planet FROM object_planets"
                ).fetchall()
            }

            connection.execute("DELETE FROM note_links")
            connection.execute("DELETE FROM notes")
            connection.execute("DELETE FROM notes_fts")
            for note_path in sorted(workspace_config.notes_dir.rglob("*.md"), key=lambda item: item.name.lower()):
                try:
                    content = note_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                relative_path = str(note_path.relative_to(workspace_config.notes_dir))
                note_id = note_path.stem
                title = self._derive_note_title(content, note_path)
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                planet = existing_planets.get(("note", note_id), self._infer_note_planet(note_path))
                connection.execute(
                    """
                    INSERT INTO notes(note_id, relative_path, title, content, planet, content_hash, updated_at, file_mtime)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)
                    """,
                    (note_id, relative_path, title, content, planet, content_hash, note_path.stat().st_mtime),
                )
                connection.execute(
                    """
                    INSERT INTO notes_fts(note_id, relative_path, title, content)
                    VALUES (?, ?, ?, ?)
                    """,
                    (note_id, relative_path, title, content),
                )
                connection.execute(
                    """
                    INSERT INTO object_planets(object_kind, object_key, planet, updated_at)
                    VALUES ('note', ?, ?, datetime('now'))
                    ON CONFLICT(object_kind, object_key) DO UPDATE SET
                        planet = excluded.planet,
                        updated_at = excluded.updated_at
                    """,
                    (note_id, planet),
                )
                for link in self._extract_wikilinks(content):
                    connection.execute(
                        """
                        INSERT INTO note_links(source_note_id, target_title, target_heading, alias, raw_link)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            note_id,
                            link["target_title"],
                            link["target_heading"],
                            link["alias"],
                            link["raw"],
                        ),
                    )

            connection.execute("DELETE FROM references_catalog")
            references_manifest = self._load_manifest_records(manifest_path, "references")
            for record in references_manifest:
                reference_id = str(record.get("reference_id") or "").strip()
                if not reference_id:
                    continue
                connection.execute(
                    """
                    INSERT INTO references_catalog(
                        reference_id, title, authors_json, year, entry_type,
                        source_format, source_path, pdf_path, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        reference_id,
                        str(record.get("title") or reference_id),
                        json.dumps(list(record.get("authors", [])), ensure_ascii=False),
                        record.get("year"),
                        record.get("entry_type"),
                        record.get("source_format"),
                        record.get("source_path"),
                        record.get("pdf_path"),
                        record.get("created_at"),
                        record.get("updated_at"),
                    ),
                )
                planet = existing_planets.get(("reference", reference_id), "Reading")
                connection.execute(
                    """
                    INSERT INTO object_planets(object_kind, object_key, planet, updated_at)
                    VALUES ('reference', ?, ?, datetime('now'))
                    ON CONFLICT(object_kind, object_key) DO UPDATE SET
                        planet = excluded.planet,
                        updated_at = excluded.updated_at
                    """,
                    (reference_id, planet),
                )

            connection.execute("DELETE FROM pdf_annotations")
            annotations_manifest = self._load_manifest_records(annotations_manifest_path, "annotations")
            for annotation in annotations_manifest:
                connection.execute(
                    """
                    INSERT INTO pdf_annotations(
                        annotation_id, reference_id, pdf_path, text, page_number,
                        page_label, rects_json, comment, color, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        annotation.get("annotation_id"),
                        annotation.get("reference_id"),
                        annotation.get("pdf_path"),
                        annotation.get("text"),
                        annotation.get("page_number"),
                        annotation.get("page_label"),
                        json.dumps(annotation.get("rects", []), ensure_ascii=False),
                        annotation.get("comment"),
                        annotation.get("color"),
                        annotation.get("created_at"),
                    ),
                )

            connection.execute("DELETE FROM citations_catalog")
            citations_manifest = self._load_manifest_records(citations_manifest_path, "citations")
            for citation in citations_manifest:
                connection.execute(
                    """
                    INSERT INTO citations_catalog(
                        citation_id, reference_id, annotation_id, token,
                        page_label, note_path, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        citation.get("citation_id"),
                        citation.get("reference_id"),
                        citation.get("annotation_id"),
                        citation.get("token"),
                        citation.get("page_label"),
                        citation.get("note_path"),
                        citation.get("created_at"),
                    ),
                )

            connection.commit()

    def _load_manifest_records(self, manifest_path: Path, key: str) -> list[dict[str, object]]:
        if not manifest_path.exists():
            return []
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        records = data.get(key, [])
        return records if isinstance(records, list) else []

    def _derive_note_title(self, content: str, note_path: Path) -> str:
        for line in content.splitlines():
            match = re.match(r"^#\s+(.+?)\s*$", line)
            if match:
                return match.group(1).strip()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:80]
        return note_path.stem

    def _infer_note_planet(self, note_path: Path) -> str:
        lowered = str(note_path).casefold()
        if "inbox" in lowered:
            return "Inbox"
        if "reading" in lowered or "paper" in lowered or "pdf" in lowered:
            return "Reading"
        if "research" in lowered or "project" in lowered:
            return "Research"
        return "Unassigned"

    def _extract_wikilinks(self, content: str) -> list[dict[str, str | None]]:
        pattern = re.compile(
            r"\[\[(?P<title>[^\]#|]+?)(?:#(?P<heading>[^\]|]+))?(?:\|(?P<alias>[^\]]+))?\]\]"
        )
        links: list[dict[str, str | None]] = []
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
