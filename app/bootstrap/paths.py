<<<<<<< HEAD
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.bootstrap.config import AppConfig


@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    root_path: Path
    agni_dir: Path
    database_path: Path
    settings_path: Path
    notes_path: Path
    references_path: Path
    attachments_path: Path
    cache_path: Path
    inbox_note_path: Path


def build_workspace_paths(workspace_path: str | Path, config: AppConfig) -> WorkspacePaths:
    root_path = Path(workspace_path).expanduser().resolve()
    agni_dir = root_path / ".agni"
    notes_path = root_path / "notes"
    references_path = root_path / "references"
    attachments_path = root_path / "attachments"
    cache_path = root_path / "cache"
    database_path = agni_dir / config.workspace_database_filename
    settings_path = agni_dir / config.workspace_settings_filename
    inbox_note_path = notes_path / "Inbox.md"

    return WorkspacePaths(
        root_path=root_path,
        agni_dir=agni_dir,
        database_path=database_path,
        settings_path=settings_path,
        notes_path=notes_path,
        references_path=references_path,
        attachments_path=attachments_path,
        cache_path=cache_path,
        inbox_note_path=inbox_note_path,
    )
=======
from pathlib import Path

from app.bootstrap.config import WorkspaceConfig
from app.bootstrap.exceptions import WorkspaceLayoutError


def resolve_workspace_paths(workspace_root: str | Path) -> WorkspaceConfig:
    """
    解析并标准化工作区路径，但不负责创建目录。
    """
    root = Path(workspace_root).expanduser().resolve()

    if not str(root).strip():
        raise WorkspaceLayoutError("workspace_root 不能为空。")

    notes_dir = root / "notes"
    attachments_dir = root / "attachments"
    exports_dir = root / "exports"
    agni_dir = root / ".agni"
    db_path = agni_dir / "agni.db"
    state_path = agni_dir / "state.json"
    cache_dir = agni_dir / "cache"

    return WorkspaceConfig(
        workspace_root=root,
        notes_dir=notes_dir,
        attachments_dir=attachments_dir,
        exports_dir=exports_dir,
        agni_dir=agni_dir,
        db_path=db_path,
        state_path=state_path,
        cache_dir=cache_dir,
    )
>>>>>>> 549c716 (Finish the basic code framework)
