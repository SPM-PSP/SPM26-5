from __future__ import annotations

import json
from pathlib import Path


PLANET_STORE_RELATIVE_PATH = Path(".agni") / "ui_planets.json"


def planet_store_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / PLANET_STORE_RELATIVE_PATH


def load_custom_planets(workspace_root: Path | str | None) -> list[str]:
    return _load_planet_list(workspace_root, "custom_planets")


def load_hidden_planets(workspace_root: Path | str | None) -> list[str]:
    return _load_planet_list(workspace_root, "hidden_planets")


def _load_planet_list(workspace_root: Path | str | None, key: str) -> list[str]:
    if workspace_root is None:
        return []

    store_path = planet_store_path(workspace_root)
    if not store_path.exists():
        return []

    try:
        data = json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    planets = data.get(key, []) if isinstance(data, dict) else []
    if not isinstance(planets, list):
        return []

    seen: set[str] = set()
    result: list[str] = []
    for planet in planets:
        title = str(planet).strip()
        if title and title not in seen:
            seen.add(title)
            result.append(title)
    return result


def add_custom_planet(workspace_root: Path | str, title: str) -> list[str]:
    clean_title = title.strip()
    planets = load_custom_planets(workspace_root)
    if clean_title and clean_title not in planets:
        planets.append(clean_title)
        save_custom_planets(workspace_root, planets)
    return planets


def hide_planet(workspace_root: Path | str, title: str) -> list[str]:
    clean_title = title.strip()
    planets = load_hidden_planets(workspace_root)
    if clean_title and clean_title not in planets:
        planets.append(clean_title)
        _save_planet_list(workspace_root, "hidden_planets", planets)
    return planets


def unhide_planet(workspace_root: Path | str, title: str) -> list[str]:
    clean_title = title.strip()
    planets = [planet for planet in load_hidden_planets(workspace_root) if planet != clean_title]
    _save_planet_list(workspace_root, "hidden_planets", planets)
    return planets


def remove_custom_planet(workspace_root: Path | str, title: str) -> list[str]:
    clean_title = title.strip()
    planets = [planet for planet in load_custom_planets(workspace_root) if planet != clean_title]
    save_custom_planets(workspace_root, planets)
    return planets


def save_custom_planets(workspace_root: Path | str, planets: list[str]) -> None:
    _save_planet_list(workspace_root, "custom_planets", planets)


def _save_planet_list(workspace_root: Path | str, key: str, planets: list[str]) -> None:
    store_path = planet_store_path(workspace_root)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(store_path.read_text(encoding="utf-8")) if store_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}

    seen: set[str] = set()
    clean_planets: list[str] = []
    for planet in planets:
        title = str(planet).strip()
        if title and title not in seen:
            seen.add(title)
            clean_planets.append(title)
    data[key] = clean_planets

    store_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
