from __future__ import annotations

from pathlib import Path

from app.services.citation_service import CitationService


class CitationController:
    def __init__(self, citation_service: CitationService) -> None:
        self.citation_service = citation_service

    def capture_annotation(
        self,
        workspace_root: str | Path,
        reference_id: str,
        selection_payload: dict[str, object],
    ) -> dict[str, object]:
        return self.citation_service.capture_annotation(workspace_root, reference_id, selection_payload)

    def insert_citation_token(
        self,
        workspace_root: str | Path,
        reference_id: str,
        note_path: str | Path,
        *,
        selection_payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return self.citation_service.insert_citation_token(
            workspace_root,
            reference_id,
            note_path,
            selection_payload=selection_payload,
        )

    def append_excerpt_to_note(
        self,
        workspace_root: str | Path,
        reference_id: str,
        note_path: str | Path,
        selection_payload: dict[str, object],
    ) -> dict[str, object]:
        return self.citation_service.append_excerpt_to_note(
            workspace_root,
            reference_id,
            note_path,
            selection_payload,
        )

    def list_citations(
        self,
        workspace_root: str | Path,
        *,
        reference_id: str | None = None,
        note_path: str | Path | None = None,
    ) -> dict[str, object]:
        return self.citation_service.list_citations(
            workspace_root,
            reference_id=reference_id,
            note_path=note_path,
        )
