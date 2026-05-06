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
