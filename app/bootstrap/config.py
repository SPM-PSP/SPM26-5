from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    app_name: str = "Agni"
    app_version: str = "0.1.0"
    workspace_settings_filename: str = "kb_settings.json"
    workspace_database_filename: str = "agni.db"
    default_workspace_root: Path | None = None
