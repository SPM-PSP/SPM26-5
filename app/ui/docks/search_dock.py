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
        super().__init__("搜索与反链", parent)
        self.workspace_root: Path | None = None
        self.notes_dir: Path | None = None
        self.search_controller = None

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

        title = QLabel("检索与关系", surface)
        title.setObjectName("section_label")
        root_layout.addWidget(title)

        self.tabs = QTabWidget(surface)
        self.tabs.addTab(self._build_search_page(), "搜索")
        self.tabs.addTab(self._build_backlinks_page(), "反链")
        root_layout.addWidget(self.tabs, 1)

        self.setWidget(surface)

    def _build_search_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit(page)
        self.search_input.setPlaceholderText("搜索笔记正文、标题、路径...")
        self.search_button = QPushButton("搜索", page)
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.search_button)
        layout.addLayout(search_row)

        self.search_results = QListWidget(page)
        self.search_results.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.search_results, 1)

        self.search_preview = QTextEdit(page)
        self.search_preview.setReadOnly(True)
        self.search_preview.setPlaceholderText("选中搜索结果后显示上下文")
        self.search_preview.setMaximumHeight(130)
        layout.addWidget(self.search_preview)

        return page

    def _build_backlinks_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.backlink_hint = QLabel("打开一篇笔记后，这里会显示引用它的其他笔记。", page)
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
        self.backlink_list.itemClicked.connect(self._emit_result_selected)
        self.search_results.customContextMenuRequested.connect(self._show_result_context_menu)
        self.backlink_list.customContextMenuRequested.connect(self._show_backlink_context_menu)

    def set_workspace(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root)
        self.notes_dir = self.workspace_root / "notes"
        self.perform_search()

    def set_search_controller(self, search_controller: object | None) -> None:
        self.search_controller = search_controller

    def focus_search(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.search_input.setFocus()
        self.search_input.selectAll()

    def perform_search(self) -> None:
        query = self.search_input.text().strip()
        self.search_results.clear()
        self.search_preview.clear()

        if self.notes_dir is None or not self.notes_dir.exists():
            self._add_disabled_item(self.search_results, "尚未发现 notes 目录")
            return

        if not query:
            self._add_disabled_item(self.search_results, "输入关键词后开始搜索")
            return

        if self._perform_backend_search(query):
            return

        results = []
        lowered_query = query.lower()
        for note_path in sorted(self.notes_dir.rglob("*.md"), key=lambda item: item.name.lower()):
            try:
                text = note_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            haystack = f"{note_path.stem}\n{text}".lower()
            if lowered_query in haystack:
                results.append((note_path, self._build_context(text, query)))

        if not results:
            self._add_disabled_item(self.search_results, "没有找到匹配内容")
            return

        for note_path, context in results:
            item = QListWidgetItem(note_path.stem)
            item.setToolTip(str(note_path))
            item.setData(Qt.ItemDataRole.UserRole, str(note_path))
            item.setData(SEARCH_CONTEXT_ROLE, context)
            self.search_results.addItem(item)

    def _perform_backend_search(self, query: str) -> bool:
        if self.search_controller is None or self.workspace_root is None:
            return False

        search_notes = getattr(self.search_controller, "search_notes", None)
        if search_notes is None:
            return False

        result = search_notes(self.workspace_root, query)
        if not isinstance(result, dict) or not result.get("success"):
            return False

        data = result.get("data", {})
        results = data.get("results", ()) if isinstance(data, dict) else ()
        if not results:
            self._add_disabled_item(self.search_results, "没有找到匹配内容")
            return True

        for raw_result in results:
            if not isinstance(raw_result, dict):
                continue

            payload = dict(raw_result)
            object_kind = str(payload.get("object_kind") or "note")
            title = str(payload.get("title") or payload.get("reference_id") or "未命名")
            path_value = (
                payload.get("file_path")
                or payload.get("pdf_path")
                or payload.get("display_path")
                or payload.get("source_path")
            )
            context = str(payload.get("context") or "")
            suffix = " · 文献" if object_kind == "reference" else ""
            item = QListWidgetItem(f"{title}{suffix}")
            if path_value:
                item.setToolTip(str(path_value))
            payload["path"] = str(path_value or "")
            item.setData(Qt.ItemDataRole.UserRole, payload)
            item.setData(SEARCH_CONTEXT_ROLE, context)
            self.search_results.addItem(item)

        if self.search_results.count() == 0:
            self._add_disabled_item(self.search_results, "没有找到匹配内容")
        return True

    def update_backlinks(self, current_note_path: str | Path | None, title: str) -> None:
        self.backlink_list.clear()
        if self.notes_dir is None or not self.notes_dir.exists() or not title:
            self._add_disabled_item(self.backlink_list, "暂无反向链接")
            return

        if self._update_backend_backlinks(current_note_path, title):
            return

        current_path = Path(current_note_path).resolve() if current_note_path else None
        patterns = (f"[[{title}]]", f"[[{title}|")
        matches = []

        for note_path in sorted(self.notes_dir.rglob("*.md"), key=lambda item: item.name.lower()):
            if current_path is not None and note_path.resolve() == current_path:
                continue
            try:
                text = note_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if any(pattern in text for pattern in patterns):
                matches.append(note_path)

        if not matches:
            self._add_disabled_item(self.backlink_list, "暂无反向链接")
            return

        for note_path in matches:
            item = QListWidgetItem(note_path.stem)
            item.setToolTip(str(note_path))
            item.setData(Qt.ItemDataRole.UserRole, str(note_path))
            self.backlink_list.addItem(item)

    def _update_backend_backlinks(
        self,
        current_note_path: str | Path | None,
        title: str,
    ) -> bool:
        if self.search_controller is None or self.workspace_root is None:
            return False

        get_backlinks = getattr(self.search_controller, "get_backlinks", None)
        if get_backlinks is None:
            return False

        result = get_backlinks(
            self.workspace_root,
            title=title,
            current_note_path=current_note_path,
        )
        if not isinstance(result, dict) or not result.get("success"):
            return False

        data = result.get("data", {})
        backlinks = data.get("backlinks", ()) if isinstance(data, dict) else ()
        if not backlinks:
            self._add_disabled_item(self.backlink_list, "暂无反向链接")
            return True

        for raw_backlink in backlinks:
            if not isinstance(raw_backlink, dict):
                continue
            payload = dict(raw_backlink)
            file_path = payload.get("file_path") or payload.get("source_path") or payload.get("path")
            title_text = str(
                payload.get("source_title")
                or payload.get("title")
                or (Path(str(file_path)).stem if file_path else "未命名")
            )
            item = QListWidgetItem(title_text)
            if file_path:
                item.setToolTip(str(file_path))
                payload["path"] = str(file_path)
            item.setData(Qt.ItemDataRole.UserRole, payload)
            item.setData(SEARCH_CONTEXT_ROLE, str(payload.get("context") or ""))
            self.backlink_list.addItem(item)

        if self.backlink_list.count() == 0:
            self._add_disabled_item(self.backlink_list, "暂无反向链接")
        return True

    def _show_search_preview(self, item: QListWidgetItem) -> None:
        self.search_preview.setPlainText(item.data(SEARCH_CONTEXT_ROLE) or "")

    def _emit_result_selected(self, item: QListWidgetItem) -> None:
        payload = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(payload, dict):
            self.result_selected.emit(payload)
        elif payload:
            self.result_selected.emit(Path(payload))

    def _show_result_context_menu(self, position) -> None:
        self._show_note_context_menu(self.search_results, position)

    def _show_backlink_context_menu(self, position) -> None:
        self._show_note_context_menu(self.backlink_list, position)

    def _show_note_context_menu(self, list_widget: QListWidget, position) -> None:
        item = list_widget.itemAt(position)
        if item is None or not item.data(Qt.ItemDataRole.UserRole):
            return

        payload = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(payload, dict):
            path_value = payload.get("file_path") or payload.get("path") or payload.get("pdf_path")
        else:
            path_value = payload
        if not path_value:
            return

        target_path = Path(str(path_value))
        menu = QMenu(self)
        open_action = QAction("打开", menu)
        copy_path_action = QAction("复制路径", menu)
        menu.addAction(open_action)
        menu.addAction(copy_path_action)

        open_action.triggered.connect(lambda: self.result_selected.emit(payload))
        copy_path_action.triggered.connect(lambda: QApplication.clipboard().setText(str(target_path)))
        menu.exec(list_widget.mapToGlobal(position))

    def _build_context(self, text: str, query: str) -> str:
        lowered_text = text.lower()
        index = lowered_text.find(query.lower())
        if index < 0:
            return text[:220].strip()

        start = max(0, index - 80)
        end = min(len(text), index + len(query) + 140)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        return f"{prefix}{text[start:end].strip()}{suffix}"

    def _add_disabled_item(self, list_widget: QListWidget, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        list_widget.addItem(item)
