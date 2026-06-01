from __future__ import annotations

import re
from collections import defaultdict

from app.ui.models.ui_items import SatelliteItem


SATELLITE_CATEGORY_LIMITS = {
    "heading": 6,
    "excerpt": 4,
    "annotation": 4,
    "citation": 5,
    "link": 5,
    "tag": 5,
}


def extract_markdown_satellites(
    text: str,
    host_title: str,
    *,
    max_items: int = 18,
) -> tuple[SatelliteItem, ...]:
    """Extract user-facing satellite objects from Markdown text.

    This is a UI-side interpretation only. Backend knowledge indexing can later
    replace it without changing the widgets that consume SatelliteItem.
    """

    satellites: list[SatelliteItem] = []
    seen: set[tuple[str, str, int | None]] = set()
    counts: defaultdict[str, int] = defaultdict(int)

    def add(title: str, kind: str, line_number: int | None, preview: str) -> None:
        clean_title = _compact(title).strip()
        clean_preview = _compact(preview).strip()
        if not clean_title:
            return
        if counts[kind] >= SATELLITE_CATEGORY_LIMITS.get(kind, 3):
            return
        key = (kind, clean_title, line_number)
        if key in seen:
            return
        seen.add(key)
        counts[kind] += 1
        satellites.append(
            SatelliteItem(
                title=clean_title[:42],
                kind=kind,
                host_title=host_title,
                line_number=line_number,
                preview=clean_preview[:160],
            )
        )

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            title = _strip_markdown_inline(heading_match.group(2))
            add(title, "heading", line_number, f"H{level} title, line {line_number}")

        if stripped.startswith(">"):
            excerpt = _strip_markdown_inline(stripped.lstrip("> "))
            add(excerpt or "Excerpt", "excerpt", line_number, stripped)

        if re.search(r"\b(TODO|NOTE|FIXME|QUESTION)\b|批注|评论|想法|疑问|问题", stripped, re.I):
            add(_strip_markdown_inline(stripped), "annotation", line_number, stripped)

        tag_source = re.sub(r"^#{1,6}\s+", "", stripped)
        for tag in re.findall(r"(?<!\S)#([\w\u4e00-\u9fff-]+)", tag_source):
            add(f"#{tag}", "tag", line_number, f"Tag #{tag}")

        for link_target in re.findall(r"\[\[([^\]|#]+)", stripped):
            title = link_target.strip().removesuffix(".md")
            add(title, "link", line_number, f"Wiki link to {title}")

        for bracket in re.findall(r"\[([^\]]*@[^\]]+)\]", stripped):
            for citation_key in re.findall(r"@([^\s,;\]]+)", bracket):
                add(f"@{citation_key}", "citation", line_number, f"Citation @{citation_key}")

        if len(satellites) >= max_items:
            break

    return tuple(satellites[:max_items])


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_markdown_inline(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    return _compact(cleaned)
