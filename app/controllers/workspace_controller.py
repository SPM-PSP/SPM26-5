from __future__ import annotations

from pathlib import Path

from app.services.workspace_service import WorkspaceService


class WorkspaceController:
    def __init__(self, workspace_service: WorkspaceService) -> None:
        self.workspace_service = workspace_service

    def select_workspace(self, workspace_path: str | Path) -> dict[str, object]:
        return self.open_workspace(workspace_path)

    def open_workspace(self, workspace_path: str | Path) -> dict[str, object]:
        result = self.workspace_service.initialize_workspace(workspace_path)
        if not result["success"]:
            return result

        return {
            "success": True,
            "message": "Workspace is ready.",
            "data": {
                "workspace_context": result["data"]["workspace_context"],
                "next_action": "open_main_window",
            },
        }

    def create_or_repair_workspace(self, workspace_path: str | Path) -> dict[str, object]:
        return self.workspace_service.initialize_workspace(workspace_path)
