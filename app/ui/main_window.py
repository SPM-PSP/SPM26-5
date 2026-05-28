from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QToolBar,
    QWidget,
)

from app.bootstrap.startup import bootstrap_workspace
from app.ui.actions import AgniActionSet, build_app_stylesheet
from app.ui.dialogs.command_palette_dialog import CommandPaletteDialog
from app.ui.dialogs.workspace_picker_dialog import WorkspacePickerDialog
from app.ui.docks.note_list_dock import NoteListDock
from app.ui.docks.outline_dock import OutlineDock
from app.ui.docks.search_dock import SearchDock
from app.ui.models.ui_items import CommandItem, KnowledgeObjectKind, KnowledgeSelection, SatelliteItem
from app.ui.widgets.note_editor_widget import NoteEditorWidget


class MainWindow(QMainWindow):
    def __init__(self, app_context, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_context = app_context
        self.workspace_root = Path(app_context.workspace_root)
        self.notes_dir = self.workspace_root / "notes"
        self.current_note_path: Path | None = None

        self.setObjectName("agni_main_window")
        self.resize(1360, 820)
        self.setMinimumSize(1080, 680)
        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
        )

        self.actions = AgniActionSet.build(self)
        self.workspace_tabs = QTabWidget(self)
        self.workspace_tabs.setObjectName("workspace_tabs")
        self.workspace_tabs.setTabsClosable(True)
        self.workspace_tabs.setMovable(True)

        self.note_dock = NoteListDock(self)
        self.search_dock = SearchDock(self)
        self.outline_dock = OutlineDock(self)
        self.workspace_label = QLabel(self)
        self.status_label = QLabel("Ready", self)

        self._build_ui()
        self._bind_signals()
        self._install_app_shortcut_filter()
        self._apply_workspace_context(app_context)

    def _build_ui(self) -> None:
        self.setStyleSheet(build_app_stylesheet())
        self.setCentralWidget(self.workspace_tabs)
        self._build_menu_bar()
        self._build_toolbar()
        self._build_docks()
        self._build_status_bar()

    def _build_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.actions.new_note)
        file_menu.addAction(self.actions.open_workspace)
        file_menu.addAction(self.actions.save_note)
        file_menu.addAction(self.actions.delete_note)
        file_menu.addSeparator()
        file_menu.addAction(self.actions.refresh_workspace)

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.actions.toggle_notes)
        view_menu.addAction(self.actions.toggle_search)
        view_menu.addAction(self.actions.toggle_outline)

        tools_menu = self.menuBar().addMenu("Tools")
        tools_menu.addAction(self.actions.command_palette)
        tools_menu.addAction(self.actions.focus_search)

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(self.actions.about)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.actions.new_note)
        toolbar.addAction(self.actions.open_workspace)
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
        self.statusBar().addWidget(self.workspace_label, 1)
        self.statusBar().addPermanentWidget(self.status_label)

    def _bind_signals(self) -> None:
        self.actions.new_note.triggered.connect(self.create_new_note)
        self.actions.open_workspace.triggered.connect(self.show_workspace_picker)
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
        self.note_dock.reference_selected.connect(self.open_pdf_placeholder)
        self.note_dock.knowledge_selected.connect(self.open_knowledge_object)
        self.note_dock.assign_to_planet_requested.connect(self.assign_object_to_planet)
        self.note_dock.new_note_requested.connect(self.create_new_note)
        self.note_dock.refresh_requested.connect(self.refresh_workspace)

        self.search_dock.result_selected.connect(self.open_note)
        self.outline_dock.heading_selected.connect(self.goto_line)
        self.outline_dock.pdf_selected.connect(self.open_pdf_placeholder)

        self.workspace_tabs.currentChanged.connect(self._on_tab_changed)
        self.workspace_tabs.tabCloseRequested.connect(self._close_tab)

    def _install_app_shortcut_filter(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _apply_workspace_context(self, app_context) -> None:
        self.app_context = app_context
        self.workspace_root = Path(app_context.workspace_root)
        self.notes_dir = self.workspace_root / "notes"
        self.current_note_path = None

        self.setWindowTitle(f"Agni - {self.workspace_root.name}")
        self.workspace_label.setText(f"Workspace: {self.workspace_root}")
        self.status_label.setText("Workspace loaded")

        self.note_dock.bind_app_context(app_context)
        self.search_dock.bind_app_context(app_context)
        self.note_dock.set_workspace(self.workspace_root)
        self.search_dock.set_workspace(self.workspace_root)
        self.outline_dock.set_workspace(self.workspace_root)

        self._reset_editor_tabs()
        self._open_initial_note()

    def _reset_editor_tabs(self) -> None:
        while self.workspace_tabs.count() > 0:
            widget = self.workspace_tabs.widget(0)
            self.workspace_tabs.removeTab(0)
            if widget is not None:
                widget.deleteLater()

        self.editor = NoteEditorWidget(self)
        self.workspace_tabs.addTab(self.editor, "Untitled")
        self._connect_editor(self.editor)

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        if self._is_save_shortcut_event(event):
            if event.type() == QEvent.Type.ShortcutOverride:
                return True
            self.save_current_note()
            return True
        return super().eventFilter(watched, event)

    def _connect_editor(self, editor: NoteEditorWidget) -> None:
        self._disable_editor_local_save_shortcut(editor)
        editor.content_changed.connect(self._on_editor_content_changed)
        editor.document_changed.connect(
            lambda _document, target=editor: self._on_editor_document_changed(target)
        )
        editor.cursor_position_changed.connect(
            lambda position, target=editor: self._on_editor_cursor_changed(target, position)
        )
        editor.status_changed.connect(self._on_editor_status_changed)
        editor.title_changed.connect(lambda _title, target=editor: self._on_editor_title_changed(target))
        editor.save_requested.connect(lambda _payload: self.save_current_note())

    def _is_save_shortcut_event(self, event: QEvent) -> bool:
        if event.type() not in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
            return False
        if QApplication.activeModalWidget() is not None:
            return False
        focus_widget = QApplication.focusWidget()
        if focus_widget is not None and focus_widget is not self and not self.isAncestorOf(focus_widget):
            return False
        if not event.matches(QKeySequence.StandardKey.Save):
            return False
        event.accept()
        return True

    def _disable_editor_local_save_shortcut(self, editor: NoteEditorWidget) -> None:
        save_sequence = QKeySequence("Ctrl+S")
        for action in editor.actions():
            shortcut = action.shortcut()
            if shortcut and shortcut.matches(save_sequence) != QKeySequence.SequenceMatch.NoMatch:
                action.setShortcut(QKeySequence())

    def _current_editor(self) -> NoteEditorWidget:
        widget = self.workspace_tabs.currentWidget()
        return widget if isinstance(widget, NoteEditorWidget) else self.editor

    def _current_note_path(self) -> Path | None:
        editor = self._current_editor()
        file_path = editor.get_document().file_path
        return Path(file_path) if file_path else self.current_note_path

    def _add_note_tab(self, editor: NoteEditorWidget, title: str, note_path: Path | None) -> None:
        index = self.workspace_tabs.addTab(editor, title or "Untitled")
        self.workspace_tabs.setTabToolTip(index, str(note_path) if note_path else "Unsaved note")
        self.workspace_tabs.setCurrentIndex(index)
        self.editor = editor
        self.current_note_path = note_path
        self._connect_editor(editor)

    def _find_note_tab(self, note_path: Path) -> int:
        expected = str(note_path.resolve())
        for index in range(self.workspace_tabs.count()):
            widget = self.workspace_tabs.widget(index)
            if not isinstance(widget, NoteEditorWidget):
                continue
            file_path = widget.get_document().file_path
            if file_path and str(Path(file_path).resolve()) == expected:
                return index
        return -1

    def _update_tab_title(self, editor: NoteEditorWidget | None = None) -> None:
        target = editor or self._current_editor()
        index = self.workspace_tabs.indexOf(target)
        if index < 0:
            return
        title = target.get_title() or target.get_document().get_title_from_content() or "Untitled"
        marker = "*" if target.has_unsaved_changes() else ""
        self.workspace_tabs.setTabText(index, f"{marker}{title}")
        self.workspace_tabs.setTabToolTip(index, target.get_document().file_path or "Unsaved note")

    def _on_tab_changed(self, index: int) -> None:
        widget = self.workspace_tabs.widget(index)
        if isinstance(widget, NoteEditorWidget):
            self.editor = widget
            self.current_note_path = self._current_note_path()
            if self.current_note_path is not None:
                self.note_dock.select_note_path(self.current_note_path)
            self._refresh_document_panels()
        elif widget is not None:
            self.current_note_path = None
            self.status_label.setText("Reference preview")

    def _close_tab(self, index: int) -> None:
        widget = self.workspace_tabs.widget(index)
        if isinstance(widget, NoteEditorWidget) and not widget.maybe_save_before_close():
            return
        if self.workspace_tabs.count() == 1:
            if isinstance(widget, NoteEditorWidget):
                widget.load_empty_document(title="Untitled")
                self.current_note_path = None
                self._update_tab_title(widget)
                self._refresh_document_panels()
            return
        self.workspace_tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()

    def _open_initial_note(self) -> None:
        inbox = self.notes_dir / "Inbox.md"
        if inbox.exists():
            self.open_note(inbox)
            return
        self.editor.load_empty_document(title="Untitled")
        self._update_tab_title(self.editor)
        self._refresh_document_panels()

    def open_note(self, note_path: object) -> None:
        controller = getattr(self.app_context, "note_controller", None)
        if controller is None:
            self.status_label.setText("Note controller is not available")
            return

        path = Path(note_path)
        result = controller.open_note(self.workspace_root, path)
        if not result["success"]:
            self.status_label.setText(str(result["message"]))
            return

        note = dict(result["data"]["note"])
        resolved_path = Path(str(note["file_path"]))
        existing_index = self._find_note_tab(resolved_path)
        if existing_index >= 0:
            self.workspace_tabs.setCurrentIndex(existing_index)
            self._refresh_document_panels()
            self.outline_dock.set_object_context(self._selection_for_note(resolved_path))
            self.status_label.setText(f"Opened {resolved_path.name}")
            return

        editor = self._current_editor()
        if not (
            self.workspace_tabs.count() == 1
            and editor.get_document().file_path is None
            and not editor.get_text().strip()
        ):
            editor = NoteEditorWidget(self)

        editor.load_document(
            text=str(note.get("markdown_content") or ""),
            note_id=str(note.get("note_id") or resolved_path.stem),
            title=str(note.get("title") or resolved_path.stem),
            file_path=str(resolved_path),
            file_mtime=note.get("file_mtime"),
        )
        if self.workspace_tabs.indexOf(editor) >= 0:
            self.current_note_path = resolved_path
            self.editor = editor
            self._update_tab_title(editor)
        else:
            self._add_note_tab(editor, str(note.get("title") or resolved_path.stem), resolved_path)
        self.note_dock.select_note_path(resolved_path)
        self.status_label.setText(f"Opened {resolved_path.name}")
        self._refresh_document_panels()
        self.outline_dock.set_object_context(self._selection_for_note(resolved_path))

    def create_new_note(self) -> None:
        dialog = QInputDialog(self)
        dialog.setWindowTitle("New Note")
        dialog.setLabelText("Note title:")
        dialog.setTextValue("Untitled")
        dialog.setStyleSheet(build_app_stylesheet())
        dialog.resize(360, 160)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        title = dialog.textValue().strip() or "Untitled"
        candidate = self.notes_dir / f"{self._safe_filename(title)}.md"
        counter = 2
        while candidate.exists():
            candidate = self.notes_dir / f"{self._safe_filename(title)}-{counter}.md"
            counter += 1

        editor = NoteEditorWidget(self)
        editor.load_empty_document(note_id=candidate.stem, title=title, file_path=str(candidate))
        editor.set_text(f"# {title}\n\n")
        self._add_note_tab(editor, title, candidate)
        editor.focus_editor()
        self.status_label.setText("New note created")
        self._refresh_document_panels()

    def save_current_note(self) -> None:
        if not isinstance(self.workspace_tabs.currentWidget(), NoteEditorWidget):
            self.status_label.setText("Current tab is not a Markdown note")
            return

        controller = getattr(self.app_context, "note_controller", None)
        if controller is None:
            self.status_label.setText("Note controller is not available")
            return

        editor = self._current_editor()
        result = controller.save_note(self.workspace_root, editor.build_save_payload())
        if not result["success"]:
            editor.mark_save_failed()
            self._show_message(QMessageBox.Icon.Critical, "Save Failed", str(result["message"]))
            return

        note = dict(result["data"]["note"])
        target_path = Path(str(note["file_path"]))
        self.current_note_path = target_path
        editor.get_document().bind_file_path(target_path)
        editor.mark_saved(file_mtime=note.get("file_mtime"))
        self._update_tab_title(editor)
        self.note_dock.refresh()
        self.note_dock.select_note_path(target_path)
        self.search_dock.perform_search()
        self._refresh_document_panels()
        self.outline_dock.set_object_context(self._selection_for_note(target_path))
        self.status_label.setText(f"Saved {target_path.name}")

    def delete_current_note(self) -> None:
        editor = self._current_editor()
        current_path = self._current_note_path()
        if current_path is None or not current_path.exists():
            if editor.get_text().strip() and self._ask_confirmation(
                "Discard Unsaved Note",
                "The current note has not been saved. Discard it?",
                confirm_text="Discard",
            ):
                editor.load_empty_document(title="Untitled")
                self.current_note_path = None
                self._update_tab_title(editor)
                self._refresh_document_panels()
                self.status_label.setText("Unsaved note discarded")
            return
        self.delete_note(current_path)

    def delete_note(self, note_path: object) -> None:
        path = Path(note_path)
        if not self._is_deletable_note_path(path):
            self._show_message(
                QMessageBox.Icon.Warning,
                "Delete Blocked",
                "Only Markdown notes inside workspace/notes can be deleted.",
            )
            return

        if not path.exists():
            self.refresh_workspace()
            self.status_label.setText("Note does not exist anymore")
            return

        if not self._ask_confirmation(
            "Delete Note",
            f"Delete note '{path.stem}' from the workspace?",
        ):
            return

        controller = getattr(self.app_context, "note_controller", None)
        if controller is None:
            self.status_label.setText("Note controller is not available")
            return

        result = controller.delete_note(self.workspace_root, path)
        if not result["success"]:
            self._show_message(QMessageBox.Icon.Critical, "Delete Failed", str(result["message"]))
            return

        was_current_note = self.current_note_path is not None and path.resolve() == self.current_note_path.resolve()
        self.note_dock.refresh()
        self.search_dock.perform_search()

        if was_current_note:
            self.current_note_path = None
            current_index = self.workspace_tabs.currentIndex()
            current_widget = self.workspace_tabs.currentWidget()
            if isinstance(current_widget, NoteEditorWidget) and self.workspace_tabs.count() > 1:
                self.workspace_tabs.removeTab(current_index)
                current_widget.deleteLater()
            next_note = self._find_first_note()
            if next_note is not None:
                self.open_note(next_note)
            else:
                self._current_editor().load_empty_document(title="Untitled")
                self._update_tab_title()
                self._refresh_document_panels()

        self.status_label.setText(f"Deleted {path.name}")

    def refresh_workspace(self) -> None:
        self.note_dock.refresh()
        self.search_dock.set_workspace(self.workspace_root)
        self.outline_dock.set_workspace(self.workspace_root)
        self._refresh_document_panels()
        self.status_label.setText("Workspace refreshed")

    def show_workspace_picker(self) -> None:
        dialog = WorkspacePickerDialog(initial_path=self.workspace_root, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.selected_workspace()
        if selected is None:
            return

        current_editor = self._current_editor()
        if isinstance(current_editor, NoteEditorWidget) and not current_editor.maybe_save_before_close():
            return

        try:
            new_context = bootstrap_workspace(selected)
        except Exception as error:
            self._show_message(QMessageBox.Icon.Critical, "Open Workspace Failed", str(error))
            return

        self._apply_workspace_context(new_context)

    def goto_line(self, line_number: int) -> None:
        editor = self._current_editor()
        editor.set_cursor_position(self._line_number_to_cursor_position(editor.get_text(), line_number))
        editor.focus_editor()

    def show_command_palette(self) -> None:
        commands = [
            CommandItem("New Note", self.create_new_note, "Create a new Markdown note"),
            CommandItem("Open Workspace", self.show_workspace_picker, "Switch to another workspace"),
            CommandItem("Save Note", self.save_current_note, "Save the current note"),
            CommandItem("Delete Note", self.delete_current_note, "Delete the current note"),
            CommandItem("Focus Knowledge Model", self.focus_knowledge_model, "Open the knowledge model view"),
            CommandItem("Focus Search", self.search_dock.focus_search, "Jump to global search"),
            CommandItem("Refresh Workspace", self.refresh_workspace, "Reload notes and references"),
        ]
        dialog = CommandPaletteDialog(commands, self)
        dialog.exec()

    def focus_knowledge_model(self) -> None:
        self.note_dock.show()
        self.note_dock.raise_()
        self.note_dock.tabs.setCurrentWidget(self.note_dock.model_page)
        self.status_label.setText("Knowledge model focused")

    def open_knowledge_object(self, selection: KnowledgeSelection) -> None:
        if selection.kind == KnowledgeObjectKind.STAR_NOTE and selection.path is not None:
            self.open_note(selection.path)
            self.outline_dock.set_object_context(selection)
            return
        if selection.kind == KnowledgeObjectKind.STAR_REFERENCE:
            self.open_pdf_placeholder(
                {"title": selection.title, "display_path": str(selection.path) if selection.path else None}
            )
            self.outline_dock.set_object_context(selection)
            return
        if selection.kind == KnowledgeObjectKind.SATELLITE and selection.path is not None:
            if selection.path.suffix.lower() == ".md":
                self.open_note(selection.path)
                if selection.satellites and selection.satellites[0].line_number:
                    self.goto_line(selection.satellites[0].line_number)
            else:
                self.open_pdf_placeholder(selection.path)
            self.outline_dock.set_object_context(selection)
            return
        self.open_knowledge_dashboard(selection)
        self.outline_dock.set_object_context(selection)

    def open_knowledge_dashboard(self, selection: KnowledgeSelection) -> None:
        tab_key = f"knowledge:{selection.kind.value}:{selection.title}"
        for index in range(self.workspace_tabs.count()):
            if self.workspace_tabs.tabToolTip(index) == tab_key:
                self.workspace_tabs.setCurrentIndex(index)
                return

        body = QLabel(self._knowledge_dashboard_text(selection), self)
        body.setObjectName("knowledge_dashboard")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        body.setMargin(24)
        index = self.workspace_tabs.addTab(body, selection.title)
        self.workspace_tabs.setTabToolTip(index, tab_key)
        self.workspace_tabs.setCurrentIndex(index)

    def assign_object_to_planet(self, target: object, planet: str) -> None:
        if not isinstance(target, dict):
            return

        controller = getattr(self.app_context, "knowledge_controller", None)
        if controller is None:
            self.status_label.setText("Knowledge controller is not available")
            return

        result = controller.assign_object_to_planet(
            self.workspace_root,
            object_kind=str(target.get("object_kind") or ""),
            object_key=str(target.get("object_key") or ""),
            planet=planet,
        )
        if not result["success"]:
            self._show_message(QMessageBox.Icon.Warning, "Assign Planet Failed", str(result["message"]))
            return

        self.note_dock.refresh()
        display_name = str(target.get("title") or target.get("object_key") or "")
        self.status_label.setText(f"Assigned {display_name} -> {planet}")

    def open_pdf_placeholder(self, pdf_ref: object) -> None:
        if isinstance(pdf_ref, dict):
            title = str(pdf_ref.get("title") or pdf_ref.get("reference_id") or "Reference")
            path_value = pdf_ref.get("display_path")
            path = Path(str(path_value)) if path_value else None
        else:
            path = Path(pdf_ref)
            title = path.name

        tab_key = str(path) if path is not None else f"reference:{title}"
        for index in range(self.workspace_tabs.count()):
            if self.workspace_tabs.tabToolTip(index) == tab_key:
                self.workspace_tabs.setCurrentIndex(index)
                return

        body = QLabel(self)
        body.setObjectName("knowledge_dashboard")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setMargin(24)
        if path is not None:
            body.setText(f"Reference Preview\n\n{title}\n\n{path}")
        else:
            body.setText(f"Reference Preview\n\n{title}\n\nNo local file is bound yet.")
        index = self.workspace_tabs.addTab(body, title)
        self.workspace_tabs.setTabToolTip(index, tab_key)
        self.workspace_tabs.setCurrentIndex(index)

    def show_about_dialog(self) -> None:
        self._show_message(
            QMessageBox.Icon.Information,
            "About Agni",
            "This build uses the workspace SQLite database for notes, references, links, search, and knowledge model data.",
        )

    def _show_message(self, icon: QMessageBox.Icon, title: str, text: str) -> None:
        message_box = QMessageBox(self)
        message_box.setIcon(icon)
        message_box.setWindowTitle(title)
        message_box.setText(text)
        message_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        message_box.setStyleSheet(build_app_stylesheet())
        message_box.exec()

    def _ask_confirmation(self, title: str, text: str, *, confirm_text: str = "Delete") -> bool:
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
        if yes_button is not None:
            yes_button.setText(confirm_text)
            yes_button.setObjectName("destructive_button")
        return message_box.exec() == QMessageBox.StandardButton.Yes

    def _on_editor_content_changed(self, _text: str) -> None:
        self._update_tab_title()
        self._refresh_document_panels()

    def _on_editor_document_changed(self, editor: NoteEditorWidget) -> None:
        if self.workspace_tabs.currentWidget() is not editor:
            return
        self._update_tab_title(editor)
        self._refresh_document_panels()
        current_path = self._current_note_path()
        if current_path is not None:
            self.outline_dock.set_object_context(self._selection_for_note(current_path))

    def _on_editor_cursor_changed(self, editor: NoteEditorWidget, position: int) -> None:
        if self.workspace_tabs.currentWidget() is editor:
            self.status_label.setText(f"Cursor: {position}")

    def _on_editor_title_changed(self, editor: NoteEditorWidget) -> None:
        self._update_tab_title(editor)
        if self.workspace_tabs.currentWidget() is editor:
            self._refresh_document_panels()

    def _on_editor_status_changed(self, status: str) -> None:
        self._update_tab_title()
        status_text = {
            "idle": "Ready",
            "editing": "Unsaved",
            "saved": "Saved",
            "save_failed": "Save failed",
            "external_modified": "Externally modified",
        }.get(status, status)
        self.status_label.setText(status_text)

    def _refresh_document_panels(self) -> None:
        document = self.editor.get_document()
        self.outline_dock.set_headings(document.extract_headings())
        title = document.title or document.get_title_from_content()
        self.search_dock.update_backlinks(self.current_note_path, title)

    def _selection_for_note(self, note_path: Path) -> KnowledgeSelection:
        document = self._current_editor().get_document()
        satellites = tuple(
            SatelliteItem(
                title=str(getattr(heading, "title", "")),
                kind="heading",
                host_title=note_path.stem,
                line_number=int(getattr(heading, "line_number", 1)),
                preview=f"Markdown heading at line {getattr(heading, 'line_number', 1)}",
            )
            for heading in document.extract_headings()
            if getattr(heading, "title", "")
        )
        return KnowledgeSelection(
            kind=KnowledgeObjectKind.STAR_NOTE,
            title=document.title or document.get_title_from_content() or note_path.stem,
            path=note_path,
            description="Markdown note",
            tags=("note", "markdown"),
            satellites=satellites,
        )

    def _line_number_to_cursor_position(self, text: str, line_number: int) -> int:
        target_line = max(1, line_number)
        position = 0
        for current_line, line in enumerate(text.splitlines(keepends=True), start=1):
            if current_line >= target_line:
                return position
            position += len(line)
        return len(text)

    def _knowledge_dashboard_text(self, selection: KnowledgeSelection) -> str:
        path_text = str(selection.path) if selection.path is not None else "No file path"
        satellites = "\n".join(f"- {item.title}" for item in selection.satellites[:8]) or "- No satellites"
        return (
            f"{selection.title}\n\n"
            f"{selection.description or 'Knowledge model entry'}\n\n"
            f"Path: {path_text}\n\n"
            f"Satellites:\n{satellites}"
        )

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
