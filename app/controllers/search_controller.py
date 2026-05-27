from __future__ import annotations

from pathlib import Path

from app.services.link_service import LinkService
from app.services.search_service import SearchService


class SearchController:
    def __init__(self, search_service: SearchService, link_service: LinkService) -> None:
        self.search_service = search_service
        self.link_service = link_service

    def search_notes(self, workspace_root: str | Path, query: str) -> dict[str, object]:
        return self.search_service.search_notes(workspace_root, query)

    def get_backlinks(
        self,
        workspace_root: str | Path,
        *,
        title: str,
        current_note_path: str | Path | None = None,
    ) -> dict[str, object]:
        return self.link_service.find_backlinks(
            workspace_root,
            target_title=title,
            current_note_path=current_note_path,
        )

    def get_note_links(self, workspace_root: str | Path, note_path: str | Path) -> dict[str, object]:
        return self.link_service.list_note_links(workspace_root, note_path)
