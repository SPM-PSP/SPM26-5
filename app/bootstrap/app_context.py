from __future__ import annotations

from dataclasses import dataclass

from app.bootstrap.config import AppConfig
from app.domain.dto import WorkspaceContextDTO


@dataclass(slots=True)
class AppContext:
    config: AppConfig
    workspace: WorkspaceContextDTO | None = None
