from dataclasses import dataclass


@dataclass(slots=True)
class WorkspaceDTO:
    root_path: str
    notes_path: str
    attachments_path: str
    exports_path: str
    db_path: str


@dataclass(slots=True)
class WorkspaceStatsDTO:
    note_count: int = 0
    attachment_count: int = 0