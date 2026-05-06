from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AppContext:
    workspace_root: Path
    db_path: Path

    note_service: Any | None = None
    search_service: Any | None = None
    reference_service: Any | None = None