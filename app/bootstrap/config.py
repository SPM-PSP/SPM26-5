<<<<<<< HEAD
from __future__ import annotations

=======
>>>>>>> 549c716 (Finish the basic code framework)
from dataclasses import dataclass
from pathlib import Path


<<<<<<< HEAD
@dataclass(frozen=True, slots=True)
class AppConfig:
    app_name: str = "Agni"
    app_version: str = "0.1.0"
    workspace_settings_filename: str = "kb_settings.json"
    workspace_database_filename: str = "agni.db"
    default_workspace_root: Path | None = None
=======
@dataclass(slots=True)
class AppConfig:
    app_name: str = "Agni"
    organization_name: str = "Agni Team"


@dataclass(slots=True)
class WorkspaceConfig:
    workspace_root: Path
    notes_dir: Path
    attachments_dir: Path
    exports_dir: Path
    agni_dir: Path
    db_path: Path
    state_path: Path
    cache_dir: Path
>>>>>>> 549c716 (Finish the basic code framework)
