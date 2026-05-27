from __future__ import annotations

import re
from pathlib import Path


def import_reference_entries(import_path: str | Path) -> tuple[dict[str, object], ...]:
    path = Path(import_path)
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")

    if suffix == ".bib":
        return parse_bibtex_entries(text)
    if suffix == ".ris":
        return parse_ris_entries(text)
    raise ValueError(f"Unsupported reference import format: {path.suffix}")


def parse_bibtex_entries(text: str) -> tuple[dict[str, object], ...]:
    entries: list[dict[str, object]] = []
    for entry_type, key, body in _split_bibtex_entries(text):
        fields = _parse_bibtex_fields(body)
        raw_authors = fields.get("author", "")
        authors = tuple(
            part.strip()
            for part in raw_authors.replace("\n", " ").split(" and ")
            if part.strip()
        )
        title = str(fields.get("title", "")).strip("{}\" ").strip() or key
        year = _extract_year(str(fields.get("year", "")).strip("{}\" "))
        entries.append(
            {
                "reference_id": key,
                "entry_type": entry_type,
                "title": title,
                "authors": authors,
                "year": year,
                "source_key": key,
                "source_format": "bibtex",
                "raw_fields": fields,
            }
        )
    return tuple(entries)


def parse_ris_entries(text: str) -> tuple[dict[str, object], ...]:
    entries: list[dict[str, object]] = []
    current: dict[str, list[str] | str] = {}

    for line in text.splitlines():
        if not line.strip():
            continue
        if len(line) < 6 or line[2:6] != "  - ":
            continue

        tag = line[:2]
        value = line[6:].strip()
        if tag == "TY":
            current = {"entry_type": value}
            continue
        if tag == "ER":
            if current:
                title = str(current.get("TI") or current.get("T1") or "Untitled").strip()
                authors = tuple(current.get("AU", [])) if isinstance(current.get("AU"), list) else ()
                year = _extract_year(str(current.get("PY") or current.get("Y1") or ""))
                reference_id = _build_reference_id(title, year)
                entries.append(
                    {
                        "reference_id": reference_id,
                        "entry_type": str(current.get("entry_type") or "JOUR"),
                        "title": title,
                        "authors": tuple(author.strip() for author in authors if author.strip()),
                        "year": year,
                        "source_key": reference_id,
                        "source_format": "ris",
                        "raw_fields": dict(current),
                    }
                )
            current = {}
            continue

        existing = current.get(tag)
        if existing is None:
            current[tag] = [value] if tag == "AU" else value
        elif isinstance(existing, list):
            existing.append(value)
        else:
            current[tag] = [existing, value]

    return tuple(entries)


def _split_bibtex_entries(text: str) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    start = 0
    while True:
        at_index = text.find("@", start)
        if at_index < 0:
            break

        brace_index = text.find("{", at_index)
        if brace_index < 0:
            break

        header = text[at_index + 1 : brace_index].strip()
        comma_index = text.find(",", brace_index)
        if comma_index < 0:
            break

        key = text[brace_index + 1 : comma_index].strip()
        depth = 1
        cursor = comma_index + 1
        while cursor < len(text) and depth > 0:
            char = text[cursor]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            cursor += 1

        body = text[comma_index + 1 : cursor - 1].strip()
        entries.append((header.lower(), key, body))
        start = cursor

    return entries


def _parse_bibtex_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    pattern = re.compile(
        r"(?P<name>[A-Za-z][A-Za-z0-9_-]*)\s*=\s*(?P<value>\{(?:[^{}]|\{[^{}]*\})*\}|\".*?\"|[^,\n]+)",
        re.DOTALL,
    )
    for match in pattern.finditer(body):
        name = match.group("name").lower()
        value = match.group("value").strip().rstrip(",").strip()
        fields[name] = value
    return fields


def _extract_year(value: str) -> int | None:
    match = re.search(r"(19|20)\d{2}", value)
    if not match:
        return None
    return int(match.group(0))


def _build_reference_id(title: str, year: int | None) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-") or "reference"
    return f"{base}-{year}" if year is not None else base
