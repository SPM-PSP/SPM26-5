from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.services.citation_formatter import format_citation_token, format_excerpt_block
from app.services.note_service import NoteService
from app.services.pdf_service import PdfService
from app.services.reference_service import ReferenceService
from app.services.workspace_service import WorkspaceService


class CitationService:
    def __init__(
        self,
        workspace_service: WorkspaceService,
        note_service: NoteService,
        pdf_service: PdfService,
        reference_service: ReferenceService,
    ) -> None:
        self.workspace_service = workspace_service
        self.note_service = note_service
        self.pdf_service = pdf_service
        self.reference_service = reference_service

    def capture_annotation(
        self,
        workspace_root: str | Path,
        reference_id: str,
        selection_payload: dict[str, object],
    ) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        annotation_result = self.pdf_service.create_annotation(
            workspace_root,
            reference_id,
            selection_payload,
        )
        if not annotation_result["success"]:
            return annotation_result

        reference = annotation_result["data"]["reference"]
        annotation = annotation_result["data"]["annotation"]
        citation = self._build_citation_record(reference, annotation)

        manifest = self._load_citations_manifest(workspace_context.agni_dir)
        manifest["citations"].append(citation)
        self._save_citations_manifest(workspace_context.agni_dir, manifest)

        return self._success(
            "Citation captured successfully.",
            reference=reference,
            annotation=annotation,
            citation=citation,
        )

    def insert_citation_token(
        self,
        workspace_root: str | Path,
        reference_id: str,
        note_path: str | Path,
        *,
        selection_payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        reference_result = self.reference_service.get_reference(workspace_root, reference_id)
        if not reference_result["success"]:
            return reference_result

        reference = reference_result["data"]["reference"]
        annotation = None
        citation = None

        if selection_payload is not None:
            capture_result = self.capture_annotation(workspace_root, reference_id, selection_payload)
            if not capture_result["success"]:
                return capture_result
            annotation = capture_result["data"]["annotation"]
            citation = capture_result["data"]["citation"]

        token = format_citation_token(reference, annotation)
        insert_result = self._append_markdown_to_note(
            workspace_root,
            note_path,
            token,
        )
        if not insert_result["success"]:
            return insert_result

        if citation is None:
            workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
            if not workspace_result["success"]:
                return workspace_result
            workspace_context = workspace_result["data"]["workspace_context"]
            citation = self._build_citation_record(reference, annotation)
            citation["note_path"] = insert_result["data"]["note"]["file_path"]
            manifest = self._load_citations_manifest(workspace_context.agni_dir)
            manifest["citations"].append(citation)
            self._save_citations_manifest(workspace_context.agni_dir, manifest)
        else:
            citation["note_path"] = insert_result["data"]["note"]["file_path"]
            self._update_citation_note_path(workspace_root, citation["citation_id"], citation["note_path"])

        return self._success(
            "Citation token inserted successfully.",
            reference=reference,
            annotation=annotation,
            citation=citation,
            note=insert_result["data"]["note"],
        )

    def append_excerpt_to_note(
        self,
        workspace_root: str | Path,
        reference_id: str,
        note_path: str | Path,
        selection_payload: dict[str, object],
    ) -> dict[str, object]:
        capture_result = self.capture_annotation(workspace_root, reference_id, selection_payload)
        if not capture_result["success"]:
            return capture_result

        reference = capture_result["data"]["reference"]
        annotation = capture_result["data"]["annotation"]
        citation = capture_result["data"]["citation"]
        excerpt_markdown = format_excerpt_block(
            str(annotation["text"]),
            str(citation["token"]),
            reference_title=str(reference.get("title") or ""),
            comment=str(annotation.get("comment") or "").strip() or None,
        )

        insert_result = self._append_markdown_to_note(
            workspace_root,
            note_path,
            excerpt_markdown,
        )
        if not insert_result["success"]:
            return insert_result

        citation["note_path"] = insert_result["data"]["note"]["file_path"]
        self._update_citation_note_path(workspace_root, citation["citation_id"], citation["note_path"])

        return self._success(
            "Excerpt appended to note successfully.",
            reference=reference,
            annotation=annotation,
            citation=citation,
            note=insert_result["data"]["note"],
        )

    def list_citations(
        self,
        workspace_root: str | Path,
        *,
        reference_id: str | None = None,
        note_path: str | Path | None = None,
    ) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        manifest = self._load_citations_manifest(workspace_context.agni_dir)
        citations = manifest["citations"]

        if reference_id is not None:
            citations = [
                item for item in citations if str(item.get("reference_id") or "") == reference_id
            ]

        if note_path is not None:
            expected_path = str(Path(note_path))
            citations = [
                item for item in citations if str(item.get("note_path") or "") == expected_path
            ]

        return self._success(
            "Citations listed successfully.",
            citations=tuple(citations),
        )

    def _append_markdown_to_note(
        self,
        workspace_root: str | Path,
        note_path: str | Path,
        markdown_block: str,
    ) -> dict[str, object]:
        open_result = self.note_service.open_note(workspace_root, note_path)
        if not open_result["success"]:
            return open_result

        note = open_result["data"]["note"]
        content = str(note["markdown_content"])
        suffix = "\n\n" if content.strip() else ""
        new_content = f"{content.rstrip()}{suffix}{markdown_block.strip()}\n"
        save_payload = {
            "title": note["title"],
            "file_path": note["file_path"],
            "markdown_content": new_content,
            "cursor_position": len(new_content),
            "version": note.get("version", 0),
        }
        return self.note_service.save_note(workspace_root, save_payload)

    def _citations_manifest_path(self, agni_dir: Path) -> Path:
        return agni_dir / "citations_manifest.json"

    def _load_citations_manifest(self, agni_dir: Path) -> dict[str, list[dict[str, object]]]:
        manifest_path = self._citations_manifest_path(agni_dir)
        if not manifest_path.exists():
            return {"citations": []}

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"citations": []}

        citations = data.get("citations", [])
        if not isinstance(citations, list):
            citations = []
        return {"citations": citations}

    def _save_citations_manifest(
        self,
        agni_dir: Path,
        manifest: dict[str, list[dict[str, object]]],
    ) -> None:
        self._citations_manifest_path(agni_dir).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _build_citation_record(
        self,
        reference: dict[str, object],
        annotation: dict[str, object] | None,
    ) -> dict[str, object]:
        return {
            "citation_id": f"citation-{uuid4().hex[:12]}",
            "reference_id": reference.get("reference_id"),
            "annotation_id": annotation.get("annotation_id") if annotation else None,
            "token": format_citation_token(reference, annotation),
            "page_label": annotation.get("page_label") if annotation else None,
            "note_path": None,
            "created_at": datetime.now().isoformat(),
        }

    def _update_citation_note_path(
        self,
        workspace_root: str | Path,
        citation_id: object,
        note_path: object,
    ) -> None:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return

        workspace_context = workspace_result["data"]["workspace_context"]
        manifest = self._load_citations_manifest(workspace_context.agni_dir)
        for item in manifest["citations"]:
            if item.get("citation_id") == citation_id:
                item["note_path"] = note_path
                break
        self._save_citations_manifest(workspace_context.agni_dir, manifest)

    def _success(self, message: str, **data: object) -> dict[str, object]:
        return {
            "success": True,
            "message": message,
            "data": data,
        }
