from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from app.bootstrap import build_startup_pipeline


def make_workspace_root(test_name: str) -> Path:
    root = Path("tests/.tmp") / f"{test_name}-{uuid.uuid4().hex}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_workspace_bootstrap_creates_required_workspace_artifacts() -> None:
    workspace_root = make_workspace_root("demo-workspace")
    app_controller = build_startup_pipeline()

    result = app_controller.start_app(workspace_root)

    assert result["success"] is True
    workspace_context = result["data"]["workspace_context"]
    assert workspace_context.root_path == workspace_root.resolve()
    assert workspace_context.agni_dir.exists()
    assert workspace_context.database_path.exists()
    assert workspace_context.settings_path.exists()
    assert workspace_context.notes_path.exists()
    assert workspace_context.inbox_note_path.exists()
    assert result["data"]["main_window"]["window_title"].startswith("Agni - demo-workspace")


def test_workspace_bootstrap_initializes_database_file() -> None:
    workspace_root = make_workspace_root("db-workspace")
    app_controller = build_startup_pipeline()

    result = app_controller.start_app(workspace_root)

    assert result["success"] is True
    workspace_context = result["data"]["workspace_context"]
    assert workspace_context.database_path.exists()
    assert workspace_context.database_path.name == "agni.db"
    assert workspace_context.agni_dir.name == ".agni"
