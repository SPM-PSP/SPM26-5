from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


class DatabaseManager:
    """Thin SQLite connection wrapper for a workspace database."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).expanduser().resolve()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON;")
        return connection

    def __enter__(self) -> sqlite3.Connection:
        self._connection = self.connect()
        return self._connection

    def __exit__(self, exc_type, exc, tb) -> None:
        connection = getattr(self, "_connection", None)
        if connection is None:
            return
        if exc_type is None:
            connection.commit()
        else:
            connection.rollback()
        connection.close()
        self._connection = None

    def query(self, sql: str, params: Iterable[Any] | None = None) -> list[sqlite3.Row]:
        with self as connection:
            cursor = connection.execute(sql, tuple(params or ()))
            return list(cursor.fetchall())

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> int:
        with self as connection:
            cursor = connection.execute(sql, tuple(params or ()))
            return cursor.rowcount

    def get_all_references(self) -> list[sqlite3.Row]:
        return self.query(
            """
            SELECT reference_id, title, authors_json, year, entry_type, source_format,
                   source_path, pdf_path, created_at, updated_at
            FROM references_catalog
            ORDER BY title COLLATE NOCASE ASC
            """
        )

    def get_note_detail(self, note_id: str) -> sqlite3.Row | None:
        rows = self.query(
            """
            SELECT note_id, relative_path, title, content, planet, updated_at, file_mtime
            FROM notes
            WHERE note_id = ?
            """,
            (note_id,),
        )
        return rows[0] if rows else None

    def get_reference_detail(self, reference_id: str) -> sqlite3.Row | None:
        rows = self.query(
            """
            SELECT reference_id, title, authors_json, year, entry_type, source_format,
                   source_path, pdf_path, created_at, updated_at
            FROM references_catalog
            WHERE reference_id = ?
            """,
            (reference_id,),
        )
        return rows[0] if rows else None

    def get_note_links(self, note_id: str) -> list[sqlite3.Row]:
        return self.query(
            """
            SELECT raw_link, target_title, target_heading, alias
            FROM note_links
            WHERE source_note_id = ?
            ORDER BY id ASC
            """,
            (note_id,),
        )
