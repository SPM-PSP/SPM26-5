from __future__ import annotations

from pathlib import Path

from app.bootstrap.app_context import AppContext
from app.bootstrap.config import AppConfig
from app.controllers.workspace_controller import WorkspaceController


class AppController:
    def __init__(self, workspace_controller: WorkspaceController, config: AppConfig) -> None:
        self.workspace_controller = workspace_controller
        self.config = config
        self.app_context: AppContext | None = None

    def start_app(self, workspace_path: str | Path | None = None) -> dict[str, object]:
        try:
            return self.handle_startup(workspace_path)
        except Exception as error:  # pragma: no cover - defensive boundary
            return self.handle_fatal_error(error)

    def handle_startup(self, workspace_path: str | Path | None = None) -> dict[str, object]:
        if workspace_path is None:
            return {
                "success": False,
                "message": "Workspace path is required until the workspace picker UI is implemented.",
                "data": {"next_action": "select_workspace"},
            }

        workspace_result = self.workspace_controller.open_workspace(workspace_path)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        self.app_context = AppContext(
            workspace_root=workspace_context.workspace_root,
            db_path=workspace_context.database_path,
        )
        return self.open_main_window()

    def open_main_window(self) -> dict[str, object]:
        if self.app_context is None:
            return self.handle_fatal_error(RuntimeError("Workspace context was not initialized."))

        window_title = f"{self.config.app_name} - {self.app_context.workspace_root.name}"
        return {
            "success": True,
            "message": "Workspace opened successfully.",
            "data": {
                "app_context": self.app_context,
                "workspace_context": self.app_context,
                "main_window": {
                    "window_title": window_title,
                    "workspace_root": str(self.app_context.workspace_root),
                },
            },
        }

    def handle_fatal_error(self, error: Exception) -> dict[str, object]:
        return {
            "success": False,
            "message": str(error),
            "data": {"error_type": error.__class__.__name__},
        }
