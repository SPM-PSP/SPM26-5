from __future__ import annotations

from pathlib import Path

from app.services.knowledge_model_service import KnowledgeModelService


class KnowledgeController:
    def __init__(self, knowledge_model_service: KnowledgeModelService) -> None:
        self.knowledge_model_service = knowledge_model_service

    def get_knowledge_model(self, workspace_root: str | Path) -> dict[str, object]:
        return self.knowledge_model_service.get_knowledge_model(workspace_root)

    def assign_object_to_planet(
        self,
        workspace_root: str | Path,
        *,
        object_kind: str,
        object_key: str,
        planet: str,
    ) -> dict[str, object]:
        return self.knowledge_model_service.assign_object_to_planet(
            workspace_root,
            object_kind=object_kind,
            object_key=object_key,
            planet=planet,
        )
