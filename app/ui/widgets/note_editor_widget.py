"""
app/ui/widgets/note_editor_widget.py

Markdown 编辑器控件。
阶段二增强版：
1. 提供基础 Markdown 文本编辑区域；
2. 与 MarkdownDocument 同步文本、标题、光标位置和修改状态；
3. 支持新建、打开、重载、保存请求构造；
4. 为 note_controller / note_service 提供更稳定的阶段二接口。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QMessageBox,
)

from app.editor.markdown_document import MarkdownDocument


class NoteEditorWidget(QWidget):
    """
    Markdown 编辑器控件。
    """

    content_changed = Signal(str)
    cursor_position_changed = Signal(int)
    save_requested = Signal(dict)
    document_changed = Signal(object)
    status_changed = Signal(str)
    title_changed = Signal(str)
    open_requested = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._document = MarkdownDocument.create_empty()
        self._is_loading = False
        self._read_only_mode = False

        self._build_ui()
        self._bind_signals()
        self._build_actions()
        self._apply_document_to_view()

    def _build_ui(self) -> None:
        """构建基础界面。"""
        self.setObjectName("note_editor_widget")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        title_hint_label = QLabel("标题：", self)
        title_hint_label.setObjectName("note_editor_title_hint_label")

        self.title_edit = QLineEdit(self)
        self.title_edit.setObjectName("note_editor_title_edit")
        self.title_edit.setPlaceholderText("请输入笔记标题")

        self.status_label = QLabel("idle", self)
        self.status_label.setObjectName("note_editor_status_label")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        header_layout.addWidget(title_hint_label)
        header_layout.addWidget(self.title_edit, 1)
        header_layout.addWidget(self.status_label)

        self.editor = QPlainTextEdit(self)
        self.editor.setObjectName("note_editor_text_edit")
        self.editor.setPlaceholderText("请输入笔记内容...")
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setTabStopDistance(32)
        self.editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        font = QFont()
        font.setPointSize(11)
        self.editor.setFont(font)

        layout.addLayout(header_layout)
        layout.addWidget(self.editor, 1)

    def _bind_signals(self) -> None:
        """绑定内部信号。"""
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.cursorPositionChanged.connect(self._on_cursor_position_changed)
        self.title_edit.textEdited.connect(self._on_title_edited)

    def _build_actions(self) -> None:
        """构建快捷键动作。"""
        self.save_action = QAction(self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self.request_save)
        self.addAction(self.save_action)

    def _apply_document_to_view(self) -> None:
        """将当前 MarkdownDocument 状态同步到界面。"""
        self._is_loading = True
        try:
            self.title_edit.setText(self._document.title or "")
            self.editor.setPlainText(self._document.get_text())
            self.status_label.setText(self._document.session_status)

            cursor = self.editor.textCursor()
            cursor_position = self._document.restore_cursor_position()
            cursor.setPosition(cursor_position)
            self.editor.setTextCursor(cursor)

            self.editor.setReadOnly(self._read_only_mode)

            self.status_changed.emit(self._document.session_status)
        finally:
            self._is_loading = False

    def _on_text_changed(self) -> None:
        """文本变化时同步文档状态。"""
        if self._is_loading:
            return

        text = self.editor.toPlainText()
        self._document.set_text(text, mark_dirty=True)

        self.status_label.setText(self._document.session_status)
        self.content_changed.emit(text)
        self.document_changed.emit(self._document)
        self.status_changed.emit(self._document.session_status)

    def _on_cursor_position_changed(self) -> None:
        """光标变化时同步文档状态。"""
        if self._is_loading:
            return

        position = self.editor.textCursor().position()
        self._document.update_cursor_position(position)

        self.cursor_position_changed.emit(position)

    def _on_title_edited(self, title: str) -> None:
        """标题变化时同步文档状态。"""
        if self._is_loading:
            return

        self._document.set_title(title)
        self.status_label.setText(self._document.session_status)

        self.title_changed.emit(title)
        self.document_changed.emit(self._document)
        self.status_changed.emit(self._document.session_status)

    # -----------------------------
    # 文档装载与创建
    # -----------------------------

    def new_note(
        self,
        *,
        note_id: str | None = None,
        title: str = "",
        file_path: str | None = None,
    ) -> None:
        """新建空白笔记。"""
        self._document = MarkdownDocument.create_empty(
            note_id=note_id,
            title=title,
            file_path=file_path,
        )
        self._apply_document_to_view()
        self.document_changed.emit(self._document)

    def open_note(
        self,
        *,
        text: str,
        note_id: str | None = None,
        title: str | None = None,
        file_path: str | None = None,
        file_mtime: float | None = None,
        version: int | None = None,
        cursor_position: int | None = None,
    ) -> None:
        """打开已有笔记。"""
        self._document.load_from_text(
            text=text,
            note_id=note_id,
            title=title,
            file_path=file_path,
            file_mtime=file_mtime,
            version=version,
            cursor_position=cursor_position,
        )
        self._apply_document_to_view()
        self.document_changed.emit(self._document)

    def reload_note(
        self,
        *,
        text: str,
        file_mtime: float | None = None,
        version: int | None = None,
    ) -> None:
        """重载当前笔记内容。"""
        self._document.load_from_text(
            text=text,
            note_id=self._document.note_id,
            title=self._document.title,
            file_path=self._document.file_path,
            file_mtime=file_mtime,
            version=version if version is not None else self._document.version,
            cursor_position=self._document.cursor_position,
        )
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
        """兼容之前接口。"""
        self.open_note(
            text=text,
            note_id=note_id,
            title=title,
            file_path=file_path,
            file_mtime=file_mtime,
            version=version,
            cursor_position=0,
        )

    def load_empty_document(
        self,
        *,
        note_id: str | None = None,
        title: str = "",
        file_path: str | None = None,
    ) -> None:
        """兼容之前接口。"""
        self.new_note(note_id=note_id, title=title, file_path=file_path)

    # -----------------------------
    # 基础对外接口
    # -----------------------------

    def get_document(self) -> MarkdownDocument:
        return self._document

    def set_document(self, document: MarkdownDocument) -> None:
        self._document = document
        self._apply_document_to_view()
        self.document_changed.emit(self._document)

    def set_text(self, text: str) -> None:
        self._document.set_text(text, mark_dirty=False)
        self._apply_document_to_view()

    def get_text(self) -> str:
        return self.editor.toPlainText()

    def get_title(self) -> str:
        return self.title_edit.text().strip()

    def update_title(self, title: str) -> None:
        self._document.set_title(title or "")
        self._apply_document_to_view()
        self.document_changed.emit(self._document)

    def clear(self) -> None:
        self._document.clear()
        self._apply_document_to_view()
        self.document_changed.emit(self._document)

    def focus_editor(self) -> None:
        self.editor.setFocus()

    def insert_text_at_cursor(self, text: str) -> None:
        if not text:
            return
        cursor = self.editor.textCursor()
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)

    def replace_selection(self, text: str) -> None:
        cursor = self.editor.textCursor()
        cursor.insertText(text)

    def get_cursor_position(self) -> int:
        return self.editor.textCursor().position()

    def set_cursor_position(self, position: int) -> None:
        cursor = self.editor.textCursor()
        position = max(0, min(position, len(self.editor.toPlainText())))
        cursor.setPosition(position)
        self.editor.setTextCursor(cursor)

        self._document.update_cursor_position(position)
        self.cursor_position_changed.emit(position)

    def is_dirty(self) -> bool:
        return self._document.is_dirty

    def has_unsaved_changes(self) -> bool:
        return self._document.has_unsaved_changes()

    def set_read_only_mode(self, enabled: bool) -> None:
        self._read_only_mode = enabled
        self.editor.setReadOnly(enabled)

    # -----------------------------
    # 保存 / 打开 payload
    # -----------------------------

    def build_save_payload(self) -> dict:
        """
        构造保存载荷。
        """
        self._document.set_title(self.get_title())
        return self._document.to_save_payload()

    def build_open_payload(self) -> dict:
        """
        构造当前打开文档状态载荷。
        """
        self._document.set_title(self.get_title())
        return self._document.to_open_payload()

    def request_save(self) -> None:
        """
        发出保存请求。
        """
        self.save_requested.emit(self.build_save_payload())

    def request_open(self) -> None:
        """
        发出打开/重载相关状态请求。
        """
        self.open_requested.emit(self.build_open_payload())

    def mark_saved(
        self,
        *,
        file_mtime: float | None = None,
        version: int | None = None,
    ) -> None:
        self._document.restore_after_save(file_mtime=file_mtime, version=version)
        self.status_label.setText(self._document.session_status)
        self.status_changed.emit(self._document.session_status)
        self.document_changed.emit(self._document)

    def mark_save_failed(self) -> None:
        self._document.mark_save_failed()
        self.status_label.setText(self._document.session_status)
        self.status_changed.emit(self._document.session_status)
        self.document_changed.emit(self._document)

    def mark_external_modified(self) -> None:
        self._document.mark_external_modified()
        self.status_label.setText(self._document.session_status)
        self.status_changed.emit(self._document.session_status)
        self.document_changed.emit(self._document)

    def maybe_save_before_close(self) -> bool:
        """
        阶段二预留：
        当前先提供最基础的关闭前判断。
        True 表示可以继续关闭，False 表示取消关闭。
        """
        if not self.has_unsaved_changes():
            return True

        result = QMessageBox.question(
            self,
            "未保存更改",
            "当前笔记有未保存内容，是否继续关闭？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    # -----------------------------
    # 后续扩展接口
    # -----------------------------

    def get_selected_text(self) -> str:
        return self.editor.textCursor().selectedText()

    def get_plain_text(self) -> str:
        return self._document.get_plain_text()

    def extract_headings(self):
        return self._document.extract_headings()