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
    QPushButton,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.models.ui_items import KnowledgeObjectKind, KnowledgeSelection


class OutlineDock(QDockWidget):
    heading_selected = Signal(int)
    pdf_selected = Signal(object)
    annotation_delete_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("文档导航", parent)
        self.workspace_root: Path | None = None
        self.reference_controller = None

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
        self.tabs.addTab(self._build_satellite_page(), "关联")
        self.tabs.addTab(self._build_tag_page(), "标签")
        root_layout.addWidget(self.tabs, 1)

        self.setWidget(surface)
        self._show_initial_empty_states()

    def _show_initial_empty_states(self) -> None:
        self.satellite_list.clear()
        self._add_disabled_list_item(
            self.satellite_list,
            "暂无关联对象\n可通过 [[双向链接]] 或 @文献引用建立关系",
        )
        self.tag_list.clear()
        self._add_disabled_list_item(self.tag_list, "暂无标签\n可在正文中使用 #标签 进行标记")

    def _build_outline_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.outline_tree = QTreeWidget(page)
        self.outline_tree.setHeaderHidden(True)
        self.outline_tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        layout.addWidget(self.outline_tree, 1)

        return page

    def _build_metadata_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.metadata_label = QLabel(self._metadata_empty_text(), page)
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
        self.satellite_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        layout.addWidget(self.satellite_list, 1)

        detail_title = QLabel("关联内容", page)
        detail_title.setObjectName("section_label")
        layout.addWidget(detail_title)

        self.satellite_detail = QTextEdit(page)
        self.satellite_detail.setReadOnly(True)
        self.satellite_detail.setPlaceholderText("点击上方关联条目查看内容。")
        self.satellite_detail.setMinimumHeight(120)
        layout.addWidget(self.satellite_detail, 1)

        self.delete_annotation_button = QPushButton("删除批注", page)
        self.delete_annotation_button.setObjectName("destructive_button")
        self.delete_annotation_button.setEnabled(False)
        layout.addWidget(self.delete_annotation_button)

        return page

    def _build_tag_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.tag_list = QListWidget(page)
        self.tag_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        layout.addWidget(self.tag_list, 1)

        return page

    def _build_pdf_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.pdf_hint = QLabel(
            "这里列出当前工作区 references/ 与 attachments/ 中的 PDF。"
            "双击文件会在中央 PDF 阅读器打开；阅读器负责翻页、划词、摘录和引用。"
            "此页只作为文献入口，不重复显示 PDF 正文。",
            page,
        )
        self.pdf_hint.setWordWrap(True)
        layout.addWidget(self.pdf_hint)

        self.pdf_list = QListWidget(page)
        self.pdf_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.pdf_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.pdf_list, 1)

        return page

    def _bind_signals(self) -> None:
        self.outline_tree.itemActivated.connect(self._emit_heading_selected)
        self.outline_tree.itemClicked.connect(self._emit_heading_selected)
        self.pdf_list.itemActivated.connect(self._emit_pdf_selected)
        self.pdf_list.itemClicked.connect(self._emit_pdf_selected)
        self.pdf_list.customContextMenuRequested.connect(self._show_pdf_context_menu)
        self.satellite_list.itemClicked.connect(self._show_satellite_detail)
        self.satellite_list.itemActivated.connect(self._show_satellite_detail)
        self.delete_annotation_button.clicked.connect(self._emit_delete_selected_annotation)

    def set_workspace(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root)
        self.refresh_pdfs()

    def set_reference_controller(self, reference_controller: object | None) -> None:
        self.reference_controller = reference_controller

    def set_object_context(self, selection: KnowledgeSelection | None) -> None:
        if selection is None:
            self.metadata_label.setText(self._metadata_empty_text())
            self.satellite_list.clear()
            self._add_disabled_list_item(
                self.satellite_list,
                "暂无关联对象\n可通过 [[双向链接]] 或 @文献引用建立关系",
            )
            self.satellite_detail.clear()
            self.satellite_detail.setPlaceholderText("点击上方关联条目查看内容。")
            self.delete_annotation_button.setEnabled(False)
            self.tag_list.clear()
            self._add_disabled_list_item(self.tag_list, "暂无标签\n可在正文中使用 #标签 进行标记")
            return

        kind_label = {
            KnowledgeObjectKind.GALAXY: "工作区",
            KnowledgeObjectKind.PLANET: "分类",
            KnowledgeObjectKind.STAR_NOTE: "笔记",
            KnowledgeObjectKind.STAR_REFERENCE: "文献",
            KnowledgeObjectKind.SATELLITE: "关联",
        }.get(selection.kind, selection.kind.value)
        path_text = str(selection.path) if selection.path is not None else "无文件路径"
        description = selection.description or "暂无描述"
        satellite_count = len(selection.satellites or ())
        tag_text = "、".join(selection.tags) if selection.tags else "暂无标签"
        self.metadata_label.setText(
            f"当前对象\n"
            f"类型：{kind_label}\n"
            f"名称：{selection.title}\n"
            f"路径：{path_text}\n\n"
            f"说明\n{description}\n\n"
            f"关联概览\n"
            f"关联数量：{satellite_count}\n"
            f"标签：{tag_text}\n\n"
            "使用提示\n"
            "1. 在左侧资源树或全屏星图中选择对象，这里会同步显示它的属性。\n"
            "2. 笔记的关联通常来自 Markdown 标题、引用、标签、摘录和批注。\n"
            "3. PDF 文献可在 PDF 页签或中央 PDF 阅读器中打开，用于划词摘录和插入引用。"
        )

        self.satellite_list.clear()
        if selection.satellites:
            for satellite in selection.satellites:
                line = f" · 第 {satellite.line_number} 行" if satellite.line_number else ""
                item = QListWidgetItem(f"{satellite.title}{line}")
                item.setToolTip(satellite.preview)
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    {
                        "title": satellite.title,
                        "kind": satellite.kind,
                        "host": satellite.host_title,
                        "line": satellite.line_number,
                        "preview": satellite.preview,
                        "object_id": satellite.object_id,
                    },
                )
                self.satellite_list.addItem(item)
            self.satellite_list.setCurrentRow(0)
            current_item = self.satellite_list.currentItem()
            if current_item is not None:
                self._show_satellite_detail(current_item)
        else:
            self._add_disabled_list_item(
                self.satellite_list,
                "暂无关联对象\n可通过 [[双向链接]] 或 @文献引用建立关系",
            )
            self.satellite_detail.clear()
            self.satellite_detail.setPlaceholderText("当前对象暂无关联内容。")
            self.delete_annotation_button.setEnabled(False)

        self.tag_list.clear()
        if selection.tags:
            for tag in selection.tags:
                self.tag_list.addItem(QListWidgetItem(tag))
        else:
            self._add_disabled_list_item(self.tag_list, "暂无标签\n可在正文中使用 #标签 进行标记")

    def _show_satellite_detail(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            self.satellite_detail.clear()
            self.satellite_detail.setPlaceholderText("当前关联没有可显示的内容。")
            self.delete_annotation_button.setEnabled(False)
            return

        annotation_id = str(data.get("object_id") or "")
        line = data.get("line")
        line_text = f"第 {line} 行\n" if line else ""
        preview = str(data.get("preview") or "").strip()
        if not preview:
            preview = "该关联暂无内容预览。"
        self.delete_annotation_button.setEnabled(
            data.get("kind") == "annotation" and bool(annotation_id)
        )

        self.satellite_detail.setPlainText(
            f"{data.get('title', '关联')}\n"
            f"类型：{data.get('kind', 'unknown')}\n"
            f"宿主：{data.get('host', '')}\n"
            f"{line_text}\n"
            f"{preview}"
        )

    def _emit_delete_selected_annotation(self) -> None:
        item = self.satellite_list.currentItem()
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return
        annotation_id = str(data.get("object_id") or "")
        if annotation_id:
            self.annotation_delete_requested.emit(annotation_id)

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
            item = QTreeWidgetItem(["暂无大纲内容\n在正文中使用 #、## 标题后会自动生成大纲"])
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.outline_tree.addTopLevelItem(item)

        self.outline_tree.expandAll()

    def refresh_pdfs(self) -> None:
        self.pdf_list.clear()
        if self.workspace_root is None:
            self._add_disabled_pdf_item("尚未打开工作区")
            return

        pdfs: list[tuple[Path, str]] = []
        seen: set[Path] = set()
        if self.reference_controller is not None:
            list_references = getattr(self.reference_controller, "list_references", None)
            if list_references is not None:
                result = list_references(self.workspace_root)
                if isinstance(result, dict) and result.get("success"):
                    data = result.get("data", {})
                    references = data.get("references", ()) if isinstance(data, dict) else ()
                    for reference in references:
                        if not isinstance(reference, dict):
                            continue
                        pdf_value = reference.get("pdf_path") or reference.get("source_path")
                        if not pdf_value:
                            continue
                        pdf_path = Path(str(pdf_value))
                        if not pdf_path.is_absolute():
                            pdf_path = self.workspace_root / pdf_path
                        if pdf_path.suffix.lower() != ".pdf" or not pdf_path.exists():
                            continue
                        resolved = pdf_path.resolve()
                        if resolved in seen:
                            continue
                        seen.add(resolved)
                        title = str(reference.get("title") or pdf_path.name)
                        pdfs.append((pdf_path, title))

        for folder_name in ("references", "attachments"):
            folder = self.workspace_root / folder_name
            if folder.exists():
                for path in folder.rglob("*.pdf"):
                    if not path.is_file():
                        continue
                    resolved = path.resolve()
                    if resolved in seen:
                        continue
                    seen.add(resolved)
                    pdfs.append((path, path.name))

        if not pdfs:
            self._add_disabled_pdf_item("暂无 PDF 附件\n可在文献管理中绑定或导入 PDF")
            return

        for pdf_path, title in sorted(pdfs, key=lambda item: item[1].lower()):
            item = QListWidgetItem(title)
            item.setToolTip(str(pdf_path))
            item.setData(Qt.ItemDataRole.UserRole, str(pdf_path))
            self.pdf_list.addItem(item)

    def focus_default(self) -> None:
        self.tabs.setCurrentIndex(0)

    def focus_pdf_list(self) -> None:
        self.tabs.setCurrentIndex(1)

    def focus_satellite_page(self) -> None:
        self.tabs.setCurrentIndex(3)

    def _metadata_empty_text(self) -> str:
        return (
            "暂无元数据\n"
            "文献条目可在导入后补全标题、作者、年份和 DOI\n\n"
            "选择左侧资源树或星图中的对象后，这里会显示工作区、分类、笔记、文献和关联信息。"
        )

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
