from pathlib import Path

from app.bootstrap.config import WorkspaceConfig
from app.bootstrap.exceptions import WorkspaceLayoutError


def resolve_workspace_paths(workspace_root: str | Path) -> WorkspaceConfig:
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