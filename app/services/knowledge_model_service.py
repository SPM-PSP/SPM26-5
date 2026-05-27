from __future__ import annotations

from pathlib import Path

from app.services.workspace_service import WorkspaceService


DEFAULT_PLANETS = ("Inbox", "Reading", "Research", "Unassigned")


class KnowledgeModelService:
    def __init__(self, workspace_service: WorkspaceService) -> None:
        self.workspace_service = workspace_service

    def get_knowledge_model(self, workspace_root: str | Path) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        workspace_context = workspace_result["data"]["workspace_context"]
        planets = {
            planet: {
                "title": planet,
                "description": self._planet_description(planet),
                "stars": [],
            }
            for planet in DEFAULT_PLANETS
        }

        with self.workspace_service.connect_workspace_database(workspace_context) as connection:
            note_rows = connection.execute(
                """
                SELECT note_id, relative_path, title, planet, content
                FROM notes
                ORDER BY title COLLATE NOCASE ASC
                """
            ).fetchall()
            reference_rows = connection.execute(
                """
                SELECT reference_id, title, pdf_path
                FROM references_catalog
                ORDER BY title COLLATE NOCASE ASC
                """
            ).fetchall()
            annotation_rows = connection.execute(
                """
                SELECT reference_id, annotation_id, text, page_label, comment
                FROM pdf_annotations
                ORDER BY created_at ASC
                """
            ).fetchall()
            citation_rows = connection.execute(
                """
                SELECT reference_id, citation_id, token, note_path
                FROM citations_catalog
                ORDER BY created_at ASC
                """
            ).fetchall()
            object_planets = {
                (str(row["object_kind"]), str(row["object_key"])): str(row["planet"])
                for row in connection.execute(
                    """
                    SELECT object_kind, object_key, planet
                    FROM object_planets
                    """
                ).fetchall()
            }

        annotations_by_reference: dict[str, list[dict[str, object]]] = {}
        for row in annotation_rows:
            annotations_by_reference.setdefault(str(row["reference_id"]), []).append(
                {
                    "title": f"Annotation p.{row['page_label']}" if row["page_label"] else "Annotation",
                    "kind": "annotation",
                    "preview": str(row["comment"] or row["text"] or "")[:120],
                }
            )

        citations_by_reference: dict[str, list[dict[str, object]]] = {}
        for row in citation_rows:
            citations_by_reference.setdefault(str(row["reference_id"]), []).append(
                {
                    "title": str(row["token"]),
                    "kind": "citation",
                    "preview": str(row["note_path"] or ""),
                }
            )

        for row in note_rows:
            note_path = workspace_context.notes_path / str(row["relative_path"])
            planet = str(row["planet"] or object_planets.get(("note", str(row["note_id"])), "Unassigned"))
            planets.setdefault(
                planet,
                {"title": planet, "description": self._planet_description(planet), "stars": []},
            )
            planets[planet]["stars"].append(
                {
                    "object_kind": "note",
                    "object_key": str(row["note_id"]),
                    "title": str(row["title"] or note_path.stem),
                    "path": str(note_path),
                    "tags": ("note", "markdown"),
                    "satellites": tuple(self._extract_note_satellites(note_path)),
                }
            )

        for row in reference_rows:
            reference_id = str(row["reference_id"])
            planet = object_planets.get(("reference", reference_id), "Reading")
            planets.setdefault(
                planet,
                {"title": planet, "description": self._planet_description(planet), "stars": []},
            )
            star_path = str(row["pdf_path"] or "")
            satellites = annotations_by_reference.get(reference_id, []) + citations_by_reference.get(reference_id, [])
            planets[planet]["stars"].append(
                {
                    "object_kind": "reference",
                    "object_key": reference_id,
                    "title": str(row["title"] or reference_id),
                    "path": star_path or None,
                    "tags": ("reference", "pdf" if row["pdf_path"] else "metadata"),
                    "satellites": tuple(satellites[:12]),
                }
            )

        ordered_planets = tuple(
            {
                "title": title,
                "description": planets[title]["description"],
                "stars": tuple(planets[title]["stars"]),
            }
            for title in DEFAULT_PLANETS
            if planets.get(title, {}).get("stars") or title in {"Inbox", "Reading", "Research"}
        )

        return self._success(
            "Knowledge model loaded successfully.",
            galaxy={
                "title": workspace_context.workspace_root.name,
                "workspace_root": str(workspace_context.workspace_root),
                "planets": ordered_planets,
            },
        )

    def assign_object_to_planet(
        self,
        workspace_root: str | Path,
        *,
        object_kind: str,
        object_key: str,
        planet: str,
    ) -> dict[str, object]:
        workspace_result = self.workspace_service.ensure_workspace_structure(workspace_root)
        if not workspace_result["success"]:
            return workspace_result

        if object_kind not in {"note", "reference"}:
            return self._failure("object_kind must be 'note' or 'reference'.")
        if not object_key.strip():
            return self._failure("object_key cannot be empty.")
        if not planet.strip():
            return self._failure("planet cannot be empty.")

        workspace_context = workspace_result["data"]["workspace_context"]
        with self.workspace_service.connect_workspace_database(workspace_context) as connection:
            connection.execute(
                """
                INSERT INTO object_planets(object_kind, object_key, planet, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(object_kind, object_key) DO UPDATE SET
                    planet = excluded.planet,
                    updated_at = excluded.updated_at
                """,
                (object_kind, object_key, planet),
            )
            if object_kind == "note":
                connection.execute(
                    "UPDATE notes SET planet = ? WHERE note_id = ?",
                    (planet, object_key),
                )
            connection.commit()

        return self._success(
            "Knowledge object assigned successfully.",
            object_kind=object_kind,
            object_key=object_key,
            planet=planet,
        )

    def _extract_note_satellites(self, note_path: Path) -> list[dict[str, object]]:
        if not note_path.exists():
            return []

        try:
            text = note_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        satellites: list[dict[str, object]] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                if title:
                    satellites.append(
                        {
                            "title": title[:60],
                            "kind": "heading",
                            "line_number": line_number,
                            "preview": f"Heading at line {line_number}",
                        }
                    )
            elif stripped.startswith(">") and len(satellites) < 12:
                satellites.append(
                    {
                        "title": "Quote",
                        "kind": "quote",
                        "line_number": line_number,
                        "preview": stripped[:120],
                    }
                )
            if len(satellites) >= 12:
                break
        return satellites

    def _planet_description(self, planet: str) -> str:
        descriptions = {
            "Inbox": "Capture and triage notes waiting for classification.",
            "Reading": "References, PDFs, and reading notes.",
            "Research": "Long-running topics, projects, and structured knowledge.",
            "Unassigned": "Objects that do not belong to a named planet yet.",
        }
        return descriptions.get(planet, "Knowledge planet.")

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
