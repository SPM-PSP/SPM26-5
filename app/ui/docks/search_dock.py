from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


SEARCH_CONTEXT_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class SearchDock(QDockWidget):
    result_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Search and Backlinks", parent)
        self.workspace_root: Path | None = None
        self.notes_dir: Path | None = None
        self.app_context = None

        self.setObjectName("search_dock")
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

        title = QLabel("Search and Relations", surface)
        title.setObjectName("section_label")
        root_layout.addWidget(title)

        self.tabs = QTabWidget(surface)
        self.tabs.addTab(self._build_search_page(), "Search")
        self.tabs.addTab(self._build_backlinks_page(), "Backlinks")
        root_layout.addWidget(self.tabs, 1)

        self.setWidget(surface)

    def _build_search_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit(page)
        self.search_input.setPlaceholderText("Search note titles and content...")
        self.search_button = QPushButton("Search", page)
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.search_button)
        layout.addLayout(search_row)

        self.search_results = QListWidget(page)
        self.search_results.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.search_results, 1)

        self.search_preview = QTextEdit(page)
        self.search_preview.setReadOnly(True)
        self.search_preview.setPlaceholderText("Select a search result to preview context")
        self.search_preview.setMaximumHeight(130)
        layout.addWidget(self.search_preview)

        return page

    def _build_backlinks_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.backlink_hint = QLabel(
            "Open a note to see other notes that link to it.",
            page,
        )
        self.backlink_hint.setWordWrap(True)
        layout.addWidget(self.backlink_hint)

        self.backlink_list = QListWidget(page)
        self.backlink_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.backlink_list, 1)

        return page

    def _bind_signals(self) -> None:
        self.search_button.clicked.connect(self.perform_search)
        self.search_input.returnPressed.connect(self.perform_search)
        self.search_results.itemClicked.connect(self._show_search_preview)
        self.search_results.itemActivated.connect(self._emit_result_selected)
        self.backlink_list.itemActivated.connect(self._emit_result_selected)
        self.backlink_list.itemClicked.connect(self._show_backlink_preview)
        self.search_results.customContextMenuRequested.connect(self._show_result_context_menu)
        self.backlink_list.customContextMenuRequested.connect(self._show_backlink_context_menu)

    def bind_app_context(self, app_context) -> None:
        self.app_context = app_context

    def set_workspace(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root)
        self.notes_dir = self.workspace_root / "notes"
        self.perform_search()

    def focus_search(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.search_input.setFocus()
        self.search_input.selectAll()

    def perform_search(self) -> None:
        query = self.search_input.text().strip()
        self.search_results.clear()
        self.search_preview.clear()

        if self.workspace_root is None:
            self._add_disabled_item(self.search_results, "Workspace is not ready.")
            return

        if not query:
            self._add_disabled_item(self.search_results, "Type a keyword to start searching.")
            return

        controller = getattr(self.app_context, "search_controller", None)
        if controller is None:
            self._add_disabled_item(self.search_results, "Search controller is not available.")
            return

        result = controller.search_notes(self.workspace_root, query)
        if not result["success"]:
            self._add_disabled_item(self.search_results, str(result["message"]))
            return

        entries = tuple(result["data"].get("results", ()))
        if not entries:
            self._add_disabled_item(self.search_results, "No matching notes found.")
            return

        for entry in entries:
            note_path = Path(str(entry.get("file_path") or ""))
            item = QListWidgetItem(str(entry.get("title") or note_path.stem))
            item.setToolTip(str(note_path))
            item.setData(Qt.ItemDataRole.UserRole, str(note_path))
            item.setData(SEARCH_CONTEXT_ROLE, str(entry.get("context") or ""))
            self.search_results.addItem(item)

    def update_backlinks(self, current_note_path: str | Path | None, title: str) -> None:
        self.backlink_list.clear()
        self.search_preview.clear()

        if self.workspace_root is None or not title:
            self._add_disabled_item(self.backlink_list, "No backlinks available.")
            return

        controller = getattr(self.app_context, "search_controller", None)
        if controller is None:
            self._add_disabled_item(self.backlink_list, "Backlink controller is not available.")
            return

        result = controller.get_backlinks(
            self.workspace_root,
            title=title,
            current_note_path=current_note_path,
        )
        if not result["success"]:
            self._add_disabled_item(self.backlink_list, str(result["message"]))
            return

        entries = tuple(result["data"].get("backlinks", ()))
        if not entries:
            self._add_disabled_item(self.backlink_list, "No backlinks available.")
            return

        for entry in entries:
            note_path = Path(str(entry.get("file_path") or ""))
            item = QListWidgetItem(str(entry.get("source_title") or note_path.stem))
            item.setToolTip(str(note_path))
            item.setData(Qt.ItemDataRole.UserRole, str(note_path))
            item.setData(SEARCH_CONTEXT_ROLE, str(entry.get("context") or ""))
            self.backlink_list.addItem(item)

    def _show_search_preview(self, item: QListWidgetItem) -> None:
        self.search_preview.setPlainText(str(item.data(SEARCH_CONTEXT_ROLE) or ""))

    def _show_backlink_preview(self, item: QListWidgetItem) -> None:
        self.search_preview.setPlainText(str(item.data(SEARCH_CONTEXT_ROLE) or ""))

    def _emit_result_selected(self, item: QListWidgetItem) -> None:
        note_path = item.data(Qt.ItemDataRole.UserRole)
        if note_path:
            self.result_selected.emit(Path(str(note_path)))

    def _show_result_context_menu(self, position) -> None:
        self._show_note_context_menu(self.search_results, position)

    def _show_backlink_context_menu(self, position) -> None:
        self._show_note_context_menu(self.backlink_list, position)

    def _show_note_context_menu(self, list_widget: QListWidget, position) -> None:
        item = list_widget.itemAt(position)
        if item is None or not item.data(Qt.ItemDataRole.UserRole):
            return

        note_path = Path(str(item.data(Qt.ItemDataRole.UserRole)))
        menu = QMenu(self)
        open_action = QAction("Open", menu)
        copy_path_action = QAction("Copy Path", menu)
        menu.addAction(open_action)
        menu.addAction(copy_path_action)

        open_action.triggered.connect(lambda: self.result_selected.emit(note_path))
        copy_path_action.triggered.connect(lambda: QApplication.clipboard().setText(str(note_path)))
        menu.exec(list_widget.mapToGlobal(position))

    def _add_disabled_item(self, list_widget: QListWidget, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        list_widget.addItem(item)
