from __future__ import annotations


def format_citation_token(
    reference: dict[str, object],
    annotation: dict[str, object] | None = None,
) -> str:
    reference_id = str(reference.get("reference_id") or "").strip()
    if not reference_id:
        raise ValueError("Reference id is required to format a citation token.")

    locator = _format_locator(annotation)
    return f"[@{reference_id}{locator}]"


def format_excerpt_block(
    excerpt_text: str,
    citation_token: str,
    *,
    reference_title: str | None = None,
    comment: str | None = None,
) -> str:
    cleaned_excerpt = excerpt_text.strip()
    if not cleaned_excerpt:
        raise ValueError("Excerpt text is required.")

    excerpt_lines = [f"> {line}" if line else ">" for line in cleaned_excerpt.splitlines()]
    body = "\n".join(excerpt_lines)

    footer_lines: list[str] = []
    if reference_title:
        footer_lines.append(f"Source: {reference_title}")
    footer_lines.append(citation_token)
    if comment:
        footer_lines.append(comment.strip())

    footer = "\n".join(footer_lines)
    return f"{body}\n>\n> {footer.replace(chr(10), chr(10) + '> ')}"


def _format_locator(annotation: dict[str, object] | None) -> str:
    if not annotation:
        return ""

    page_label = annotation.get("page_label")
    if page_label not in (None, ""):
        return f", p. {page_label}"

    page_number = annotation.get("page_number")
    if page_number not in (None, ""):
        return f", p. {page_number}"

    return ""
