from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.ui.actions import AgniActionSet, build_app_stylesheet
from app.ui.docks.note_list_dock import NoteListDock
from app.ui.docks.outline_dock import OutlineDock
from app.ui.docks.search_dock import SearchDock
from app.ui.widgets.note_editor_widget import NoteEditorWidget


class MainWindow(QMainWindow):
    def __init__(self, app_context, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_context = app_context
        self.workspace_root = Path(app_context.workspace_root)
        self.notes_dir = self.workspace_root / "notes"
        self.current_note_path: Path | None = None

        self.setObjectName("agni_main_window")
        self.setWindowTitle(f"Agni - {self.workspace_root.name}")
        self.resize(1360, 820)
        self.setMinimumSize(1080, 680)
        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
        )

        self.actions = AgniActionSet.build(self)
        self.editor = NoteEditorWidget(self)
        self.note_dock = NoteListDock(self)
        self.search_dock = SearchDock(self)
        self.outline_dock = OutlineDock(self)
        self.workspace_label = QLabel(self)
        self.status_label = QLabel("就绪", self)

        self._build_ui()
        self._bind_signals()
        self._load_workspace()
        self._open_initial_note()

    def _build_ui(self) -> None:
        self.setStyleSheet(build_app_stylesheet())
        self.setCentralWidget(self.editor)

        self._build_menu_bar()
        self._build_toolbar()
        self._build_docks()
        self._build_status_bar()

    def _build_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        file_menu.addAction(self.actions.new_note)
        file_menu.addAction(self.actions.save_note)
        file_menu.addAction(self.actions.delete_note)
        file_menu.addSeparator()
        file_menu.addAction(self.actions.refresh_workspace)

        view_menu = self.menuBar().addMenu("视图")
        view_menu.addAction(self.actions.toggle_notes)
        view_menu.addAction(self.actions.toggle_search)
        view_menu.addAction(self.actions.toggle_outline)

        tools_menu = self.menuBar().addMenu("工具")
        tools_menu.addAction(self.actions.command_palette)
        tools_menu.addAction(self.actions.focus_search)

        help_menu = self.menuBar().addMenu("帮助")
        help_menu.addAction(self.actions.about)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏", self)
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.actions.new_note)
        toolbar.addAction(self.actions.save_note)
        toolbar.addAction(self.actions.delete_note)
        toolbar.addSeparator()
        toolbar.addAction(self.actions.focus_search)
        toolbar.addAction(self.actions.command_palette)
        toolbar.addSeparator()
        toolbar.addAction(self.actions.refresh_workspace)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    def _build_docks(self) -> None:
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.note_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.search_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.outline_dock)
        self.tabifyDockWidget(self.search_dock, self.outline_dock)
        self.search_dock.raise_()
        self.resizeDocks([self.note_dock], [300], Qt.Orientation.Horizontal)
        self.resizeDocks([self.search_dock, self.outline_dock], [340, 340], Qt.Orientation.Horizontal)

    def _build_status_bar(self) -> None:
        self.workspace_label.setText(f"工作区: {self.workspace_root}")
        self.statusBar().addWidget(self.workspace_label, 1)
        self.statusBar().addPermanentWidget(self.status_label)

    def _bind_signals(self) -> None:
        self.actions.new_note.triggered.connect(self.create_new_note)
        self.actions.save_note.triggered.connect(self.save_current_note)
        self.actions.delete_note.triggered.connect(self.delete_current_note)
        self.actions.command_palette.triggered.connect(self.show_command_palette)
        self.actions.focus_search.triggered.connect(self.search_dock.focus_search)
        self.actions.refresh_workspace.triggered.connect(self.refresh_workspace)
        self.actions.about.triggered.connect(self.show_about_dialog)

        self.actions.toggle_notes.toggled.connect(self.note_dock.setVisible)
        self.actions.toggle_search.toggled.connect(self.search_dock.setVisible)
        self.actions.toggle_outline.toggled.connect(self.outline_dock.setVisible)
        self.note_dock.visibilityChanged.connect(self.actions.toggle_notes.setChecked)
        self.search_dock.visibilityChanged.connect(self.actions.toggle_search.setChecked)
        self.outline_dock.visibilityChanged.connect(self.actions.toggle_outline.setChecked)

        self.note_dock.note_selected.connect(self.open_note)
        self.note_dock.delete_note_requested.connect(self.delete_note)
        self.note_dock.new_note_requested.connect(self.create_new_note)
        self.note_dock.refresh_requested.connect(self.refresh_workspace)
        self.search_dock.result_selected.connect(self.open_note)
        self.outline_dock.heading_selected.connect(self.goto_line)
        self.outline_dock.pdf_selected.connect(self.show_pdf_placeholder)

        self.editor.content_changed.connect(self._on_editor_content_changed)
        self.editor.status_changed.connect(self._on_editor_status_changed)
        self.editor.save_requested.connect(lambda _payload: self.save_current_note())

    def _load_workspace(self) -> None:
        self.note_dock.set_workspace(self.workspace_root)
        self.search_dock.set_workspace(self.workspace_root)
        self.outline_dock.set_workspace(self.workspace_root)

    def _open_initial_note(self) -> None:
        inbox = self.notes_dir / "Inbox.md"
        if inbox.exists():
            self.open_note(inbox)
            return

        self.editor.load_empty_document(title="未命名笔记")
        self._refresh_document_panels()

    def open_note(self, note_path: object) -> None:
        path = Path(note_path)
        if not path.exists() or not path.is_file():
            self.status_label.setText("无法打开所选文件")
            return

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            self._show_message(
                QMessageBox.Icon.Warning,
                "无法打开",
                "该文件不是 UTF-8 Markdown 文档。",
            )
            return

        self.current_note_path = path
        self.editor.load_document(
            text=text,
            note_id=path.stem,
            title=path.stem,
            file_path=str(path),
            file_mtime=path.stat().st_mtime,
        )
        self.note_dock.select_note_path(path)
        self.status_label.setText(f"已打开: {path.name}")
        self._refresh_document_panels()

    def create_new_note(self) -> None:
        dialog = QInputDialog(self)
        dialog.setWindowTitle("新建笔记")
        dialog.setLabelText("笔记标题：")
        dialog.setTextValue("Untitled")
        dialog.setStyleSheet(build_app_stylesheet())
        dialog.resize(360, 160)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        title = dialog.textValue().strip() or "Untitled"
        safe_name = self._safe_filename(title)
        candidate = self.notes_dir / f"{safe_name}.md"
        counter = 2
        while candidate.exists():
            candidate = self.notes_dir / f"{safe_name}-{counter}.md"
            counter += 1

        self.current_note_path = candidate
        self.editor.load_empty_document(note_id=candidate.stem, title=title, file_path=str(candidate))
        self.editor.set_text(f"# {title}\n\n")
        self.editor.focus_editor()
        self.status_label.setText("新笔记已创建，保存后写入工作区")
        self._refresh_document_panels()

    def save_current_note(self) -> None:
        if self.current_note_path is None:
            title = self.editor.get_document().get_title_from_content()
            self.current_note_path = self.notes_dir / f"{self._safe_filename(title)}.md"

        self.notes_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.current_note_path.write_text(self.editor.get_text(), encoding="utf-8")
        except OSError as error:
            self.editor.mark_save_failed()
            self._show_message(QMessageBox.Icon.Critical, "保存失败", str(error))
            return

        self.editor.mark_saved(file_mtime=self.current_note_path.stat().st_mtime)
        self.note_dock.refresh_notes()
        self.note_dock.select_note_path(self.current_note_path)
        self.status_label.setText(f"已保存: {self.current_note_path.name}")

    def delete_current_note(self) -> None:
        if self.current_note_path is None:
            if self.editor.get_text().strip() and self._ask_confirmation(
                "丢弃未保存笔记",
                "当前笔记尚未保存。确定要丢弃这篇未保存的笔记吗？",
                confirm_text="丢弃",
            ):
                self.editor.load_empty_document(title="未命名笔记")
                self._refresh_document_panels()
                self.status_label.setText("未保存笔记已丢弃")
            return

        self.delete_note(self.current_note_path)

    def delete_note(self, note_path: object) -> None:
        path = Path(note_path)
        if not self._is_deletable_note_path(path):
            self._show_message(
                QMessageBox.Icon.Warning,
                "无法删除",
                "只能删除当前工作区 notes 目录下的 Markdown 笔记。",
            )
            return

        if not path.exists():
            self.refresh_workspace()
            self.status_label.setText("笔记已不存在，工作区已刷新")
            return

        if not self._ask_confirmation(
            "删除笔记",
            f"确定要删除笔记“{path.stem}”吗？\n\n该操作会删除工作区中的 Markdown 文件。",
        ):
            return

        was_current_note = self.current_note_path is not None and (
            path.resolve() == self.current_note_path.resolve()
        )

        try:
            path.unlink()
        except OSError as error:
            self._show_message(QMessageBox.Icon.Critical, "删除失败", str(error))
            return

        self.note_dock.refresh_notes()
        self.search_dock.perform_search()

        if was_current_note:
            self.current_note_path = None
            next_note = self._find_first_note()
            if next_note is not None:
                self.open_note(next_note)
            else:
                self.editor.load_empty_document(title="未命名笔记")
                self._refresh_document_panels()

        self.status_label.setText(f"已删除: {path.name}")

    def refresh_workspace(self) -> None:
        self._load_workspace()
        self._refresh_document_panels()
        self.status_label.setText("工作区已刷新")

    def goto_line(self, line_number: int) -> None:
        editor = self.editor.editor
        cursor = QTextCursor(editor.document().findBlockByLineNumber(max(0, line_number - 1)))
        editor.setTextCursor(cursor)
        editor.setFocus()

    def show_command_palette(self) -> None:
        dialog = QDialog(self)
        dialog.setObjectName("command_palette_dialog")
        dialog.setWindowTitle("命令面板")
        dialog.setStyleSheet(build_app_stylesheet())
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        hint = QLabel("选择一个常用操作", dialog)
        hint.setObjectName("section_label")
        layout.addWidget(hint)

        command_list = QListWidget(dialog)
        commands = [
            ("新建笔记", self.create_new_note),
            ("保存当前笔记", self.save_current_note),
            ("删除当前笔记", self.delete_current_note),
            ("聚焦搜索", self.search_dock.focus_search),
            ("刷新工作区", self.refresh_workspace),
        ]
        for text, _callback in commands:
            command_list.addItem(QListWidgetItem(text))
        layout.addWidget(command_list, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setText("关闭")
        layout.addWidget(buttons)
        buttons.rejected.connect(dialog.reject)

        def run_selected() -> None:
            row = command_list.currentRow()
            if row >= 0:
                dialog.accept()
                commands[row][1]()

        command_list.itemActivated.connect(lambda _item: run_selected())
        dialog.resize(360, 360)
        dialog.exec()

    def show_pdf_placeholder(self, pdf_path: object) -> None:
        path = Path(pdf_path)
        self._show_message(
            QMessageBox.Icon.Information,
            "PDF 面板",
            f"已选中文献：{path.name}\n\n后续可在这里接入 PDF 预览、页码跳转和引用插入。",
        )

    def show_about_dialog(self) -> None:
        self._show_message(
            QMessageBox.Icon.Information,
            "关于 Agni",
            "Agni 当前工作台提供三栏布局、Markdown 编辑、工作区资源、全文搜索、反向链接、大纲与 PDF 面板。当前界面层不直接操作数据库，后续可继续接入 service 与 repository。",
        )

    def _show_message(self, icon: QMessageBox.Icon, title: str, text: str) -> None:
        message_box = QMessageBox(self)
        message_box.setIcon(icon)
        message_box.setWindowTitle(title)
        message_box.setText(text)
        message_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        message_box.setStyleSheet(build_app_stylesheet())
        ok_button = message_box.button(QMessageBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText("确定")
        message_box.exec()

    def _ask_confirmation(self, title: str, text: str, *, confirm_text: str = "删除") -> bool:
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Warning)
        message_box.setWindowTitle(title)
        message_box.setText(text)
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        message_box.setDefaultButton(QMessageBox.StandardButton.No)
        message_box.setStyleSheet(build_app_stylesheet())

        yes_button = message_box.button(QMessageBox.StandardButton.Yes)
        no_button = message_box.button(QMessageBox.StandardButton.No)
        if yes_button is not None:
            yes_button.setText(confirm_text)
            yes_button.setObjectName("destructive_button")
        if no_button is not None:
            no_button.setText("取消")

        return message_box.exec() == QMessageBox.StandardButton.Yes

    def _on_editor_content_changed(self, _text: str) -> None:
        self._refresh_document_panels()

    def _on_editor_status_changed(self, status: str) -> None:
        status_text = {
            "idle": "就绪",
            "editing": "未保存",
            "saved": "已保存",
            "save_failed": "保存失败",
            "external_modified": "外部修改",
        }.get(status, status)
        self.status_label.setText(status_text)

    def _refresh_document_panels(self) -> None:
        document = self.editor.get_document()
        self.outline_dock.set_headings(document.extract_headings())
        title = document.title or document.get_title_from_content()
        self.search_dock.update_backlinks(self.current_note_path, title)

    def _safe_filename(self, title: str) -> str:
        cleaned = "".join(char for char in title.strip() if char not in r'\/:*?"<>|')
        cleaned = "-".join(cleaned.split())
        return cleaned or "Untitled"

    def _is_deletable_note_path(self, note_path: Path) -> bool:
        try:
            resolved_note = note_path.resolve()
            resolved_notes_dir = self.notes_dir.resolve()
            resolved_note.relative_to(resolved_notes_dir)
        except ValueError:
            return False

        return resolved_note.suffix.lower() == ".md"

    def _find_first_note(self) -> Path | None:
        if not self.notes_dir.exists():
            return None

        notes = sorted(self.notes_dir.rglob("*.md"), key=lambda item: item.name.lower())
        return notes[0] if notes else None
