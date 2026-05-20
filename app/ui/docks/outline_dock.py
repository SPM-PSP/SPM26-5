from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.models.ui_items import KnowledgeObjectKind, KnowledgeSelection


class OutlineDock(QDockWidget):
    heading_selected = Signal(int)
    pdf_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("大纲与 PDF", parent)
        self.workspace_root: Path | None = None

        self.setObjectName("outline_dock")
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

        title = QLabel("文档导航", surface)
        title.setObjectName("section_label")
        root_layout.addWidget(title)

        self.tabs = QTabWidget(surface)
        self.tabs.addTab(self._build_outline_page(), "大纲")
        self.tabs.addTab(self._build_pdf_page(), "PDF")
        self.tabs.addTab(self._build_metadata_page(), "元数据")
        self.tabs.addTab(self._build_satellite_page(), "卫星")
        self.tabs.addTab(self._build_tag_page(), "标签")
        root_layout.addWidget(self.tabs, 1)

        self.setWidget(surface)

    def _build_outline_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.outline_tree = QTreeWidget(page)
        self.outline_tree.setHeaderHidden(True)
        layout.addWidget(self.outline_tree, 1)

        return page

    def _build_metadata_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.metadata_label = QLabel("选择模型树中的对象后显示元数据。", page)
        self.metadata_label.setObjectName("inspector_label")
        self.metadata_label.setWordWrap(True)
        self.metadata_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.metadata_label, 1)

        return page

    def _build_satellite_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.satellite_list = QListWidget(page)
        layout.addWidget(self.satellite_list, 1)

        return page

    def _build_tag_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.tag_list = QListWidget(page)
        layout.addWidget(self.tag_list, 1)

        return page

    def _build_pdf_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.pdf_hint = QLabel("PDF 面板用于后续接入预览、页码跳转和文献引用。", page)
        self.pdf_hint.setWordWrap(True)
        layout.addWidget(self.pdf_hint)

        self.pdf_list = QListWidget(page)
        self.pdf_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.pdf_list, 1)

        return page

    def _bind_signals(self) -> None:
        self.outline_tree.itemActivated.connect(self._emit_heading_selected)
        self.outline_tree.itemClicked.connect(self._emit_heading_selected)
        self.pdf_list.itemActivated.connect(self._emit_pdf_selected)
        self.pdf_list.itemClicked.connect(self._emit_pdf_selected)
        self.pdf_list.customContextMenuRequested.connect(self._show_pdf_context_menu)

    def set_workspace(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root)
        self.refresh_pdfs()

    def set_object_context(self, selection: KnowledgeSelection | None) -> None:
        if selection is None:
            self.metadata_label.setText("选择模型树中的对象后显示元数据。")
            self.satellite_list.clear()
            self.tag_list.clear()
            return

        kind_label = {
            KnowledgeObjectKind.GALAXY: "星系",
            KnowledgeObjectKind.PLANET: "行星",
            KnowledgeObjectKind.STAR_NOTE: "笔记星球",
            KnowledgeObjectKind.STAR_REFERENCE: "文献星球",
            KnowledgeObjectKind.SATELLITE: "卫星",
        }.get(selection.kind, selection.kind.value)
        path_text = str(selection.path) if selection.path is not None else "无文件路径"
        description = selection.description or "暂无描述"
        self.metadata_label.setText(
            f"类型：{kind_label}\n"
            f"名称：{selection.title}\n"
            f"路径：{path_text}\n\n"
            f"{description}"
        )

        self.satellite_list.clear()
        if selection.satellites:
            for satellite in selection.satellites:
                line = f" · 第 {satellite.line_number} 行" if satellite.line_number else ""
                item = QListWidgetItem(f"{satellite.title}{line}")
                item.setToolTip(satellite.preview)
                self.satellite_list.addItem(item)
        else:
            self._add_disabled_list_item(self.satellite_list, "暂无卫星条目")

        self.tag_list.clear()
        if selection.tags:
            for tag in selection.tags:
                self.tag_list.addItem(QListWidgetItem(tag))
        else:
            self._add_disabled_list_item(self.tag_list, "暂无标签")

    def set_headings(self, headings: Iterable[object]) -> None:
        self.outline_tree.clear()
        stack: list[QTreeWidgetItem] = []

        for heading in headings:
            level = int(getattr(heading, "level", 1))
            title = str(getattr(heading, "title", ""))
            line_number = int(getattr(heading, "line_number", 1))
            if not title:
                continue

            item = QTreeWidgetItem([f"{title}"])
            item.setToolTip(0, f"第 {line_number} 行")
            item.setData(0, Qt.ItemDataRole.UserRole, line_number)

            while len(stack) >= level:
                stack.pop()

            if stack:
                stack[-1].addChild(item)
            else:
                self.outline_tree.addTopLevelItem(item)

            stack.append(item)

        if self.outline_tree.topLevelItemCount() == 0:
            item = QTreeWidgetItem(["暂无标题"])
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.outline_tree.addTopLevelItem(item)

        self.outline_tree.expandAll()

    def refresh_pdfs(self) -> None:
        self.pdf_list.clear()
        if self.workspace_root is None:
            self._add_disabled_pdf_item("尚未打开工作区")
            return

        pdfs: list[Path] = []
        for folder_name in ("references", "attachments"):
            folder = self.workspace_root / folder_name
            if folder.exists():
                pdfs.extend(path for path in folder.rglob("*.pdf") if path.is_file())

        if not pdfs:
            self._add_disabled_pdf_item("暂无 PDF 文献")
            return

        for pdf_path in sorted(pdfs, key=lambda item: item.name.lower()):
            item = QListWidgetItem(pdf_path.name)
            item.setToolTip(str(pdf_path))
            item.setData(Qt.ItemDataRole.UserRole, str(pdf_path))
            self.pdf_list.addItem(item)

    def _emit_heading_selected(self, item: QTreeWidgetItem) -> None:
        line_number = item.data(0, Qt.ItemDataRole.UserRole)
        if line_number:
            self.heading_selected.emit(int(line_number))

    def _emit_pdf_selected(self, item: QListWidgetItem) -> None:
        pdf_path = item.data(Qt.ItemDataRole.UserRole)
        if pdf_path:
            self.pdf_selected.emit(Path(pdf_path))

    def _show_pdf_context_menu(self, position) -> None:
        item = self.pdf_list.itemAt(position)
        if item is None or not item.data(Qt.ItemDataRole.UserRole):
            return

        pdf_path = Path(item.data(Qt.ItemDataRole.UserRole))
        menu = QMenu(self)
        open_action = QAction("打开 PDF", menu)
        copy_path_action = QAction("复制路径", menu)
        menu.addAction(open_action)
        menu.addAction(copy_path_action)

        open_action.triggered.connect(lambda: self.pdf_selected.emit(pdf_path))
        copy_path_action.triggered.connect(lambda: QApplication.clipboard().setText(str(pdf_path)))
        menu.exec(self.pdf_list.mapToGlobal(position))

    def _add_disabled_pdf_item(self, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.pdf_list.addItem(item)

    def _add_disabled_list_item(self, list_widget: QListWidget, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        list_widget.addItem(item)
