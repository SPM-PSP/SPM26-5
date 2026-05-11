"""
app/ui/widgets/note_editor_widget.py

Markdown 编辑器控件。

职责：
1. 提供基础 Markdown 文本编辑区域；
2. 与 MarkdownDocument 同步文本、光标位置和修改状态；
3. 对外暴露最小 UI 接口，便于 note_controller / note_service 对接；
4. 不直接负责数据库写入、链接解析、引用入库和索引刷新。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPlainTextEdit,
    QLabel,
    QSizePolicy,
)

from app.editor.markdown_document import MarkdownDocument


class NoteEditorWidget(QWidget):
    """
    Markdown 编辑器控件。

    当前版本定位：
    - 阶段一：中央编辑器空壳，可输入文字；
    - 阶段二：支持笔记载入、保存状态同步；
    - 后续：再逐步补充补全、预览、标题提取、大纲联动等功能。
    """

    content_changed = Signal(str)
    cursor_position_changed = Signal(int)
    save_requested = Signal(dict)
    document_changed = Signal(object)
    status_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._document = MarkdownDocument.create_empty()
        self._is_loading = False

        self._build_ui()
        self._bind_signals()
        self._apply_document_to_view()

    def _build_ui(self) -> None:
        """构建基础界面。"""
        self.setObjectName("note_editor_widget")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.title_label = QLabel("未命名笔记", self)
        self.title_label.setObjectName("note_editor_title_label")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.editor = QPlainTextEdit(self)
        self.editor.setObjectName("note_editor_text_edit")
        self.editor.setPlaceholderText("请输入笔记内容...")
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setTabStopDistance(32)
        self.editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        font = QFont()
        font.setPointSize(11)
        self.editor.setFont(font)

        layout.addWidget(self.title_label)
        layout.addWidget(self.editor, 1)

    def _bind_signals(self) -> None:
        """绑定编辑器内部信号。"""
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.cursorPositionChanged.connect(self._on_cursor_position_changed)

    def _apply_document_to_view(self) -> None:
        """将当前 MarkdownDocument 状态应用到编辑器界面。"""
        self._is_loading = True
        try:
            self.title_label.setText(self._document.title or "未命名笔记")
            self.editor.setPlainText(self._document.get_text())

            cursor = self.editor.textCursor()
            cursor_position = max(0, min(self._document.cursor_position, len(self._document.get_text())))
            cursor.setPosition(cursor_position)
            self.editor.setTextCursor(cursor)

            self.status_changed.emit(self._document.session_status)
        finally:
            self._is_loading = False

    def _on_text_changed(self) -> None:
        """编辑器文本变化时同步到 MarkdownDocument。"""
        if self._is_loading:
            return

        text = self.editor.toPlainText()
        self._document.set_text(text, mark_dirty=True)

        self.content_changed.emit(text)
        self.document_changed.emit(self._document)
        self.status_changed.emit(self._document.session_status)

    def _on_cursor_position_changed(self) -> None:
        """编辑器光标变化时同步到 MarkdownDocument。"""
        if self._is_loading:
            return

        cursor = self.editor.textCursor()
        position = cursor.position()
        self._document.update_cursor_position(position)

        self.cursor_position_changed.emit(position)

    # -----------------------------
    # 对外基础接口
    # -----------------------------

    def get_document(self) -> MarkdownDocument:
        """返回当前绑定的 MarkdownDocument。"""
        return self._document

    def set_document(self, document: MarkdownDocument) -> None:
        """绑定新的 MarkdownDocument。"""
        self._document = document
        self._apply_document_to_view()
        self.document_changed.emit(self._document)

    def set_text(self, text: str) -> None:
        """直接设置编辑器文本，同时同步到文档对象。"""
        self._document.set_text(text, mark_dirty=False)
        self._apply_document_to_view()

    def get_text(self) -> str:
        """获取当前编辑器文本。"""
        return self.editor.toPlainText()

    def clear(self) -> None:
        """清空编辑器内容。"""
        self._document.clear()
        self._apply_document_to_view()
        self.document_changed.emit(self._document)

    def load_document(
        self,
        *,
        text: str,
        note_id: str | None = None,
        title: str | None = None,
        file_path: str | None = None,
        file_mtime: float | None = None,
        version: int | None = None,
    ) -> None:
        """
        从已有内容加载文档。
        打开笔记时可调用。
        """
        self._document.load_from_text(
            text=text,
            note_id=note_id,
            title=title,
            file_path=file_path,
            file_mtime=file_mtime,
            version=version,
        )
        self._apply_document_to_view()
        self.document_changed.emit(self._document)

    def load_empty_document(
        self,
        *,
        note_id: str | None = None,
        title: str = "",
        file_path: str | None = None,
    ) -> None:
        """加载空文档，适合新建笔记场景。"""
        self._document = MarkdownDocument.create_empty(
            note_id=note_id,
            title=title,
            file_path=file_path,
        )
        self._apply_document_to_view()
        self.document_changed.emit(self._document)

    def update_title(self, title: str) -> None:
        """更新文档标题显示。"""
        self._document.title = title or ""
        self.title_label.setText(self._document.title or "未命名笔记")
        self.document_changed.emit(self._document)

    def focus_editor(self) -> None:
        """将焦点切换到编辑器。"""
        self.editor.setFocus()

    def insert_text_at_cursor(self, text: str) -> None:
        """
        在当前光标位置插入文本。
        供后续引用插入、wikilink 插入等功能复用。
        """
        if not text:
            return

        cursor = self.editor.textCursor()
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)

        # textChanged 会自动同步 document，这里不用重复 set_text

    def replace_selection(self, text: str) -> None:
        """
        用指定文本替换当前选区。
        供补全候选插入等功能复用。
        """
        cursor = self.editor.textCursor()
        cursor.insertText(text)

    def get_cursor_position(self) -> int:
        """获取当前光标位置。"""
        return self.editor.textCursor().position()

    def set_cursor_position(self, position: int) -> None:
        """设置当前光标位置。"""
        cursor = self.editor.textCursor()
        position = max(0, min(position, len(self.editor.toPlainText())))
        cursor.setPosition(position)
        self.editor.setTextCursor(cursor)

        self._document.update_cursor_position(position)
        self.cursor_position_changed.emit(position)

    def is_dirty(self) -> bool:
        """返回当前文档是否已修改。"""
        return self._document.is_dirty

    def mark_saved(
        self,
        *,
        file_mtime: float | None = None,
        version: int | None = None,
    ) -> None:
        """保存成功后由外部调用，同步文档状态。"""
        self._document.mark_saved(file_mtime=file_mtime, version=version)
        self.status_changed.emit(self._document.session_status)
        self.document_changed.emit(self._document)

    def mark_save_failed(self) -> None:
        """保存失败后由外部调用，同步文档状态。"""
        self._document.mark_save_failed()
        self.status_changed.emit(self._document.session_status)
        self.document_changed.emit(self._document)

    def mark_external_modified(self) -> None:
        """标记当前文档被外部修改。"""
        self._document.mark_external_modified()
        self.status_changed.emit(self._document.session_status)
        self.document_changed.emit(self._document)

    def build_save_payload(self) -> dict:
        """
        构造最小保存载荷。
        供 note_controller / note_service.save_note() 使用。
        """
        document = self.get_document()
        return document.to_save_payload()

    def request_save(self) -> None:
        """
        主动发出保存请求信号。
        外层 controller 可监听该信号并调用后端保存逻辑。
        """
        self.save_requested.emit(self.build_save_payload())

    # -----------------------------
    # 可选扩展接口（后续阶段会用到）
    # -----------------------------

    def get_selected_text(self) -> str:
        """返回当前选中文本。"""
        return self.editor.textCursor().selectedText()

    def get_plain_text(self) -> str:
        """返回简化纯文本。"""
        return self._document.get_plain_text()

    def extract_headings(self):
        """提取当前文档标题结构。"""
        return self._document.extract_headings()