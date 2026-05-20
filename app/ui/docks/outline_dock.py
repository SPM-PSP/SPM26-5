from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


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

    def _build_pdf_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.pdf_hint = QLabel("PDF 面板用于后续接入预览、页码跳转和文献引用。", page)
        self.pdf_hint.setWordWrap(True)
        layout.addWidget(self.pdf_hint)

        self.pdf_list = QListWidget(page)
        layout.addWidget(self.pdf_list, 1)

        return page

    def _bind_signals(self) -> None:
        self.outline_tree.itemActivated.connect(self._emit_heading_selected)
        self.outline_tree.itemClicked.connect(self._emit_heading_selected)
        self.pdf_list.itemActivated.connect(self._emit_pdf_selected)
        self.pdf_list.itemClicked.connect(self._emit_pdf_selected)

    def set_workspace(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root)
        self.refresh_pdfs()

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

    def _add_disabled_pdf_item(self, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.pdf_list.addItem(item)
