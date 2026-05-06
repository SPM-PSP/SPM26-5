import json
from pathlib import Path

from app.bootstrap.app_context import AppContext
from app.bootstrap.config import AppConfig, WorkspaceConfig
from app.bootstrap.paths import resolve_workspace_paths


def ensure_workspace_layout(config: WorkspaceConfig) -> None:
    config.workspace_root.mkdir(parents=True, exist_ok=True)
    config.notes_dir.mkdir(parents=True, exist_ok=True)
    config.attachments_dir.mkdir(parents=True, exist_ok=True)
    config.exports_dir.mkdir(parents=True, exist_ok=True)
    config.agni_dir.mkdir(parents=True, exist_ok=True)
    config.cache_dir.mkdir(parents=True, exist_ok=True)

    if not config.state_path.exists():
        config.state_path.write_text(
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


def bootstrap_workspace(workspace_root: str | Path) -> AppContext:
    workspace_config = resolve_workspace_paths(workspace_root)
    ensure_workspace_layout(workspace_config)

    return AppContext(
        workspace_root=workspace_config.workspace_root,
        db_path=workspace_config.db_path,
    )


def bootstrap_app(workspace_root: str | Path) -> tuple[AppConfig, AppContext]:
    app_config = AppConfig()
    app_context = bootstrap_workspace(workspace_root)
    return app_config, app_context