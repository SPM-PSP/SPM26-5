from __future__ import annotations

import sqlite3


CURRENT_VERSION = 2


SCHEMA_V1 = """
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
    tags_json TEXT NOT NULL DEFAULT '[]',
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
    tags_json,
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
    tags_json TEXT NOT NULL DEFAULT '[]',
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


def _ensure_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS migration_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def get_current_version(connection: sqlite3.Connection) -> int:
    _ensure_migration_table(connection)
    row = connection.execute(
        "SELECT MAX(version) AS version FROM migration_version"
    ).fetchone()
    if row is None or row["version"] is None:
        return 0
    return int(row["version"])


def _column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row["name"]) == column_name for row in rows)


def _rebuild_notes_fts(connection: sqlite3.Connection) -> None:
    connection.execute("DROP TABLE IF EXISTS notes_fts")
    connection.execute(
        """
        CREATE VIRTUAL TABLE notes_fts USING fts5(
            note_id UNINDEXED,
            relative_path UNINDEXED,
            title,
            tags_json,
            content
        )
        """
    )


def migrate(connection: sqlite3.Connection) -> None:
    _ensure_migration_table(connection)
    current_version = get_current_version(connection)
    if current_version < 1:
        connection.executescript(SCHEMA_V1)
        connection.execute(
            "INSERT OR REPLACE INTO migration_version(version) VALUES (1)"
        )
        current_version = 1

    if current_version < 2:
        if not _column_exists(connection, "notes", "tags_json"):
            connection.execute(
                "ALTER TABLE notes ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'"
            )
        if not _column_exists(connection, "references_catalog", "tags_json"):
            connection.execute(
                "ALTER TABLE references_catalog ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'"
            )
        _rebuild_notes_fts(connection)
        connection.execute(
            "INSERT OR REPLACE INTO migration_version(version) VALUES (2)"
        )
