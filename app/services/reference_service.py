from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.references import import_reference_entries
from app.services.workspace_service import WorkspaceService


class ReferenceService:
    def __init__(self, workspace_service: WorkspaceService) -> None:
        self.workspace_service = workspace_service

    def create_reference(self, workspace_root: str | Path, payload: dict[str, object]) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        manifest = self._load_manifest(workspace_context.agni_dir)

        normalized = self._normalize_reference_payload(payload)
        if not normalized["title"]:
            return self._failure("Reference title is required.")

        reference_id = str(normalized["reference_id"] or self._generate_reference_id(normalized["title"]))
        record = {
            "reference_id": reference_id,
            "title": normalized["title"],
            "authors": normalized["authors"],
            "year": normalized["year"],
            "entry_type": normalized["entry_type"],
            "source_format": normalized["source_format"],
            "source_path": normalized["source_path"],
            "pdf_path": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        if any(item["reference_id"] == reference_id for item in manifest["references"]):
            return self._failure(f"Reference already exists: {reference_id}")

        manifest["references"].append(record)
        self._save_manifest(workspace_context.agni_dir, manifest)
        self._sync_reference_record(workspace_context, record)
        return self._success("Reference created successfully.", reference=record)

    def list_references(self, workspace_root: str | Path) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        manifest = self._load_manifest(workspace_context.agni_dir)
        return self._success(
            "References listed successfully.",
            references=tuple(manifest["references"]),
        )

    def get_reference(self, workspace_root: str | Path, reference_id: str) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        manifest = self._load_manifest(workspace_context.agni_dir)
        record = self._find_reference(manifest, reference_id)
        if record is None:
            return self._failure(f"Reference not found: {reference_id}")
        return self._success("Reference loaded successfully.", reference=record)

    def bind_pdf(
        self,
        workspace_root: str | Path,
        reference_id: str,
        pdf_path: str | Path,
    ) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        manifest = self._load_manifest(workspace_context.agni_dir)
        record = self._find_reference(manifest, reference_id)
        if record is None:
            return self._failure(f"Reference not found: {reference_id}")

        try:
            stored_pdf_path = self._store_pdf(workspace_context.attachments_path, pdf_path)
        except ValueError as error:
            return self._failure(str(error))
        except OSError as error:
            return self._failure(f"Failed to bind PDF: {error}")

        record["pdf_path"] = str(stored_pdf_path)
        record["updated_at"] = datetime.now().isoformat()
        self._save_manifest(workspace_context.agni_dir, manifest)
        self._sync_reference_record(workspace_context, record)
        return self._success("PDF bound successfully.", reference=record)

    def import_reference_file(self, workspace_root: str | Path, import_path: str | Path) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        source_path = Path(import_path).expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            return self._failure("Reference import file does not exist.")
        if source_path.suffix.lower() not in {".bib", ".ris"}:
            return self._failure("Only .bib and .ris import files are supported.")

        try:
            imported_entries = import_reference_entries(source_path)
        except (OSError, UnicodeDecodeError, ValueError) as error:
            return self._failure(f"Failed to import references: {error}")

        copied_source = self._copy_import_source(workspace_context.references_path, source_path)
        manifest = self._load_manifest(workspace_context.agni_dir)
        created: list[dict[str, object]] = []

        for entry in imported_entries:
            title = str(entry.get("title") or "").strip()
            reference_id = self._ensure_unique_reference_id(
                manifest,
                str(entry.get("reference_id") or self._generate_reference_id(title or "reference")),
            )
            record = {
                "reference_id": reference_id,
                "title": title or reference_id,
                "authors": tuple(entry.get("authors", ())),
                "year": entry.get("year"),
                "entry_type": entry.get("entry_type"),
                "source_format": entry.get("source_format"),
                "source_path": str(copied_source),
                "pdf_path": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            manifest["references"].append(record)
            created.append(record)
            self._sync_reference_record(workspace_context, record)

        self._save_manifest(workspace_context.agni_dir, manifest)
        return self._success(
            "Reference import completed successfully.",
            import_source=str(copied_source),
            references=tuple(created),
        )

    def _manifest_path(self, agni_dir: Path) -> Path:
        return agni_dir / "references_manifest.json"

    def _load_manifest(self, agni_dir: Path) -> dict[str, list[dict[str, object]]]:
        manifest_path = self._manifest_path(agni_dir)
        if not manifest_path.exists():
            return {"references": []}

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"references": []}

        references = data.get("references", [])
        if not isinstance(references, list):
            references = []
        return {"references": references}

    def _save_manifest(self, agni_dir: Path, manifest: dict[str, list[dict[str, object]]]) -> None:
        self._manifest_path(agni_dir).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _find_reference(
        self,
        manifest: dict[str, list[dict[str, object]]],
        reference_id: str,
    ) -> dict[str, object] | None:
        for record in manifest["references"]:
            if record.get("reference_id") == reference_id:
                return record
        return None

    def _normalize_reference_payload(self, payload: dict[str, object]) -> dict[str, object]:
        authors = payload.get("authors", ())
        if isinstance(authors, str):
            normalized_authors = tuple(part.strip() for part in authors.split(";") if part.strip())
        else:
            normalized_authors = tuple(str(part).strip() for part in authors if str(part).strip())

        year_value = payload.get("year")
        try:
            year = int(year_value) if year_value not in (None, "") else None
        except (TypeError, ValueError):
            year = None

        return {
            "reference_id": str(payload.get("reference_id") or "").strip() or None,
            "title": str(payload.get("title") or "").strip(),
            "authors": normalized_authors,
            "year": year,
            "entry_type": str(payload.get("entry_type") or "reference").strip(),
            "source_format": str(payload.get("source_format") or "manual").strip(),
            "source_path": (
                str(Path(payload["source_path"]).expanduser().resolve())
                if payload.get("source_path") not in (None, "")
                else None
            ),
        }

    def _generate_reference_id(self, title: str) -> str:
        base = "".join(char.lower() if char.isalnum() else "-" for char in title).strip("-")
        base = "-".join(part for part in base.split("-") if part) or "reference"
        return f"{base}-{uuid4().hex[:8]}"

    def _ensure_unique_reference_id(
        self,
        manifest: dict[str, list[dict[str, object]]],
        reference_id: str,
    ) -> str:
        existing_ids = {str(item.get("reference_id")) for item in manifest["references"]}
        candidate = reference_id
        while candidate in existing_ids:
            candidate = f"{reference_id}-{uuid4().hex[:6]}"
        return candidate

    def _copy_import_source(self, references_path: Path, source_path: Path) -> Path:
        target = references_path / source_path.name
        if target.exists():
            target = references_path / f"{source_path.stem}-{uuid4().hex[:6]}{source_path.suffix}"
        shutil.copy2(source_path, target)
        return target

    def _store_pdf(self, attachments_path: Path, pdf_path: str | Path) -> Path:
        source_path = Path(pdf_path).expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            raise ValueError("PDF file does not exist.")
        if source_path.suffix.lower() != ".pdf":
            raise ValueError("Only .pdf files can be bound to a reference.")

        target = attachments_path / source_path.name
        if source_path.resolve() == target.resolve():
            return target
        if target.exists():
            target = attachments_path / f"{source_path.stem}-{uuid4().hex[:6]}{source_path.suffix}"
        shutil.copy2(source_path, target)
        return target

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

    def _sync_reference_record(self, workspace_context, record: dict[str, object]) -> None:
        with self.workspace_service.connect_workspace_database(workspace_context) as connection:
            connection.execute(
                """
                INSERT INTO references_catalog(
                    reference_id, title, authors_json, year, entry_type,
                    source_format, source_path, pdf_path, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(reference_id) DO UPDATE SET
                    title = excluded.title,
                    authors_json = excluded.authors_json,
                    year = excluded.year,
                    entry_type = excluded.entry_type,
                    source_format = excluded.source_format,
                    source_path = excluded.source_path,
                    pdf_path = excluded.pdf_path,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    record.get("reference_id"),
                    record.get("title"),
                    json.dumps(list(record.get("authors", ()))),
                    record.get("year"),
                    record.get("entry_type"),
                    record.get("source_format"),
                    record.get("source_path"),
                    record.get("pdf_path"),
                    record.get("created_at"),
                    record.get("updated_at"),
                ),
            )
            connection.execute(
                """
                INSERT INTO object_planets(object_kind, object_key, planet, updated_at)
                VALUES ('reference', ?, 'Reading', datetime('now'))
                ON CONFLICT(object_kind, object_key) DO NOTHING
                """,
                (record.get("reference_id"),),
            )
            connection.commit()
