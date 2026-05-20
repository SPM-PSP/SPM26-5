from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .workspace_service import WorkspaceService

__all__ = ["WorkspaceService"]


def __getattr__(name: str) -> Any:
    if name == "WorkspaceService":
        from .workspace_service import WorkspaceService

        return WorkspaceService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
