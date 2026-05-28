from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AppContext:
    workspace_root: Path
    db_path: Path
    workspace_context: Any | None = None
    database: Any | None = None
    workspace_controller: Any | None = None

    note_service: Any | None = None
    search_service: Any | None = None
    reference_service: Any | None = None
    link_service: Any | None = None
    knowledge_model_service: Any | None = None
    note_controller: Any | None = None
    search_controller: Any | None = None
    reference_controller: Any | None = None
    knowledge_controller: Any | None = None
