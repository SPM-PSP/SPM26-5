from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.bootstrap.config import AppConfig
from app.bootstrap.exceptions import WorkspaceInitializationError, WorkspaceValidationError
from app.bootstrap.paths import WorkspacePaths, build_workspace_paths
from app.domain.dto import WorkspaceContextDTO


class WorkspaceService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def validate_workspace(self, workspace_path: str | Path) -> dict[str, object]:
        candidate = Path(workspace_path).expanduser()
        if not str(candidate).strip():
            raise WorkspaceValidationError("Workspace path cannot be empty.")
        if candidate.exists() and candidate.is_file():
            raise WorkspaceValidationError("Workspace path must be a directory, not a file.")

        resolved_path = candidate.resolve()
        return {
            "success": True,
            "message": "Workspace path is valid.",
            "data": {"workspace_path": resolved_path},
        }

    def ensure_workspace_structure(self, workspace_path: str | Path) -> dict[str, object]:
        validation_result = self.validate_workspace(workspace_path)
        resolved_path = validation_result["data"]["workspace_path"]
        workspace_paths = build_workspace_paths(resolved_path, self.config)
        created_paths: list[Path] = []

        for directory in (
            workspace_paths.root_path,
            workspace_paths.agni_dir,
            workspace_paths.notes_path,
            workspace_paths.references_path,
            workspace_paths.attachments_path,
            workspace_paths.cache_path,
        ):
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                created_paths.append(directory)

        if not workspace_paths.inbox_note_path.exists():
            workspace_paths.inbox_note_path.write_text("", encoding="utf-8")
            created_paths.append(workspace_paths.inbox_note_path)

        if not workspace_paths.settings_path.exists():
            settings_payload = {
                "workspace_root": str(workspace_paths.root_path),
                "notes_dir": "notes",
                "references_dir": "references",
                "attachments_dir": "attachments",
                "cache_dir": "cache",
            }
            workspace_paths.settings_path.write_text(
                json.dumps(settings_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            created_paths.append(workspace_paths.settings_path)

        database_was_missing = not workspace_paths.database_path.exists()
        self._initialize_database(workspace_paths.database_path)
        if database_was_missing and workspace_paths.database_path.exists():
            created_paths.append(workspace_paths.database_path)

        return {
            "success": True,
            "message": "Workspace structure is ready.",
            "data": {
                "workspace_paths": workspace_paths,
                "created_paths": tuple(created_paths),
            },
        }

    def initialize_workspace(self, workspace_path: str | Path) -> dict[str, object]:
        structure_result = self.ensure_workspace_structure(workspace_path)
        workspace_paths = structure_result["data"]["workspace_paths"]
        created_paths = structure_result["data"]["created_paths"]
        workspace_context = self.build_workspace_context(workspace_paths, created_paths)

        return {
            "success": True,
            "message": "Workspace initialized successfully.",
            "data": {"workspace_context": workspace_context},
        }

    def build_workspace_context(
        self, workspace_paths: WorkspacePaths, created_paths: tuple[Path, ...]
    ) -> WorkspaceContextDTO:
        return WorkspaceContextDTO(
            root_path=workspace_paths.root_path,
            agni_dir=workspace_paths.agni_dir,
            database_path=workspace_paths.database_path,
            settings_path=workspace_paths.settings_path,
            notes_path=workspace_paths.notes_path,
            references_path=workspace_paths.references_path,
            attachments_path=workspace_paths.attachments_path,
            cache_path=workspace_paths.cache_path,
            inbox_note_path=workspace_paths.inbox_note_path,
            created_paths=created_paths,
        )

    def _initialize_database(self, database_path: Path) -> None:
        if self._database_is_bootstrapped(database_path):
            return

        bootstrap_error: sqlite3.Error | None = None
        try:
            with sqlite3.connect(database_path) as connection:
                connection.execute("PRAGMA journal_mode=WAL;")
                connection.execute("PRAGMA foreign_keys=ON;")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT OR REPLACE INTO app_metadata(key, value)
                    VALUES ('workspace_version', '1')
                    """
                )
                connection.commit()
        except sqlite3.Error as error:
            bootstrap_error = error

        if not self._database_is_bootstrapped(database_path):
            try:
                self._write_serialized_bootstrap_database(database_path)
            except sqlite3.Error as fallback_error:
                error_message = (
                    f"Failed to initialize workspace database: {bootstrap_error}"
                    if bootstrap_error is not None
                    else "Failed to initialize workspace database."
                )
                raise WorkspaceInitializationError(error_message) from fallback_error

        if not database_path.exists():
            raise WorkspaceInitializationError("Workspace database was not created.")

    def _database_is_bootstrapped(self, database_path: Path) -> bool:
        if not database_path.exists() or database_path.stat().st_size == 0:
            return False

        try:
            with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
                row = connection.execute(
                    "SELECT value FROM app_metadata WHERE key = 'workspace_version'"
                ).fetchone()
        except sqlite3.Error:
            return False

        return row == ("1",)

    def _write_serialized_bootstrap_database(self, database_path: Path) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute(
                """
                CREATE TABLE app_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO app_metadata(key, value)
                VALUES ('workspace_version', '1')
                """
            )
            connection.commit()
            database_path.write_bytes(connection.serialize())
        finally:
            connection.close()
