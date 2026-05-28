from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable


class DatabaseInterface(ABC):
    @abstractmethod
    def connect(self):
        raise NotImplementedError

    @abstractmethod
    def query(self, sql: str, params: Iterable[Any] | None = None):
        raise NotImplementedError

    @abstractmethod
    def execute(self, sql: str, params: Iterable[Any] | None = None) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_all_references(self):
        raise NotImplementedError

    @abstractmethod
    def get_note_detail(self, note_id: str):
        raise NotImplementedError

    @abstractmethod
    def get_reference_detail(self, reference_id: str):
        raise NotImplementedError

    @abstractmethod
    def get_note_links(self, note_id: str):
        raise NotImplementedError


def fetch_all_references(db: DatabaseInterface):
    return db.get_all_references()


def fetch_note_detail(db: DatabaseInterface, note_id: str):
    return db.get_note_detail(note_id)


def fetch_reference_detail(db: DatabaseInterface, reference_id: str):
    return db.get_reference_detail(reference_id)


def fetch_note_links(db: DatabaseInterface, note_id: str):
    return db.get_note_links(note_id)


def connect_to_database(db_path: str | Path) -> DatabaseInterface:
    from .connection import DatabaseManager

    return DatabaseManager(db_path)
