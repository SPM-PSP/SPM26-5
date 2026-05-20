from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


RELATIVE_PATH_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class NoteListDock(QDockWidget):
    note_selected = Signal(object)
    delete_note_requested = Signal(object)
    new_note_requested = Signal()
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("资源库", parent)
        self.workspace_root: Path | None = None
        self.notes_dir: Path | None = None
        self.attachments_dir: Path | None = None

        self.setObjectName("note_list_dock")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._build_ui()
        self._bind_signals()

    def _build_ui(self) -> None:
        surface = QWidget(self)
        surface.setObjectName("dock_surface")
        root_layout = QVBoxLayout(surface)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        title = QLabel("工作区资源", surface)
        title.setObjectName("section_label")
        root_layout.addWidget(title)

        self.tabs = QTabWidget(surface)
        self.notes_page = self._build_notes_page()
        self.references_page = self._build_references_page()
        self.tabs.addTab(self.notes_page, "笔记")
        self.tabs.addTab(self.references_page, "文献")
        root_layout.addWidget(self.tabs, 1)

        self.setWidget(surface)

    def _build_notes_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.note_filter = QLineEdit(page)
        self.note_filter.setPlaceholderText("筛选笔记...")
        layout.addWidget(self.note_filter)

        button_row = QHBoxLayout()
        self.new_note_button = QPushButton("新建", page)
        self.delete_note_button = QPushButton("删除", page)
        self.delete_note_button.setObjectName("destructive_button")
        self.refresh_button = QPushButton("刷新", page)
        button_row.addWidget(self.new_note_button)
        button_row.addWidget(self.delete_note_button)
        button_row.addWidget(self.refresh_button)
        layout.addLayout(button_row)

        self.note_list = QListWidget(page)
        self.note_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.note_list, 1)

        return page

    def _build_references_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.reference_filter = QLineEdit(page)
        self.reference_filter.setPlaceholderText("筛选文献或 PDF...")
        layout.addWidget(self.reference_filter)

        self.reference_list = QListWidget(page)
        self.reference_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.reference_list, 1)

        return page

    def _bind_signals(self) -> None:
        self.note_filter.textChanged.connect(self._filter_notes)
        self.reference_filter.textChanged.connect(self._filter_references)
        self.note_list.itemActivated.connect(self._emit_note_selected)
        self.note_list.itemClicked.connect(self._emit_note_selected)
        self.new_note_button.clicked.connect(self.new_note_requested.emit)
        self.delete_note_button.clicked.connect(self._emit_delete_selected)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)

    def set_workspace(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root)
        self.notes_dir = self.workspace_root / "notes"
        self.attachments_dir = self.workspace_root / "attachments"
        self.refresh()

    def refresh(self) -> None:
        self.refresh_notes()
        self.refresh_references()

    def refresh_notes(self) -> None:
        self.note_list.clear()
        if self.notes_dir is None or not self.notes_dir.exists():
            self._add_disabled_item(self.note_list, "尚未发现 notes 目录")
            return

        note_paths = sorted(self.notes_dir.rglob("*.md"), key=lambda item: item.name.lower())
        if not note_paths:
            self._add_disabled_item(self.note_list, "暂无 Markdown 笔记")
            return

        for note_path in note_paths:
            rel_path = note_path.relative_to(self.notes_dir)
            item = QListWidgetItem(note_path.stem)
            item.setToolTip(str(note_path))
            item.setData(Qt.ItemDataRole.UserRole, str(note_path))
            item.setData(RELATIVE_PATH_ROLE, str(rel_path))
            self.note_list.addItem(item)

        self._filter_notes(self.note_filter.text())

    def refresh_references(self) -> None:
        self.reference_list.clear()
        if self.workspace_root is None:
            self._add_disabled_item(self.reference_list, "尚未打开工作区")
            return

        candidates: list[Path] = []
        for folder_name in ("references", "attachments"):
            folder = self.workspace_root / folder_name
            if folder.exists():
                candidates.extend(
                    path
                    for path in folder.rglob("*")
                    if path.is_file() and path.suffix.lower() in {".pdf", ".bib", ".ris"}
                )

        if not candidates:
            self._add_disabled_item(self.reference_list, "暂无文献文件")
            return

        for ref_path in sorted(candidates, key=lambda item: item.name.lower()):
            item = QListWidgetItem(ref_path.name)
            item.setToolTip(str(ref_path))
            item.setData(Qt.ItemDataRole.UserRole, str(ref_path))
            self.reference_list.addItem(item)

        self._filter_references(self.reference_filter.text())

    def select_note_path(self, note_path: str | Path) -> None:
        expected = str(note_path)
        for row in range(self.note_list.count()):
            item = self.note_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == expected:
                self.note_list.setCurrentItem(item)
                break

    def selected_note_path(self) -> Path | None:
        item = self.note_list.currentItem()
        if item is None:
            return None

        note_path = item.data(Qt.ItemDataRole.UserRole)
        return Path(note_path) if note_path else None

    def _filter_notes(self, query: str) -> None:
        self._filter_list(self.note_list, query)

    def _filter_references(self, query: str) -> None:
        self._filter_list(self.reference_list, query)

    def _filter_list(self, list_widget: QListWidget, query: str) -> None:
        normalized = query.strip().lower()
        for row in range(list_widget.count()):
            item = list_widget.item(row)
            haystack = f"{item.text()} {item.toolTip()}".lower()
            item.setHidden(bool(normalized) and normalized not in haystack)

    def _emit_note_selected(self, item: QListWidgetItem) -> None:
        note_path = item.data(Qt.ItemDataRole.UserRole)
        if note_path:
            self.note_selected.emit(Path(note_path))

    def _emit_delete_selected(self) -> None:
        note_path = self.selected_note_path()
        if note_path is not None:
            self.delete_note_requested.emit(note_path)

    def _add_disabled_item(self, list_widget: QListWidget, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        list_widget.addItem(item)
