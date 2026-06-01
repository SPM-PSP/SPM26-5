from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.models.ui_items import KnowledgeObjectKind, KnowledgeSelection, SatelliteItem


RELATIVE_PATH_ROLE = int(Qt.ItemDataRole.UserRole) + 1
KNOWLEDGE_KIND_ROLE = int(Qt.ItemDataRole.UserRole) + 2
KNOWLEDGE_PATH_ROLE = int(Qt.ItemDataRole.UserRole) + 3
KNOWLEDGE_DESCRIPTION_ROLE = int(Qt.ItemDataRole.UserRole) + 4
KNOWLEDGE_LINE_ROLE = int(Qt.ItemDataRole.UserRole) + 5
KNOWLEDGE_OBJECT_KEY_ROLE = int(Qt.ItemDataRole.UserRole) + 6


class NoteListDock(QDockWidget):
    note_selected = Signal(object)
    delete_note_requested = Signal(object)
    reference_selected = Signal(object)
    reference_edit_requested = Signal(object)
    knowledge_selected = Signal(object)
    assign_to_planet_requested = Signal(object, str)
    new_note_requested = Signal()
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Workspace", parent)
        self.workspace_root: Path | None = None
        self.notes_dir: Path | None = None
        self.attachments_dir: Path | None = None
        self.app_context = None

        self.setObjectName("note_list_dock")
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

        title = QLabel("Workspace Resources", surface)
        title.setObjectName("section_label")
        root_layout.addWidget(title)

        self.tabs = QTabWidget(surface)
        self.model_page = self._build_model_page()
        self.notes_page = self._build_notes_page()
        self.references_page = self._build_references_page()
        self.tabs.addTab(self.model_page, "Model")
        self.tabs.addTab(self.notes_page, "Notes")
        self.tabs.addTab(self.references_page, "References")
        root_layout.addWidget(self.tabs, 1)

        self.setWidget(surface)

    def _build_model_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        hint = QLabel("Galaxy -> Planet -> Star -> Satellite", page)
        hint.setObjectName("section_label")
        layout.addWidget(hint)

        self.knowledge_tree = QTreeWidget(page)
        self.knowledge_tree.setHeaderHidden(True)
        self.knowledge_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.knowledge_tree, 1)

        return page

    def _build_notes_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.note_filter = QLineEdit(page)
        self.note_filter.setPlaceholderText("Filter notes...")
        layout.addWidget(self.note_filter)

        button_row = QHBoxLayout()
        self.new_note_button = QPushButton("New", page)
        self.delete_note_button = QPushButton("Delete", page)
        self.delete_note_button.setObjectName("destructive_button")
        self.refresh_button = QPushButton("Refresh", page)
        button_row.addWidget(self.new_note_button)
        button_row.addWidget(self.delete_note_button)
        button_row.addWidget(self.refresh_button)
        layout.addLayout(button_row)

        self.note_list = QListWidget(page)
        self.note_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.note_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.note_list, 1)
        return page

    def _build_references_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.reference_filter = QLineEdit(page)
        self.reference_filter.setPlaceholderText("Filter references or PDFs...")
        layout.addWidget(self.reference_filter)

        self.reference_list = QListWidget(page)
        self.reference_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.reference_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.reference_list, 1)
        return page

    def _bind_signals(self) -> None:
        self.knowledge_tree.itemClicked.connect(self._emit_knowledge_selected)
        self.knowledge_tree.itemActivated.connect(self._emit_knowledge_selected)
        self.knowledge_tree.customContextMenuRequested.connect(self._show_knowledge_context_menu)
        self.note_filter.textChanged.connect(self._filter_notes)
        self.reference_filter.textChanged.connect(self._filter_references)
        self.note_list.itemActivated.connect(self._emit_note_selected)
        self.note_list.itemClicked.connect(self._emit_note_selected)
        self.note_list.customContextMenuRequested.connect(self._show_note_context_menu)
        self.reference_list.itemActivated.connect(self._emit_reference_selected)
        self.reference_list.itemClicked.connect(self._emit_reference_selected)
        self.reference_list.customContextMenuRequested.connect(self._show_reference_context_menu)
        self.new_note_button.clicked.connect(self.new_note_requested.emit)
        self.delete_note_button.clicked.connect(self._emit_delete_selected)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)

    def bind_app_context(self, app_context) -> None:
        self.app_context = app_context

    def set_workspace(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root)
        self.notes_dir = self.workspace_root / "notes"
        self.attachments_dir = self.workspace_root / "attachments"
        self.refresh()

    def refresh(self) -> None:
        self.refresh_knowledge_model()
        self.refresh_notes()
        self.refresh_references()

    def refresh_knowledge_model(self) -> None:
        self.knowledge_tree.clear()
        if self.workspace_root is None:
            self._add_disabled_tree_item("Workspace is not ready.")
            return

        controller = getattr(self.app_context, "knowledge_controller", None)
        if controller is None:
            self._add_disabled_tree_item("Knowledge controller is not available.")
            return

        result = controller.get_knowledge_model(self.workspace_root)
        if not result["success"]:
            self._add_disabled_tree_item(str(result["message"]))
            return

        galaxy = dict(result["data"].get("galaxy", {}))
        galaxy_item = QTreeWidgetItem([f"Galaxy  {galaxy.get('title') or self.workspace_root.name}"])
        galaxy_item.setToolTip(0, str(galaxy.get("workspace_root") or self.workspace_root))
        galaxy_item.setData(0, KNOWLEDGE_KIND_ROLE, KnowledgeObjectKind.GALAXY.value)
        galaxy_item.setData(0, KNOWLEDGE_PATH_ROLE, str(galaxy.get("workspace_root") or self.workspace_root))
        galaxy_item.setData(0, KNOWLEDGE_DESCRIPTION_ROLE, "Current workspace knowledge graph.")
        self.knowledge_tree.addTopLevelItem(galaxy_item)

        for planet in tuple(galaxy.get("planets", ())):
            planet_item = QTreeWidgetItem([f"Planet  {planet.get('title') or 'Unassigned'}"])
            planet_item.setData(0, KNOWLEDGE_KIND_ROLE, KnowledgeObjectKind.PLANET.value)
            planet_item.setData(0, KNOWLEDGE_DESCRIPTION_ROLE, str(planet.get("description") or ""))
            galaxy_item.addChild(planet_item)

            for star in tuple(planet.get("stars", ())):
                star_kind = KnowledgeObjectKind.STAR_REFERENCE
                if str(star.get("object_kind") or "") == "note":
                    star_kind = KnowledgeObjectKind.STAR_NOTE

                star_item = QTreeWidgetItem([f"Star  {star.get('title') or star.get('object_key') or 'Untitled'}"])
                star_item.setToolTip(0, str(star.get("path") or ""))
                star_item.setData(0, KNOWLEDGE_KIND_ROLE, star_kind.value)
                star_item.setData(0, KNOWLEDGE_OBJECT_KEY_ROLE, str(star.get("object_key") or ""))
                star_item.setData(0, KNOWLEDGE_PATH_ROLE, str(star.get("path") or ""))
                star_item.setData(0, KNOWLEDGE_DESCRIPTION_ROLE, ", ".join(tuple(star.get("tags", ()))))
                planet_item.addChild(star_item)

                for satellite in tuple(star.get("satellites", ())):
                    satellite_item = QTreeWidgetItem(
                        [f"Satellite  {satellite.get('title') or 'Satellite'}"]
                    )
                    satellite_item.setData(0, KNOWLEDGE_KIND_ROLE, KnowledgeObjectKind.SATELLITE.value)
                    satellite_item.setData(0, KNOWLEDGE_PATH_ROLE, str(star.get("path") or ""))
                    satellite_item.setData(
                        0,
                        KNOWLEDGE_DESCRIPTION_ROLE,
                        str(satellite.get("preview") or ""),
                    )
                    satellite_item.setData(0, KNOWLEDGE_LINE_ROLE, satellite.get("line_number"))
                    star_item.addChild(satellite_item)

        self.knowledge_tree.expandToDepth(1)

    def refresh_notes(self) -> None:
        self.note_list.clear()
        if self.workspace_root is None:
            self._add_disabled_item(self.note_list, "Workspace is not ready.")
            return

        controller = getattr(self.app_context, "note_controller", None)
        if controller is None:
            self._add_disabled_item(self.note_list, "Note controller is not available.")
            return

        result = controller.list_notes(self.workspace_root)
        if not result["success"]:
            self._add_disabled_item(self.note_list, str(result["message"]))
            return

        notes = tuple(result["data"].get("notes", ()))
        if not notes:
            self._add_disabled_item(self.note_list, "No Markdown notes found.")
            return

        for note in notes:
            note_path = Path(str(note.get("file_path") or ""))
            item = QListWidgetItem(str(note.get("title") or note_path.stem))
            item.setToolTip(str(note_path))
            item.setData(Qt.ItemDataRole.UserRole, str(note_path))
            item.setData(RELATIVE_PATH_ROLE, str(note.get("relative_path") or note_path.name))
            self.note_list.addItem(item)

        self._filter_notes(self.note_filter.text())

    def refresh_references(self) -> None:
        self.reference_list.clear()
        if self.workspace_root is None:
            self._add_disabled_item(self.reference_list, "Workspace is not ready.")
            return

        controller = getattr(self.app_context, "reference_controller", None)
        if controller is None:
            self._add_disabled_item(self.reference_list, "Reference controller is not available.")
            return

        result = controller.list_references(self.workspace_root)
        if not result["success"]:
            self._add_disabled_item(self.reference_list, str(result["message"]))
            return

        references = tuple(result["data"].get("references", ()))
        if not references:
            self._add_disabled_item(self.reference_list, "No references found.")
            return

        for reference in references:
            payload = self._reference_payload(dict(reference))
            item = QListWidgetItem(payload["label"])
            item.setToolTip(payload["tooltip"])
            item.setData(Qt.ItemDataRole.UserRole, payload)
            self.reference_list.addItem(item)

        self._filter_references(self.reference_filter.text())

    def select_note_path(self, note_path: str | Path) -> None:
        expected = str(note_path)
        for row in range(self.note_list.count()):
            item = self.note_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == expected:
                self.note_list.setCurrentItem(item)
                break

    def selected_note_path(self) -> Path | None:
        item = self.note_list.currentItem()
        if item is None:
            return None

        note_path = item.data(Qt.ItemDataRole.UserRole)
        return Path(note_path) if note_path else None

    def _filter_notes(self, query: str) -> None:
        self._filter_list(self.note_list, query)

    def _filter_references(self, query: str) -> None:
        self._filter_list(self.reference_list, query)

    def _filter_list(self, list_widget: QListWidget, query: str) -> None:
        normalized = query.strip().lower()
        for row in range(list_widget.count()):
            item = list_widget.item(row)
            haystack = f"{item.text()} {item.toolTip()}".lower()
            item.setHidden(bool(normalized) and normalized not in haystack)

    def _emit_note_selected(self, item: QListWidgetItem) -> None:
        note_path = item.data(Qt.ItemDataRole.UserRole)
        if note_path:
            self.note_selected.emit(Path(str(note_path)))

    def _emit_delete_selected(self) -> None:
        note_path = self.selected_note_path()
        if note_path is not None:
            self.delete_note_requested.emit(note_path)

    def _emit_reference_selected(self, item: QListWidgetItem) -> None:
        reference_payload = item.data(Qt.ItemDataRole.UserRole)
        if reference_payload:
            self.reference_selected.emit(reference_payload)

    def _emit_knowledge_selected(self, item: QTreeWidgetItem) -> None:
        selection = self._selection_from_tree_item(item)
        if selection is not None:
            self.knowledge_selected.emit(selection)

    def _show_note_context_menu(self, position) -> None:
        item = self.note_list.itemAt(position)
        if item is None or not item.data(Qt.ItemDataRole.UserRole):
            return

        note_path = Path(str(item.data(Qt.ItemDataRole.UserRole)))
        menu = QMenu(self)
        open_action = QAction("Open", menu)
        delete_action = QAction("Delete", menu)
        copy_path_action = QAction("Copy Path", menu)
        assign_menu = QMenu("Assign Planet", menu)
        assign_actions = {
            planet: QAction(planet, assign_menu)
            for planet in ("Inbox", "Reading", "Research", "Unassigned")
        }
        for action in assign_actions.values():
            assign_menu.addAction(action)
        menu.addAction(open_action)
        menu.addAction(delete_action)
        menu.addMenu(assign_menu)
        menu.addSeparator()
        menu.addAction(copy_path_action)

        open_action.triggered.connect(lambda: self.note_selected.emit(note_path))
        delete_action.triggered.connect(lambda: self.delete_note_requested.emit(note_path))
        for planet, action in assign_actions.items():
            action.triggered.connect(
                lambda _checked=False, target=planet: self.assign_to_planet_requested.emit(
                    {
                        "object_kind": "note",
                        "object_key": note_path.stem,
                        "path": str(note_path),
                        "title": note_path.stem,
                    },
                    target,
                )
            )
        copy_path_action.triggered.connect(lambda: QApplication.clipboard().setText(str(note_path)))
        menu.exec(self.note_list.mapToGlobal(position))

    def _show_reference_context_menu(self, position) -> None:
        item = self.reference_list.itemAt(position)
        if item is None or not item.data(Qt.ItemDataRole.UserRole):
            return

        payload = dict(item.data(Qt.ItemDataRole.UserRole))
        menu = QMenu(self)
        open_action = QAction("Open Reference", menu)
        edit_action = QAction("Edit Metadata", menu)
        menu.addAction(open_action)
        menu.addAction(edit_action)

        display_path = payload.get("display_path")
        if display_path:
            copy_path_action = QAction("Copy Path", menu)
            menu.addAction(copy_path_action)
            copy_path_action.triggered.connect(
                lambda: QApplication.clipboard().setText(str(display_path))
            )

        open_action.triggered.connect(lambda: self.reference_selected.emit(payload))
        edit_action.triggered.connect(lambda: self.reference_edit_requested.emit(payload))
        menu.exec(self.reference_list.mapToGlobal(position))

    def _show_knowledge_context_menu(self, position) -> None:
        item = self.knowledge_tree.itemAt(position)
        if item is None:
            return

        selection = self._selection_from_tree_item(item)
        if selection is None:
            return

        menu = QMenu(self)
        open_action = QAction("Open / View", menu)
        menu.addAction(open_action)
        open_action.triggered.connect(lambda: self.knowledge_selected.emit(selection))

        if selection.path is not None:
            copy_path_action = QAction("Copy Path", menu)
            menu.addAction(copy_path_action)
            copy_path_action.triggered.connect(
                lambda: QApplication.clipboard().setText(str(selection.path))
            )

        if selection.kind in {KnowledgeObjectKind.STAR_NOTE, KnowledgeObjectKind.STAR_REFERENCE}:
            assign_menu = QMenu("Assign Planet", menu)
            for planet in ("Inbox", "Reading", "Research", "Unassigned"):
                action = QAction(planet, assign_menu)
                action.triggered.connect(
                    lambda _checked=False, target=planet: self.assign_to_planet_requested.emit(
                        {
                            "object_kind": (
                                "reference"
                                if selection.kind == KnowledgeObjectKind.STAR_REFERENCE
                                else "note"
                            ),
                            "object_key": str(item.data(0, KNOWLEDGE_OBJECT_KEY_ROLE) or selection.title),
                            "path": str(selection.path) if selection.path is not None else None,
                            "title": selection.title,
                        },
                        target,
                    )
                )
                assign_menu.addAction(action)
            menu.addMenu(assign_menu)

        menu.exec(self.knowledge_tree.mapToGlobal(position))

    def _selection_from_tree_item(self, item: QTreeWidgetItem) -> KnowledgeSelection | None:
        kind_value = item.data(0, KNOWLEDGE_KIND_ROLE)
        if not kind_value:
            return None

        path_value = item.data(0, KNOWLEDGE_PATH_ROLE)
        path = Path(path_value) if path_value else None
        description = item.data(0, KNOWLEDGE_DESCRIPTION_ROLE) or ""
        title = (
            item.text(0)
            .replace("Galaxy  ", "")
            .replace("Planet  ", "")
            .replace("Star  ", "")
            .replace("Satellite  ", "")
        )
        return KnowledgeSelection(
            kind=KnowledgeObjectKind(kind_value),
            title=title,
            path=path,
            description=str(description),
            tags=self._infer_tags_for_title(title),
            satellites=tuple(self._satellites_for_tree_item(item)),
        )

    def _satellites_for_tree_item(self, item: QTreeWidgetItem) -> list[SatelliteItem]:
        satellites: list[SatelliteItem] = []
        children: list[QTreeWidgetItem] = []

        if item.data(0, KNOWLEDGE_KIND_ROLE) == KnowledgeObjectKind.SATELLITE.value:
            children.append(item)
        else:
            for index in range(item.childCount()):
                child = item.child(index)
                if child.data(0, KNOWLEDGE_KIND_ROLE) == KnowledgeObjectKind.SATELLITE.value:
                    children.append(child)

        for child in children:
            line_number = child.data(0, KNOWLEDGE_LINE_ROLE)
            satellites.append(
                SatelliteItem(
                    title=child.text(0).replace("Satellite  ", ""),
                    kind="ui-entry",
                    host_title=item.text(0),
                    line_number=int(line_number) if line_number else None,
                    preview=str(child.data(0, KNOWLEDGE_DESCRIPTION_ROLE) or ""),
                )
            )
        return satellites

    def _reference_payload(self, reference: dict[str, object]) -> dict[str, object]:
        reference_id = str(reference.get("reference_id") or "")
        title = str(reference.get("title") or reference_id or "Untitled reference")
        year = reference.get("year")
        authors = tuple(str(author) for author in reference.get("authors", ()) if str(author))
        tags = tuple(str(tag) for tag in reference.get("tags", ()) if str(tag))
        entry_type = str(reference.get("entry_type") or "reference")
        pdf_path = str(reference.get("pdf_path")) if reference.get("pdf_path") else None
        source_path = str(reference.get("source_path")) if reference.get("source_path") else None
        display_path = pdf_path or source_path
        label = f"{title} ({year})" if year not in (None, "") else title
        tooltip = "\n".join(
            part
            for part in (
                reference_id,
                ", ".join(authors),
                f"tags: {', '.join(tags)}" if tags else "",
                display_path or "",
            )
            if part
        )
        return {
            "reference_id": reference_id,
            "title": title,
            "authors": authors,
            "tags": tags,
            "year": year,
            "entry_type": entry_type,
            "pdf_path": pdf_path,
            "source_path": source_path,
            "display_path": display_path,
            "label": label,
            "tooltip": tooltip,
        }

    def _infer_tags_for_title(self, title: str) -> tuple[str, ...]:
        tags: list[str] = []
        lowered = title.lower()
        if "pdf" in lowered or "reference" in lowered:
            tags.append("reference")
        if "inbox" in lowered:
            tags.append("inbox")
        if "note" in lowered or title.endswith(".md"):
            tags.append("note")
        return tuple(tags)

    def _add_disabled_item(self, list_widget: QListWidget, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        list_widget.addItem(item)

    def _add_disabled_tree_item(self, text: str) -> None:
        item = QTreeWidgetItem([text])
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.knowledge_tree.addTopLevelItem(item)
