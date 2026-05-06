<<<<<<< HEAD
from __future__ import annotations

from dataclasses import dataclass

from app.bootstrap.config import AppConfig
from app.domain.dto import WorkspaceContextDTO
=======
from dataclasses import dataclass
from pathlib import Path
from typing import Any
>>>>>>> 549c716 (Finish the basic code framework)


@dataclass(slots=True)
class AppContext:
<<<<<<< HEAD
    config: AppConfig
    workspace: WorkspaceContextDTO | None = None
=======
    workspace_root: Path
    db_path: Path

    # 后续由 Xie / Xiang / 你自己逐步接入
    note_service: Any | None = None
    search_service: Any | None = None
    reference_service: Any | None = None

    # 后续也可以把 main_window / controllers 塞进来，
    # 但阶段一先不要加太多，保持轻量。
>>>>>>> 549c716 (Finish the basic code framework)
