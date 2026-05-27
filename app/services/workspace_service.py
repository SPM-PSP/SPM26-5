from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.bootstrap.config import AppConfig, WorkspaceConfig
from app.bootstrap.paths import resolve_workspace_paths


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

        return tuple(created_paths)

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
