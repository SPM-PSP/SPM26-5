from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .citation_service import CitationService
    from .link_service import LinkService
    from .note_service import NoteService
    from .pdf_service import PdfService
    from .reference_service import ReferenceService
    from .search_service import SearchService
    from .workspace_service import WorkspaceService

__all__ = [
    "CitationService",
    "LinkService",
    "NoteService",
    "PdfService",
    "ReferenceService",
    "SearchService",
    "WorkspaceService",
]


def __getattr__(name: str) -> Any:
    if name == "CitationService":
        from .citation_service import CitationService

        return CitationService
    if name == "LinkService":
        from .link_service import LinkService

        return LinkService
    if name == "NoteService":
        from .note_service import NoteService

        return NoteService
    if name == "PdfService":
        from .pdf_service import PdfService

        return PdfService
    if name == "ReferenceService":
        from .reference_service import ReferenceService

        return ReferenceService
    if name == "SearchService":
        from .search_service import SearchService

        return SearchService
    if name == "WorkspaceService":
        from .workspace_service import WorkspaceService

        return WorkspaceService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
