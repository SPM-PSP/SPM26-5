from __future__ import annotations

import sqlite3
from pathlib import Path

from .migrations import migrate
from .pragmas import apply_pragmas


class DatabaseManager:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).expanduser().resolve()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            self.db_path.touch()
        with self.get_connection() as connection:
            migrate(connection)

    def get_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        apply_pragmas(connection)
        return connection
