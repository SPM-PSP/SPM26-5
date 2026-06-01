from __future__ import annotations

import json
import re
from pathlib import Path


TITLE_STORE_RELATIVE_PATH = Path(".agni") / "ui_note_titles.json"
CASE_COLLISION_SUFFIX_RE = re.compile(r"^(?P<title>.+)-(?P<counter>[2-9]\d*)$")


def title_store_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / TITLE_STORE_RELATIVE_PATH


def title_for_path(workspace_root: Path | str | None, note_path: Path | str) -> str | None:
    if workspace_root is None:
        return None
    mapping = load_title_map(workspace_root)
    title = mapping.get(_relative_key(workspace_root, note_path))
    if isinstance(title, str):
        title = title.strip()
    return title or _case_collision_suffix_title(Path(note_path))


def set_title_for_path(workspace_root: Path | str, note_path: Path | str, title: str) -> None:
    mapping = load_title_map(workspace_root)
    key = _relative_key(workspace_root, note_path)
    clean_title = title.strip()
    if clean_title and clean_title != Path(note_path).stem:
        mapping[key] = clean_title
    else:
        mapping.pop(key, None)
    save_title_map(workspace_root, mapping)


def remove_title_for_path(workspace_root: Path | str, note_path: Path | str) -> None:
    mapping = load_title_map(workspace_root)
    key = _relative_key(workspace_root, note_path)
    if key in mapping:
        mapping.pop(key, None)
        save_title_map(workspace_root, mapping)


def load_title_map(workspace_root: Path | str) -> dict[str, str]:
    store_path = title_store_path(workspace_root)
    if not store_path.exists():
        return {}
    try:
        data = json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if str(value).strip()}


def save_title_map(workspace_root: Path | str, mapping: dict[str, str]) -> None:
    store_path = title_store_path(workspace_root)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _relative_key(workspace_root: Path | str, note_path: Path | str) -> str:
    root = Path(workspace_root).resolve()
    path = Path(note_path).resolve()
    try:
        key = path.relative_to(root)
    except ValueError:
        key = path
    return key.as_posix()


def _case_collision_suffix_title(note_path: Path) -> str | None:
    match = CASE_COLLISION_SUFFIX_RE.match(note_path.stem)
    if match is None:
        return None

    title = match.group("title")
    try:
        siblings = note_path.parent.iterdir()
    except OSError:
        return None

    for sibling in siblings:
        if sibling == note_path or not sibling.is_file() or sibling.suffix != note_path.suffix:
            continue
        if sibling.stem.lower() == title.lower() and sibling.stem != title:
            return title
    return None
