"""
app/ui/widgets/note_editor_widget.py

行级 Live Preview 版 NoteEditorWidget
当前行源码编辑，其他行保持 Markdown 渲染。

本版重点：
1. 统一浅色主题；
2. 当前编辑行背景与整体风格一致；
3. 当前编辑行文字更清晰；
4. 保持与 main_window.py 的现有接口兼容。
"""

from __future__ import annotations

from typing import Optional
import html
import re

from PySide6.QtCore import Qt, Signal, QRect, QTimer
from PySide6.QtGui import QAction, QFont, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QMessageBox,
    QTextBrowser,
    QPlainTextEdit,
    QFrame,
)

from app.editor.markdown_document import MarkdownDocument


EDITOR_FONT_FAMILY = "Microsoft YaHei UI"
EDITOR_FONT_FALLBACK = '"Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif'
EDITOR_HTML_FONT_RULE = f"font-family: {EDITOR_FONT_FALLBACK};"
EDITOR_FONT_POINT_SIZE = 11
EDITOR_TEXT_COLOR = "#111827"
EDITOR_CONTENT_PADDING_X = 24
EDITOR_CONTENT_PADDING_Y = 18
EDITOR_LINE_PADDING_Y = 3
EDITOR_LINE_HEIGHT = 1.6
EDITOR_MIN_LINE_HEIGHT = 28


class LinePreviewBrowser(QTextBrowser):
    """支持点击行的预览控件。"""

    line_clicked = Signal(int)

    def mousePressEvent(self, event):
        cursor = self.cursorForPosition(event.pos())
        line_index = max(0, cursor.blockNumber())
        self.line_clicked.emit(line_index)
        super().mousePressEvent(event)


