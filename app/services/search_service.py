from __future__ import annotations

from pathlib import Path

from app.services.workspace_service import WorkspaceService


class SearchService:
    def __init__(self, workspace_service: WorkspaceService) -> None:
        self.workspace_service = workspace_service

    def search_notes(self, workspace_root: str | Path, query: str) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        normalized_query = query.strip()
        if not normalized_query:
            return self._success("Search query is empty.", results=tuple())

        notes_dir = workspace_result["data"]["workspace_context"].notes_path
        lowered_query = normalized_query.casefold()
        results: list[dict[str, object]] = []

        for note_path in sorted(notes_dir.rglob("*.md"), key=lambda item: item.name.lower()):
            try:
                text = note_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            title = self._derive_title(text, note_path)
            haystack = f"{title}\n{note_path.stem}\n{text}".casefold()
            if lowered_query not in haystack:
                continue

            results.append(
                {
                    "title": title,
                    "file_path": str(note_path),
                    "relative_path": str(note_path.relative_to(notes_dir)),
                    "context": self._build_context(text, normalized_query),
                }
            )

        return self._success(
            "Search completed successfully.",
            query=normalized_query,
            results=tuple(results),
        )

    def _derive_title(self, text: str, note_path: Path) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:80]
        return note_path.stem

    def _build_context(self, text: str, query: str) -> str:
        lowered_text = text.casefold()
        index = lowered_text.find(query.casefold())
        if index < 0:
            return text[:220].strip()

        start = max(0, index - 80)
        end = min(len(text), index + len(query) + 140)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        return f"{prefix}{text[start:end].strip()}{suffix}"

    def _success(self, message: str, **data: object) -> dict[str, object]:
        return {
            "success": True,
            "message": message,
            "data": data,
        }
