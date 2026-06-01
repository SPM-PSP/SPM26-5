from __future__ import annotations

import json
from pathlib import Path
from typing import Any


LAYOUT_FILE_NAME = "ui_graph_layout.json"


def load_graph_layout(workspace_root: Path | None) -> dict[str, Any]:
    if workspace_root is None:
        return {}
    path = _layout_path(workspace_root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_node_position(
    workspace_root: Path | None,
    view_key: str,
    node_key: str,
) -> tuple[float, float] | None:
    data = load_graph_layout(workspace_root)
    value = data.get(view_key, {}).get(node_key)
    if not isinstance(value, dict):
        return None
    try:
        return float(value["x"]), float(value["y"])
    except (KeyError, TypeError, ValueError):
        return None


def save_node_position(
    workspace_root: Path | None,
    view_key: str,
    node_key: str,
    x: float,
    y: float,
) -> None:
    if workspace_root is None:
        return
    data = load_graph_layout(workspace_root)
    view_data = data.setdefault(view_key, {})
    if not isinstance(view_data, dict):
        view_data = {}
        data[view_key] = view_data
    view_data[node_key] = {"x": round(float(x), 2), "y": round(float(y), 2)}

    path = _layout_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _layout_path(workspace_root: Path) -> Path:
    return workspace_root / ".agni" / LAYOUT_FILE_NAME