class FloatingLineEditor(QPlainTextEdit):
    """覆盖在预览之上的当前行编辑器。"""

    line_commit_requested = Signal()
    move_up_requested = Signal()
    move_down_requested = Signal()
    split_line_requested = Signal(int)
    merge_prev_requested = Signal()
    merge_next_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setTabChangesFocus(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.document().setDocumentMargin(0)
        text_option = self.document().defaultTextOption()
        text_option.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.document().setDefaultTextOption(text_option)
        self.setContentsMargins(0, 0, 0, 0)
        self.setViewportMargins(0, 0, 0, 0)

        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #FFFFFF;
                color: #111827;
                border: none;
                border-radius: 0;
                padding: 3px 0;
                selection-background-color: #BFDBFE;
                selection-color: #111827;
            }
        """)

    def keyPressEvent(self, event):
        key = event.key()
        cursor = self.textCursor()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.split_line_requested.emit(cursor.position())
            event.accept()
            return

        if key == Qt.Key.Key_Up:
            if cursor.position() == 0:
                self.move_up_requested.emit()
                event.accept()
                return

        if key == Qt.Key.Key_Down:
            if cursor.position() == len(self.toPlainText()):
                self.move_down_requested.emit()
                event.accept()
                return

        if key == Qt.Key.Key_Backspace:
            if cursor.position() == 0:
                self.merge_prev_requested.emit()
                event.accept()
                return

        if key == Qt.Key.Key_Delete:
            if cursor.position() == len(self.toPlainText()):
                self.merge_next_requested.emit()
                event.accept()
                return

        super().keyPressEvent(event)


class NoteEditorWidget(QWidget):
    """
    行级 Live Preview 版 Markdown 编辑器。
    当前行源码编辑，其他行渲染。
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

        self._lines: list[str] = [""]
        self._current_line_index: int = 0

        self._overlay_refresh_timer = QTimer(self)
        self._overlay_refresh_timer.setSingleShot(True)
        self._overlay_refresh_timer.setInterval(20)

        self._build_ui()
        self._bind_signals()
        self._build_actions()
        self._apply_document_to_view()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setObjectName("note_editor_widget")
        self.setStyleSheet("""
            QWidget#note_editor_widget {
                background-color: #FFFFFF;
            }
            QLabel {
                color: #374151;
            }
            QLineEdit {
                background-color: #FFFFFF;
                color: #111827;
                border: 1px solid #D9E1EC;
                border-radius: 8px;
                min-height: 32px;
                padding: 4px 10px;
            }
            QLineEdit:focus {
                border: 1px solid #2563EB;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        title_hint_label = QLabel("标题：", self)
        self.title_edit = QLineEdit(self)
        self.title_edit.setPlaceholderText("请输入笔记标题")

        self.status_label = QLabel("idle", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        header_layout.addWidget(title_hint_label)
        header_layout.addWidget(self.title_edit, 1)
        header_layout.addWidget(self.status_label)

        self.preview = LinePreviewBrowser(self)
        self.preview.setOpenLinks(False)
        self.preview.setOpenExternalLinks(False)
        self.preview.setReadOnly(True)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        preview_font = QFont(EDITOR_FONT_FAMILY)
        preview_font.setPointSize(EDITOR_FONT_POINT_SIZE)
        self.preview.setFont(preview_font)
        self.preview.document().setDefaultFont(preview_font)
        self.preview.document().setDocumentMargin(0)
        self.preview.setViewportMargins(
            EDITOR_CONTENT_PADDING_X,
            EDITOR_CONTENT_PADDING_Y,
            EDITOR_CONTENT_PADDING_X,
            EDITOR_CONTENT_PADDING_Y,
        )

        self.preview.setStyleSheet("""
            QTextBrowser {
                background-color: #FFFFFF;
                color: #111827;
                border: 1px solid #E6EAF0;
                border-radius: 8px;
                padding: 0;
            }
        """)

        self.line_editor = FloatingLineEditor(self.preview.viewport())
        editor_font = QFont(EDITOR_FONT_FAMILY)
        editor_font.setPointSize(EDITOR_FONT_POINT_SIZE)
        editor_font.setWeight(QFont.Weight.Normal)
        self.line_editor.setFont(editor_font)
        self.line_editor.document().setDefaultFont(editor_font)
        self.line_editor.hide()

        layout.addLayout(header_layout)
        layout.addWidget(self.preview, 1)

    def _bind_signals(self) -> None:
        self.title_edit.textEdited.connect(self._on_title_edited)
        self.preview.line_clicked.connect(self._on_preview_line_clicked)

        self.line_editor.textChanged.connect(self._on_line_editor_text_changed)
        self.line_editor.cursorPositionChanged.connect(self._on_line_editor_cursor_changed)
        self.line_editor.move_up_requested.connect(self._move_to_previous_line)
        self.line_editor.move_down_requested.connect(self._move_to_next_line)
        self.line_editor.split_line_requested.connect(self._split_current_line)
        self.line_editor.merge_prev_requested.connect(self._merge_with_previous_line)
        self.line_editor.merge_next_requested.connect(self._merge_with_next_line)

        self._overlay_refresh_timer.timeout.connect(self._reposition_line_editor)

    def _build_actions(self) -> None:
        self.save_action = QAction(self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self.request_save)
        self.addAction(self.save_action)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_editor_fonts()
        self._overlay_refresh_timer.start()

    def _apply_editor_fonts(self) -> None:
        editor_font = QFont(EDITOR_FONT_FAMILY)
        editor_font.setPointSize(EDITOR_FONT_POINT_SIZE)

        self.preview.setFont(editor_font)
        self.preview.document().setDefaultFont(editor_font)
        self.line_editor.setFont(editor_font)
        self.line_editor.document().setDefaultFont(editor_font)

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------

    def _set_lines_from_text(self, text: str) -> None:
        self._lines = text.split("\n")
        if not self._lines:
            self._lines = [""]
        self._current_line_index = max(0, min(self._current_line_index, len(self._lines) - 1))

    def _get_text_from_lines(self) -> str:
        return "\n".join(self._lines)

    def _refresh_preview(self) -> None:
        html_text = self._render_document_html(self._lines, self._current_line_index)
        self.preview.setHtml(html_text)
        self._overlay_refresh_timer.start()

    def _render_document_html(self, lines: list[str], editing_line_index: int) -> str:
        body_parts = []
        for i, line in enumerate(lines):
            if i == editing_line_index:
                placeholder = self._render_editing_line_placeholder(line)
                body_parts.append(f'<div class="agni-line editing-line">{placeholder}</div>')
            else:
                body_parts.append(self._render_line_to_html(line))

        return f"""
        <html>
        <head>
        <style>
            body {{
                {EDITOR_HTML_FONT_RULE}
                font-size: {EDITOR_FONT_POINT_SIZE}pt;
                line-height: {EDITOR_LINE_HEIGHT};
                padding: 0;
                margin: 0;
                color: {EDITOR_TEXT_COLOR};
                background: #FFFFFF;
                text-align: left;
            }}
            .agni-line {{
                min-height: {EDITOR_MIN_LINE_HEIGHT}px;
                margin: 0;
                padding: {EDITOR_LINE_PADDING_Y}px 0;
                white-space: pre-wrap;
                word-wrap: break-word;
                color: {EDITOR_TEXT_COLOR};
                text-align: left;
            }}
            .editing-line {{
                background: #FFFFFF;
                border: none;
                border-radius: 0;
            }}
            .editing-line-placeholder {{
                visibility: hidden;
            }}
            h1, h2, h3, h4, h5, h6 {{
                margin: 8px 0 6px 0;
                font-weight: 700;
                color: #111827;
            }}
            h1 {{ font-size: 20pt; }}
            h2 {{ font-size: 17pt; }}
            h3 {{ font-size: 15pt; }}
            h4 {{ font-size: 13pt; }}
            h5 {{ font-size: 12pt; }}
            h6 {{ font-size: 11pt; }}

            p {{
                margin: 0;
                color: {EDITOR_TEXT_COLOR};
            }}
            
            .agni-hr {{
                border: none;
                border-top: 1px solid #D9E1EC;
                margin: 8px 0;
            }}

            .list-item {{
                margin-left: 18px;
                color: {EDITOR_TEXT_COLOR};
            }}

            .blockquote {{
                border-left: 3px solid #93C5FD;
                padding-left: 10px;
                color: #374151;
            }}

            .code-inline {{
                background: #F8FAFC;
                border: 1px solid #E6EAF0;
                border-radius: 4px;
                padding: 1px 4px;
                font-family: Consolas, monospace;
                color: #B45309;
            }}

            .wikilink {{
                color: #2563EB;
                font-weight: 600;
            }}

            .citation {{
                color: #8B5CF6;
                font-weight: 600;
            }}

            a {{
                color: #2563EB;
                text-decoration: none;
            }}

            strong {{
                color: #111827;
                font-weight: 700;
            }}

            em {{
                color: {EDITOR_TEXT_COLOR};
                font-style: italic;
            }}
        </style>
        </head>
        <body>
            {''.join(body_parts)}
        </body>
        </html>
        """

    def _render_editing_line_placeholder(self, line: str) -> str:
        if line == "":
            return '<span class="editing-line-placeholder">&nbsp;</span>'

        return f'<span class="editing-line-placeholder">{html.escape(line)}</span>'

    def _render_line_to_html(self, line: str) -> str:
        stripped = line.rstrip()

        if stripped == "":
            return '<div class="agni-line">&nbsp;</div>'

        # Markdown 分隔线：---  ___  ***
        hr_match = re.match(r"^\s*([-_*])\s*(\1\s*){2,}$", stripped)
        if hr_match:
            return '<div class="agni-line"><hr class="agni-hr"></div>'

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            content = self._render_inline_html(heading_match.group(2))
            return f'<div class="agni-line"><h{level}>{content}</h{level}></div>'

        blockquote_match = re.match(r"^>\s?(.*)$", stripped)
        if blockquote_match:
            content = self._render_inline_html(blockquote_match.group(1))
            return f'<div class="agni-line blockquote">{content}</div>'

        list_match = re.match(r"^[-*+]\s+(.*)$", stripped)
        if list_match:
            content = self._render_inline_html(list_match.group(1))
            return f'<div class="agni-line list-item">• {content}</div>'

        ordered_match = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if ordered_match:
            index = ordered_match.group(1)
            content = self._render_inline_html(ordered_match.group(2))
            return f'<div class="agni-line list-item">{index}. {content}</div>'

        content = self._render_inline_html(stripped)
        return f'<div class="agni-line"><p>{content}</p></div>'

    def _render_inline_html(self, text: str) -> str:
        escaped = html.escape(text)

        escaped = re.sub(
            r"\[\[(.*?)(\|(.*?))?\]\]",
            lambda m: f'<span class="wikilink">{html.escape(m.group(3) or m.group(1))}</span>',
            escaped,
        )

        escaped = re.sub(
            r"\[@([^\]]+)\]",
            lambda m: f'<span class="citation">[@{html.escape(m.group(1))}]</span>',
            escaped,
        )

        escaped = re.sub(
            r"\[(.*?)\]\((.*?)\)",
            lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>',
            escaped,
        )

        escaped = re.sub(
            r"`([^`]+)`",
            lambda m: f'<span class="code-inline">{m.group(1)}</span>',
            escaped,
        )

        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)

        return escaped

    # ------------------------------------------------------------------
    # 行编辑器定位与切换
    # ------------------------------------------------------------------

    def _reposition_line_editor(self) -> None:
        block = self.preview.document().findBlockByNumber(self._current_line_index)
        if not block.isValid():
            self.line_editor.hide()
            return

        self._apply_editor_fonts()

        cursor = QTextCursor(block)
        rect = self.preview.cursorRect(cursor)
        block_rect = self.preview.document().documentLayout().blockBoundingRect(block)

        viewport_rect = self.preview.viewport().rect()
        x = max(0, rect.left())
        y = rect.top()
        width = max(120, viewport_rect.width() - x)

        editor_doc_height = int(self.line_editor.document().size().height())
        line_height = max(
            EDITOR_MIN_LINE_HEIGHT,
            int(block_rect.height()),
            editor_doc_height,
            self.line_editor.fontMetrics().height() + (EDITOR_LINE_PADDING_Y * 2),
        )
        self.line_editor.setGeometry(QRect(x, y, width, line_height))
        self.line_editor.show()
        self.line_editor.raise_()

    def _switch_to_line(self, line_index: int, *, focus: bool = True) -> None:
        line_index = max(0, min(line_index, len(self._lines) - 1))
        self._current_line_index = line_index

        self.line_editor.blockSignals(True)
        self.line_editor.setPlainText(self._lines[self._current_line_index])
        self._apply_editor_fonts()
        self.line_editor.blockSignals(False)

        cursor = self.line_editor.textCursor()
        cursor.setPosition(len(self._lines[self._current_line_index]))
        self.line_editor.setTextCursor(cursor)

        self._refresh_preview()

        if focus:
            self.line_editor.setFocus()

    def _on_preview_line_clicked(self, line_index: int) -> None:
        self._switch_to_line(line_index, focus=True)

    # ------------------------------------------------------------------
    # 行编辑逻辑
    # ------------------------------------------------------------------

    def _on_line_editor_text_changed(self) -> None:
        if self._is_loading:
            return

        self._lines[self._current_line_index] = self.line_editor.toPlainText()
        full_text = self._get_text_from_lines()

        self._document.set_text(full_text, mark_dirty=True)
        self.status_label.setText(self._document.session_status)

        self.content_changed.emit(full_text)
        self.document_changed.emit(self._document)
        self.status_changed.emit(self._document.session_status)

        self._overlay_refresh_timer.start()

    def _on_line_editor_cursor_changed(self) -> None:
        cursor = self.line_editor.textCursor()
        position_in_line = cursor.position()
        absolute = self._line_column_to_absolute_position(
            self._current_line_index,
            position_in_line,
        )
        self._document.update_cursor_position(absolute)
        self.cursor_position_changed.emit(absolute)

    def _split_current_line(self, position: int) -> None:
        current = self._lines[self._current_line_index]
        left = current[:position]
        right = current[position:]

        self._lines[self._current_line_index] = left
        self._lines.insert(self._current_line_index + 1, right)

        self._document.set_text(self._get_text_from_lines(), mark_dirty=True)
        self._switch_to_line(self._current_line_index + 1, focus=True)

    def _merge_with_previous_line(self) -> None:
        if self._current_line_index == 0:
            return

        prev_line = self._lines[self._current_line_index - 1]
        current_line = self._lines[self._current_line_index]
        new_line = prev_line + current_line

        self._lines[self._current_line_index - 1] = new_line
        del self._lines[self._current_line_index]

        self._document.set_text(self._get_text_from_lines(), mark_dirty=True)
        self._switch_to_line(self._current_line_index - 1, focus=True)

        cursor = self.line_editor.textCursor()
        cursor.setPosition(len(prev_line))
        self.line_editor.setTextCursor(cursor)

    def _merge_with_next_line(self) -> None:
        if self._current_line_index >= len(self._lines) - 1:
            return

        current_line = self._lines[self._current_line_index]
        next_line = self._lines[self._current_line_index + 1]
        self._lines[self._current_line_index] = current_line + next_line
        del self._lines[self._current_line_index + 1]

        self._document.set_text(self._get_text_from_lines(), mark_dirty=True)
        self._switch_to_line(self._current_line_index, focus=True)

        cursor = self.line_editor.textCursor()
        cursor.setPosition(len(current_line))
        self.line_editor.setTextCursor(cursor)

    def _move_to_previous_line(self) -> None:
        if self._current_line_index > 0:
            self._switch_to_line(self._current_line_index - 1, focus=True)

    def _move_to_next_line(self) -> None:
        if self._current_line_index < len(self._lines) - 1:
            self._switch_to_line(self._current_line_index + 1, focus=True)

    # ------------------------------------------------------------------
    # 标题 / 文档同步
    # ------------------------------------------------------------------

    def _on_title_edited(self, title: str) -> None:
        if self._is_loading:
            return

        self._document.set_title(title)
        self.status_label.setText(self._document.session_status)

        self.title_changed.emit(title)
        self.document_changed.emit(self._document)
        self.status_changed.emit(self._document.session_status)

    def _absolute_position_to_line_column(self, absolute_pos: int) -> tuple[int, int]:
        text = self._get_text_from_lines()
        absolute_pos = max(0, min(absolute_pos, len(text)))

        lines = self._lines
        current = 0
        for i, line in enumerate(lines):
            line_len = len(line)
            if absolute_pos <= current + line_len:
                return i, absolute_pos - current
            current += line_len + 1

        return len(lines) - 1, len(lines[-1])

    def _line_column_to_absolute_position(self, line_index: int, column: int) -> int:
        line_index = max(0, min(line_index, len(self._lines) - 1))
        absolute = 0
        for i in range(line_index):
            absolute += len(self._lines[i]) + 1
        absolute += max(0, min(column, len(self._lines[line_index])))
        return absolute

    def _apply_document_to_view(self) -> None:
        self._is_loading = True
        try:
            self.title_edit.setText(self._document.title or "")
            self.status_label.setText(self._document.session_status)

            self._set_lines_from_text(self._document.get_text())

            line_index, column = self._absolute_position_to_line_column(
                self._document.restore_cursor_position()
            )
            self._current_line_index = line_index

            self._switch_to_line(self._current_line_index, focus=False)

            cursor = self.line_editor.textCursor()
            cursor.setPosition(column)
            self.line_editor.setTextCursor(cursor)

            self.status_changed.emit(self._document.session_status)
        finally:
            self._is_loading = False

    # ------------------------------------------------------------------
    # 文档装载与创建
    # ------------------------------------------------------------------

    def get_document(self) -> MarkdownDocument:
        return self._document

    def set_document(self, document: MarkdownDocument) -> None:
        self._document = document
        self._apply_document_to_view()
        self.document_changed.emit(self._document)

    def new_note(
        self,
        *,
        note_id: str | None = None,
        title: str = "",
        file_path: str | None = None,
    ) -> None:
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
        self.new_note(note_id=note_id, title=title, file_path=file_path)

    # ------------------------------------------------------------------
    # 基础接口
    # ------------------------------------------------------------------

    def set_text(self, text: str) -> None:
        self._document.set_text(text, mark_dirty=False)
        self._apply_document_to_view()

    def get_text(self) -> str:
        return self._get_text_from_lines()

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
        self.line_editor.setFocus()

    def insert_text_at_cursor(self, text: str) -> None:
        if not text:
            return
        cursor = self.line_editor.textCursor()
        cursor.insertText(text)
        self.line_editor.setTextCursor(cursor)

    def replace_selection(self, text: str) -> None:
        cursor = self.line_editor.textCursor()
        cursor.insertText(text)

    def get_cursor_position(self) -> int:
        return self._document.cursor_position

    def set_cursor_position(self, position: int) -> None:
        line_index, column = self._absolute_position_to_line_column(position)
        self._switch_to_line(line_index, focus=True)

        cursor = self.line_editor.textCursor()
        cursor.setPosition(column)
        self.line_editor.setTextCursor(cursor)

        self._document.update_cursor_position(position)
        self.cursor_position_changed.emit(position)

    def is_dirty(self) -> bool:
        return self._document.is_dirty

    def has_unsaved_changes(self) -> bool:
        return self._document.has_unsaved_changes()

    def set_read_only_mode(self, enabled: bool) -> None:
        self._read_only_mode = enabled
        self.line_editor.setReadOnly(enabled)
        self.title_edit.setReadOnly(enabled)

    # ------------------------------------------------------------------
    # 保存 / 打开 payload
    # ------------------------------------------------------------------

    def build_save_payload(self) -> dict:
        self._document.set_title(self.get_title())
        return self._document.to_save_payload()

    def build_open_payload(self) -> dict:
        self._document.set_title(self.get_title())
        return self._document.to_open_payload()

    def request_save(self) -> None:
        self.save_requested.emit(self.build_save_payload())

    def request_open(self) -> None:
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

    # ------------------------------------------------------------------
    # 扩展接口
    # ------------------------------------------------------------------

    def get_selected_text(self) -> str:
        return self.line_editor.textCursor().selectedText()

    def get_plain_text(self) -> str:
        return self._document.get_plain_text()

    def extract_headings(self):
        return self._document.extract_headings()

    def refresh_preview_now(self) -> None:
        self._refresh_preview()
