from __future__ import annotations

from typing import Any


def serialize_pdf_selection(selection_payload: dict[str, Any]) -> dict[str, object]:
    text = _normalize_text(selection_payload.get("text"))
    if not text:
        raise ValueError("Selection text is required.")

    page_number = _coerce_int(selection_payload.get("page_number"))
    page_label = str(selection_payload.get("page_label") or "").strip() or (
        str(page_number) if page_number is not None else None
    )

    rects_payload = selection_payload.get("rects", ())
    rects_list: list[dict[str, float]] = []
    for item in rects_payload:
        rect = _normalize_rect(item)
        if rect is not None:
            rects_list.append(rect)
    rects = tuple(rects_list)

    return {
        "text": text,
        "page_number": page_number,
        "page_label": page_label,
        "rects": rects,
        "comment": str(selection_payload.get("comment") or "").strip() or None,
        "color": str(selection_payload.get("color") or "").strip() or None,
    }


def _normalize_text(value: object) -> str:
    raw = str(value or "")
    return " ".join(raw.split())


def _coerce_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_rect(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None

    keys = ("x", "y", "width", "height")
    rect: dict[str, float] = {}
    for key in keys:
        raw = value.get(key)
        if raw in (None, ""):
            return None
        try:
            rect[key] = float(raw)
        except (TypeError, ValueError):
            return None
    return rect
