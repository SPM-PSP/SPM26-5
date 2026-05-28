import json

from app.bootstrap.startup import bootstrap_workspace


def test_bootstrap_workspace_creates_expected_layout(tmp_path):
    workspace_root = tmp_path / "demo_workspace"

    ctx = bootstrap_workspace(workspace_root)

    assert ctx.workspace_root == workspace_root.resolve()
    assert ctx.db_path == (workspace_root / ".agni" / "agni.db").resolve()

    assert (workspace_root / "notes").exists()
    assert (workspace_root / "attachments").exists()
    assert (workspace_root / "exports").exists()
    assert (workspace_root / ".agni").exists()
    assert (workspace_root / ".agni" / "cache").exists()
    assert (workspace_root / ".agni" / "state.json").exists()


def test_bootstrap_workspace_creates_default_state_json(tmp_path):
    workspace_root = tmp_path / "demo_workspace"

    bootstrap_workspace(workspace_root)

    state_path = workspace_root / ".agni" / "state.json"
    data = json.loads(state_path.read_text(encoding="utf-8"))

    assert "recent_notes" in data
    assert "last_opened_note_id" in data
    assert data["recent_notes"] == []
    assert data["last_opened_note_id"] is None


def test_bootstrap_workspace_is_idempotent(tmp_path):
    workspace_root = tmp_path / "demo_workspace"

    bootstrap_workspace(workspace_root)
    bootstrap_workspace(workspace_root)

    assert (workspace_root / "notes").exists()
    assert (workspace_root / "attachments").exists()
    assert (workspace_root / "exports").exists()
    assert (workspace_root / ".agni").exists()
    assert (workspace_root / ".agni" / "cache").exists()
    assert (workspace_root / ".agni" / "state.json").exists()


def test_bootstrap_workspace_initializes_database_and_controllers(tmp_path):
    workspace_root = tmp_path / "demo_workspace"

    ctx = bootstrap_workspace(workspace_root)

    assert (workspace_root / ".agni" / "agni.db").exists()
    assert ctx.workspace_context is not None
    assert ctx.database is not None
    assert ctx.note_controller is not None
    assert ctx.search_controller is not None
    assert ctx.reference_controller is not None
    assert ctx.knowledge_controller is not None
