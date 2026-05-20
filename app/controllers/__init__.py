from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .app_controller import AppController
    from .workspace_controller import WorkspaceController

__all__ = ["AppController", "WorkspaceController"]


def __getattr__(name: str) -> Any:
    if name == "AppController":
        from .app_controller import AppController

        return AppController
    if name == "WorkspaceController":
        from .workspace_controller import WorkspaceController

        return WorkspaceController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
