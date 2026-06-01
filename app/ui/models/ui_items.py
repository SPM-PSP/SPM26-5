from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable


@dataclass(slots=True)
class NoteListItem:
    title: str
    path: Path
    relative_path: str


@dataclass(slots=True)
class ReferenceListItem:
    title: str
    path: Path
    kind: str


@dataclass(slots=True)
class PdfDocumentItem:
    title: str
    path: Path
    page_count: int | None = None
    reference_key: str = ""


@dataclass(slots=True)
class PdfPageItem:
    page_number: int
    label: str = ""
    thumbnail_path: Path | None = None


@dataclass(slots=True)
class PdfAnnotationDraft:
    pdf_path: Path
    page_number: int
    kind: str
    text: str = ""
    citation_key: str = ""
    rects: tuple[dict[str, float], ...] = ()


@dataclass(slots=True)
class SearchResultItem:
    title: str
    path: Path
    context: str


@dataclass(slots=True)
class CommandItem:
    title: str
    callback: Callable[[], None]
    description: str = ""


class KnowledgeObjectKind(str, Enum):
    GALAXY = "galaxy"
    PLANET = "planet"
    STAR_NOTE = "star_note"
    STAR_REFERENCE = "star_reference"
    SATELLITE = "satellite"


@dataclass(slots=True)
class GalaxyItem:
    title: str
    workspace_root: Path
    description: str = "当前工作区知识体系"


@dataclass(slots=True)
class PlanetItem:
    title: str
    description: str
    filter_text: str = ""


@dataclass(slots=True)
class StarItem:
    title: str
    kind: KnowledgeObjectKind
    path: Path
    tags: tuple[str, ...] = ()
    planet: str = "未归类"


@dataclass(slots=True)
class SatelliteItem:
    title: str
    kind: str
    host_title: str
    line_number: int | None = None
    preview: str = ""
    object_id: str = ""


@dataclass(slots=True)
class KnowledgeSelection:
    kind: KnowledgeObjectKind
    title: str
    path: Path | None = None
    description: str = ""
    tags: tuple[str, ...] = ()
    satellites: tuple[SatelliteItem, ...] = ()


@dataclass(slots=True)
class KnowledgeGraphNode:
    kind: KnowledgeObjectKind
    title: str
    color: str
    path: Path | None = None
    description: str = ""
    planet: str = ""
    tags: tuple[str, ...] = ()
    satellites: tuple[SatelliteItem, ...] = ()
