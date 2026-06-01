from __future__ import annotations

import sqlite3
from pathlib import Path

from .connection import DatabaseManager


def initialize_database(db_path: str | Path) -> None:
    DatabaseManager(db_path).initialize()


def connect_to_database(db_path: str | Path) -> sqlite3.Connection:
    return DatabaseManager(db_path).get_connection()
