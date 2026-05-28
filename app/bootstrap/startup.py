from pathlib import Path

from app.bootstrap.app_context import AppContext
from app.bootstrap.config import AppConfig
from app.bootstrap.exceptions import BootstrapError
from app.controllers.knowledge_controller import KnowledgeController
from app.controllers.note_controller import NoteController
from app.controllers.reference_controller import ReferenceController
from app.controllers.search_controller import SearchController
from app.controllers.workspace_controller import WorkspaceController
from app.services.knowledge_model_service import KnowledgeModelService
from app.services.link_service import LinkService
from app.services.note_service import NoteService
from app.services.reference_service import ReferenceService
from app.services.search_service import SearchService
from app.services.workspace_service import WorkspaceService
from database.tool import connect_to_database


def bootstrap_workspace(workspace_root: str | Path, app_config: AppConfig | None = None) -> AppContext:
    config = app_config or AppConfig()
    workspace_service = WorkspaceService(config)
    workspace_controller = WorkspaceController(workspace_service)
    workspace_result = workspace_controller.open_workspace(workspace_root)
    if not workspace_result["success"]:
        raise BootstrapError(str(workspace_result["message"]))

    workspace_context = workspace_result["data"]["workspace_context"]
    note_service = NoteService(workspace_service)
    reference_service = ReferenceService(workspace_service)
    link_service = LinkService(workspace_service)
    search_service = SearchService(workspace_service)
    knowledge_model_service = KnowledgeModelService(workspace_service)

    return AppContext(
        workspace_root=workspace_context.workspace_root,
        db_path=workspace_context.database_path,
        workspace_context=workspace_context,
        database=connect_to_database(workspace_context.database_path),
        workspace_controller=workspace_controller,
        note_service=note_service,
        search_service=search_service,
        reference_service=reference_service,
        link_service=link_service,
        knowledge_model_service=knowledge_model_service,
        note_controller=NoteController(note_service),
        search_controller=SearchController(search_service, link_service),
        reference_controller=ReferenceController(reference_service),
        knowledge_controller=KnowledgeController(knowledge_model_service),
    )


def bootstrap_app(workspace_root: str | Path) -> tuple[AppConfig, AppContext]:
    app_config = AppConfig()
    app_context = bootstrap_workspace(workspace_root, app_config)
    return app_config, app_context
