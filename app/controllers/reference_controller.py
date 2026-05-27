from __future__ import annotations

from pathlib import Path

from app.services.reference_service import ReferenceService


class ReferenceController:
    def __init__(self, reference_service: ReferenceService) -> None:
        self.reference_service = reference_service

    def create_reference(self, workspace_root: str | Path, payload: dict[str, object]) -> dict[str, object]:
        return self.reference_service.create_reference(workspace_root, payload)

    def list_references(self, workspace_root: str | Path) -> dict[str, object]:
        return self.reference_service.list_references(workspace_root)

    def get_reference(self, workspace_root: str | Path, reference_id: str) -> dict[str, object]:
        return self.reference_service.get_reference(workspace_root, reference_id)

    def bind_pdf(
        self,
        workspace_root: str | Path,
        reference_id: str,
        pdf_path: str | Path,
    ) -> dict[str, object]:
        return self.reference_service.bind_pdf(workspace_root, reference_id, pdf_path)

    def import_reference_file(self, workspace_root: str | Path, import_path: str | Path) -> dict[str, object]:
        return self.reference_service.import_reference_file(workspace_root, import_path)
