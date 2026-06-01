from __future__ import annotations

from pathlib import Path

from app.services.pdf_service import PdfService


class PdfController:
    def __init__(self, pdf_service: PdfService) -> None:
        self.pdf_service = pdf_service

    def open_pdf(self, workspace_root: str | Path, pdf_path: str | Path) -> dict[str, object]:
        return self.pdf_service.open_pdf(workspace_root, pdf_path)

    def open_reference_pdf(self, workspace_root: str | Path, reference_id: str) -> dict[str, object]:
        return self.pdf_service.open_reference_pdf(workspace_root, reference_id)

    def create_annotation(
        self,
        workspace_root: str | Path,
        reference_id: str,
        selection_payload: dict[str, object],
    ) -> dict[str, object]:
        return self.pdf_service.create_annotation(workspace_root, reference_id, selection_payload)

    def list_reference_annotations(self, workspace_root: str | Path, reference_id: str) -> dict[str, object]:
        return self.pdf_service.list_reference_annotations(workspace_root, reference_id)

    def delete_annotation(self, workspace_root: str | Path, annotation_id: str) -> dict[str, object]:
        return self.pdf_service.delete_annotation(workspace_root, annotation_id)
