from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .app_controller import AppController
    from .citation_controller import CitationController
    from .note_controller import NoteController
    from .pdf_controller import PdfController
    from .reference_controller import ReferenceController
    from .search_controller import SearchController
    from .workspace_controller import WorkspaceController

__all__ = [
    "AppController",
    "CitationController",
    "NoteController",
    "PdfController",
    "ReferenceController",
    "SearchController",
    "WorkspaceController",
]


def __getattr__(name: str) -> Any:
    if name == "AppController":
        from .app_controller import AppController

        return AppController
    if name == "CitationController":
        from .citation_controller import CitationController

        return CitationController
    if name == "NoteController":
        from .note_controller import NoteController

        return NoteController
    if name == "PdfController":
        from .pdf_controller import PdfController

        return PdfController
    if name == "ReferenceController":
        from .reference_controller import ReferenceController

        return ReferenceController
    if name == "SearchController":
        from .search_controller import SearchController

        return SearchController
    if name == "WorkspaceController":
        from .workspace_controller import WorkspaceController

        return WorkspaceController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
