from __future__ import annotations

import sqlite3


PRAGMAS = (
    "PRAGMA foreign_keys=ON;",
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA temp_store=MEMORY;",
)


def apply_pragmas(connection: sqlite3.Connection) -> None:
    for pragma in PRAGMAS:
        connection.execute(pragma)
