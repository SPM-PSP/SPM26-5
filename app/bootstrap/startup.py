<<<<<<< HEAD
from __future__ import annotations

from app.bootstrap.config import AppConfig
from app.controllers.app_controller import AppController
from app.controllers.workspace_controller import WorkspaceController
from app.services.workspace_service import WorkspaceService


def build_startup_pipeline(config: AppConfig | None = None) -> AppController:
    app_config = config or AppConfig()
    workspace_service = WorkspaceService(app_config)
    workspace_controller = WorkspaceController(workspace_service)
    return AppController(workspace_controller=workspace_controller, config=app_config)
=======
import json
from pathlib import Path

from app.bootstrap.app_context import AppContext
from app.bootstrap.config import AppConfig, WorkspaceConfig
from app.bootstrap.paths import resolve_workspace_paths


def ensure_workspace_layout(config: WorkspaceConfig) -> None:
    """
    确保工作区目录结构存在。
    """
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
    """
    启动时先补齐工作区目录结构，并返回基础 AppContext。
    """
    workspace_config = resolve_workspace_paths(workspace_root)
    ensure_workspace_layout(workspace_config)

    return AppContext(
        workspace_root=workspace_config.workspace_root,
        db_path=workspace_config.db_path,
    )


def bootstrap_app(workspace_root: str | Path) -> tuple[AppConfig, AppContext]:
    """
    返回应用级配置和工作区上下文。
    阶段一先做到这里，后面再继续接数据库、controller、main window。
    """
    app_config = AppConfig()
    app_context = bootstrap_workspace(workspace_root)
    return app_config, app_context
>>>>>>> 549c716 (Finish the basic code framework)
