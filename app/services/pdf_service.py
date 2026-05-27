from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.pdf import serialize_pdf_selection
from app.services.reference_service import ReferenceService
from app.services.workspace_service import WorkspaceService


class PdfService:
    def __init__(
        self,
        workspace_service: WorkspaceService,
        reference_service: ReferenceService,
    ) -> None:
        self.workspace_service = workspace_service
        self.reference_service = reference_service

    def open_pdf(self, workspace_root: str | Path, pdf_path: str | Path) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        resolved_pdf = self._resolve_workspace_pdf_path(workspace_context.workspace_root, pdf_path)
        if resolved_pdf is None:
            return self._failure(
                "PDF path must point to an existing .pdf file inside workspace/attachments or workspace/references."
            )

        return self._success(
            "PDF opened successfully.",
            pdf=self._build_pdf_payload(workspace_context.workspace_root, resolved_pdf),
        )

    def open_reference_pdf(self, workspace_root: str | Path, reference_id: str) -> dict[str, object]:
        reference_result = self.reference_service.get_reference(workspace_root, reference_id)
        if not reference_result["success"]:
            return reference_result

        reference = reference_result["data"]["reference"]
        pdf_path = reference.get("pdf_path")
        if not pdf_path:
            return self._failure(f"Reference does not have a bound PDF: {reference_id}")

        open_result = self.open_pdf(workspace_root, str(pdf_path))
        if not open_result["success"]:
            return open_result

        return self._success(
            "Reference PDF opened successfully.",
            reference=reference,
            pdf=open_result["data"]["pdf"],
        )

    def create_annotation(
        self,
        workspace_root: str | Path,
        reference_id: str,
        selection_payload: dict[str, object],
    ) -> dict[str, object]:
        reference_result = self.reference_service.get_reference(workspace_root, reference_id)
        if not reference_result["success"]:
            return reference_result

        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        reference = reference_result["data"]["reference"]
        pdf_path = reference.get("pdf_path")
        if not pdf_path:
            return self._failure(f"Reference does not have a bound PDF: {reference_id}")

        open_result = self.open_pdf(workspace_root, str(pdf_path))
        if not open_result["success"]:
            return open_result

        try:
            selection = serialize_pdf_selection(selection_payload)
        except ValueError as error:
            return self._failure(str(error))

        manifest = self._load_annotations_manifest(workspace_context.agni_dir)
        annotation = {
            "annotation_id": f"annotation-{uuid4().hex[:12]}",
            "reference_id": reference_id,
            "pdf_path": str(pdf_path),
            "text": selection["text"],
            "page_number": selection["page_number"],
            "page_label": selection["page_label"],
            "rects": list(selection["rects"]),
            "comment": selection["comment"],
            "color": selection["color"],
            "created_at": datetime.now().isoformat(),
        }
        manifest["annotations"].append(annotation)
        self._save_annotations_manifest(workspace_context.agni_dir, manifest)
        self._sync_annotation_record(workspace_context, annotation)

        return self._success(
            "PDF annotation captured successfully.",
            reference=reference,
            pdf=open_result["data"]["pdf"],
            annotation=annotation,
        )

    def list_reference_annotations(self, workspace_root: str | Path, reference_id: str) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        manifest = self._load_annotations_manifest(workspace_context.agni_dir)
        annotations = tuple(
            item for item in manifest["annotations"] if item.get("reference_id") == reference_id
        )
        return self._success(
            "PDF annotations listed successfully.",
            reference_id=reference_id,
            annotations=annotations,
        )

    def _resolve_workspace_pdf_path(self, workspace_root: Path, pdf_path: str | Path) -> Path | None:
        candidate = Path(pdf_path)
        if not candidate.is_absolute():
            candidate = workspace_root / candidate

        resolved_workspace = workspace_root.resolve()
        resolved_pdf = candidate.resolve()
        try:
            relative = resolved_pdf.relative_to(resolved_workspace)
        except ValueError:
            return None

        if resolved_pdf.suffix.lower() != ".pdf":
            return None
        if not resolved_pdf.exists() or not resolved_pdf.is_file():
            return None
        if not relative.parts or relative.parts[0] not in {"attachments", "references"}:
            return None
        return resolved_pdf

    def _build_pdf_payload(self, workspace_root: Path, pdf_path: Path) -> dict[str, object]:
        return {
            "title": pdf_path.name,
            "file_path": str(pdf_path),
            "relative_path": str(pdf_path.relative_to(workspace_root)),
            "file_size": pdf_path.stat().st_size,
            "page_count": None,
        }

    def _annotations_manifest_path(self, agni_dir: Path) -> Path:
        return agni_dir / "pdf_annotations_manifest.json"

    def _load_annotations_manifest(self, agni_dir: Path) -> dict[str, list[dict[str, object]]]:
        manifest_path = self._annotations_manifest_path(agni_dir)
        if not manifest_path.exists():
            return {"annotations": []}

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"annotations": []}

        annotations = data.get("annotations", [])
        if not isinstance(annotations, list):
            annotations = []
        return {"annotations": annotations}

    def _save_annotations_manifest(
        self,
        agni_dir: Path,
        manifest: dict[str, list[dict[str, object]]],
    ) -> None:
        self._annotations_manifest_path(agni_dir).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _success(self, message: str, **data: object) -> dict[str, object]:
        return {
            "success": True,
            "message": message,
            "data": data,
        }

    def _failure(self, message: str, **data: object) -> dict[str, object]:
        return {
            "success": False,
            "message": message,
            "data": data,
        }

    def _sync_annotation_record(self, workspace_context, annotation: dict[str, object]) -> None:
        with self.workspace_service.connect_workspace_database(workspace_context) as connection:
            connection.execute(
                """
                INSERT INTO pdf_annotations(
                    annotation_id, reference_id, pdf_path, text, page_number,
                    page_label, rects_json, comment, color, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(annotation_id) DO UPDATE SET
                    reference_id = excluded.reference_id,
                    pdf_path = excluded.pdf_path,
                    text = excluded.text,
                    page_number = excluded.page_number,
                    page_label = excluded.page_label,
                    rects_json = excluded.rects_json,
                    comment = excluded.comment,
                    color = excluded.color,
                    created_at = excluded.created_at
                """,
                (
                    annotation.get("annotation_id"),
                    annotation.get("reference_id"),
                    annotation.get("pdf_path"),
                    annotation.get("text"),
                    annotation.get("page_number"),
                    annotation.get("page_label"),
                    json.dumps(annotation.get("rects", []), ensure_ascii=False),
                    annotation.get("comment"),
                    annotation.get("color"),
                    annotation.get("created_at"),
                ),
            )
            connection.commit()
