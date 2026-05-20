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


class NoteListDock(QDockWidget):
    note_selected = Signal(object)
    delete_note_requested = Signal(object)
    reference_selected = Signal(object)
    knowledge_selected = Signal(object)
    assign_to_planet_requested = Signal(object, str)
    new_note_requested = Signal()
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("资源库", parent)
        self.workspace_root: Path | None = None
        self.notes_dir: Path | None = None
        self.attachments_dir: Path | None = None
        self.planet_overrides: dict[str, str] = {}

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

        title = QLabel("工作区资源", surface)
        title.setObjectName("section_label")
        root_layout.addWidget(title)

        self.tabs = QTabWidget(surface)
        self.model_page = self._build_model_page()
        self.notes_page = self._build_notes_page()
        self.references_page = self._build_references_page()
        self.tabs.addTab(self.model_page, "模型")
        self.tabs.addTab(self.notes_page, "笔记")
        self.tabs.addTab(self.references_page, "文献")
        root_layout.addWidget(self.tabs, 1)

        self.setWidget(surface)

    def _build_model_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        hint = QLabel("星系 → 行星 → 星球 → 卫星", page)
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
        self.note_filter.setPlaceholderText("筛选笔记...")
        layout.addWidget(self.note_filter)

        button_row = QHBoxLayout()
        self.new_note_button = QPushButton("新建", page)
        self.delete_note_button = QPushButton("删除", page)
        self.delete_note_button.setObjectName("destructive_button")
        self.refresh_button = QPushButton("刷新", page)
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
        self.reference_filter.setPlaceholderText("筛选文献或 PDF...")
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
            self._add_disabled_tree_item("尚未打开工作区")
            return

        galaxy = QTreeWidgetItem([f"星系  {self.workspace_root.name}"])
        galaxy.setToolTip(0, str(self.workspace_root))
        galaxy.setData(0, KNOWLEDGE_KIND_ROLE, KnowledgeObjectKind.GALAXY.value)
        galaxy.setData(0, KNOWLEDGE_PATH_ROLE, str(self.workspace_root))
        galaxy.setData(0, KNOWLEDGE_DESCRIPTION_ROLE, "当前工作区代表一个知识体系。")
        self.knowledge_tree.addTopLevelItem(galaxy)

        planets = (
            ("Inbox", "收集箱与临时想法", "inbox"),
            ("Reading", "阅读中的文献与摘录", "reading"),
            ("Research", "研究主题与长期项目", "research"),
            ("未归类", "尚未归入具体行星的对象", ""),
        )
        planet_items: dict[str, QTreeWidgetItem] = {}
        for title, description, filter_text in planets:
            planet = QTreeWidgetItem([f"行星  {title}"])
            planet.setData(0, KNOWLEDGE_KIND_ROLE, KnowledgeObjectKind.PLANET.value)
            planet.setData(0, KNOWLEDGE_DESCRIPTION_ROLE, description)
            planet.setData(0, Qt.ItemDataRole.UserRole, filter_text)
            galaxy.addChild(planet)
            planet_items[title] = planet

        for note_path in self._iter_note_paths():
            planet_title = self._guess_planet_for_path(note_path)
            note_title = self._note_display_title(note_path)
            star = QTreeWidgetItem([f"星球  {note_title}"])
            star.setToolTip(0, str(note_path))
            star.setData(0, KNOWLEDGE_KIND_ROLE, KnowledgeObjectKind.STAR_NOTE.value)
            star.setData(0, KNOWLEDGE_PATH_ROLE, str(note_path))
            star.setData(0, KNOWLEDGE_DESCRIPTION_ROLE, "Markdown 笔记星球")
            planet_items.get(planet_title, planet_items["未归类"]).addChild(star)

            for satellite in self._extract_note_satellites(note_path):
                item = QTreeWidgetItem([f"卫星  {satellite.title}"])
                item.setToolTip(0, satellite.preview)
                item.setData(0, KNOWLEDGE_KIND_ROLE, KnowledgeObjectKind.SATELLITE.value)
                item.setData(0, KNOWLEDGE_PATH_ROLE, str(note_path))
                item.setData(0, KNOWLEDGE_DESCRIPTION_ROLE, satellite.preview)
                item.setData(0, KNOWLEDGE_LINE_ROLE, satellite.line_number)
                star.addChild(item)

        for ref_path in self._iter_reference_paths():
            star = QTreeWidgetItem([f"星球  {ref_path.name}"])
            star.setToolTip(0, str(ref_path))
            star.setData(0, KNOWLEDGE_KIND_ROLE, KnowledgeObjectKind.STAR_REFERENCE.value)
            star.setData(0, KNOWLEDGE_PATH_ROLE, str(ref_path))
            star.setData(0, KNOWLEDGE_DESCRIPTION_ROLE, "文献或附件星球")
            planet_items["Reading"].addChild(star)

            satellite = QTreeWidgetItem(["卫星  元数据 / 批注占位"])
            satellite.setData(0, KNOWLEDGE_KIND_ROLE, KnowledgeObjectKind.SATELLITE.value)
            satellite.setData(0, KNOWLEDGE_PATH_ROLE, str(ref_path))
            satellite.setData(0, KNOWLEDGE_DESCRIPTION_ROLE, "后续接入 PDF 批注、摘录、版本记录。")
            satellite.setData(0, KNOWLEDGE_LINE_ROLE, None)
            star.addChild(satellite)

        self.knowledge_tree.expandToDepth(1)

    def refresh_notes(self) -> None:
        self.note_list.clear()
        if self.notes_dir is None or not self.notes_dir.exists():
            self._add_disabled_item(self.note_list, "尚未发现 notes 目录")
            return

        note_paths = self._iter_note_paths()
        if not note_paths:
            self._add_disabled_item(self.note_list, "暂无 Markdown 笔记")
            return

        for note_path in note_paths:
            rel_path = note_path.relative_to(self.notes_dir)
            item = QListWidgetItem(self._note_display_title(note_path))
            item.setToolTip(str(note_path))
            item.setData(Qt.ItemDataRole.UserRole, str(note_path))
            item.setData(RELATIVE_PATH_ROLE, str(rel_path))
            self.note_list.addItem(item)

        self._filter_notes(self.note_filter.text())

    def refresh_references(self) -> None:
        self.reference_list.clear()
        if self.workspace_root is None:
            self._add_disabled_item(self.reference_list, "尚未打开工作区")
            return

        candidates = self._iter_reference_paths()

        if not candidates:
            self._add_disabled_item(self.reference_list, "暂无文献文件")
            return

        for ref_path in sorted(candidates, key=lambda item: item.name.lower()):
            item = QListWidgetItem(ref_path.name)
            item.setToolTip(str(ref_path))
            item.setData(Qt.ItemDataRole.UserRole, str(ref_path))
            self.reference_list.addItem(item)

        self._filter_references(self.reference_filter.text())

    def select_note_path(self, note_path: str | Path) -> None:
        expected = str(note_path)
        for row in range(self.note_list.count()):
            item = self.note_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == expected:
                self.note_list.setCurrentItem(item)
                break

    def assign_path_to_planet(self, path: str | Path, planet: str) -> None:
        self.planet_overrides[str(Path(path).resolve())] = planet
        self.refresh_knowledge_model()

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
            self.note_selected.emit(Path(note_path))

    def _emit_delete_selected(self) -> None:
        note_path = self.selected_note_path()
        if note_path is not None:
            self.delete_note_requested.emit(note_path)

    def _emit_reference_selected(self, item: QListWidgetItem) -> None:
        reference_path = item.data(Qt.ItemDataRole.UserRole)
        if reference_path:
            self.reference_selected.emit(Path(reference_path))

    def _emit_knowledge_selected(self, item: QTreeWidgetItem) -> None:
        selection = self._selection_from_tree_item(item)
        if selection is not None:
            self.knowledge_selected.emit(selection)

    def _show_note_context_menu(self, position) -> None:
        item = self.note_list.itemAt(position)
        if item is None or not item.data(Qt.ItemDataRole.UserRole):
            return

        note_path = Path(item.data(Qt.ItemDataRole.UserRole))
        menu = QMenu(self)
        open_action = QAction("打开", menu)
        delete_action = QAction("删除", menu)
        copy_path_action = QAction("复制路径", menu)
        assign_menu = QMenu("归入行星", menu)
        assign_actions = {
            planet: QAction(planet, assign_menu)
            for planet in ("Inbox", "Reading", "Research")
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
                    note_path,
                    target,
                )
            )
        copy_path_action.triggered.connect(lambda: QApplication.clipboard().setText(str(note_path)))
        menu.exec(self.note_list.mapToGlobal(position))

    def _show_reference_context_menu(self, position) -> None:
        item = self.reference_list.itemAt(position)
        if item is None or not item.data(Qt.ItemDataRole.UserRole):
            return

        reference_path = Path(item.data(Qt.ItemDataRole.UserRole))
        menu = QMenu(self)
        open_action = QAction("打开文献", menu)
        copy_path_action = QAction("复制路径", menu)
        menu.addAction(open_action)
        menu.addAction(copy_path_action)

        open_action.triggered.connect(lambda: self.reference_selected.emit(reference_path))
        copy_path_action.triggered.connect(
            lambda: QApplication.clipboard().setText(str(reference_path))
        )
        menu.exec(self.reference_list.mapToGlobal(position))

    def _show_knowledge_context_menu(self, position) -> None:
        item = self.knowledge_tree.itemAt(position)
        if item is None:
            return

        selection = self._selection_from_tree_item(item)
        if selection is None:
            return

        menu = QMenu(self)
        open_action = QAction("打开 / 查看", menu)
        copy_path_action = QAction("复制路径", menu)
        assign_menu = QMenu("归入行星", menu)
        assign_actions = {
            planet: QAction(planet, assign_menu)
            for planet in ("Inbox", "Reading", "Research")
        }
        for action in assign_actions.values():
            assign_menu.addAction(action)
        menu.addAction(open_action)
        if selection.path is not None:
            menu.addAction(copy_path_action)
        if selection.kind in {
            KnowledgeObjectKind.STAR_NOTE,
            KnowledgeObjectKind.STAR_REFERENCE,
        }:
            menu.addMenu(assign_menu)

        open_action.triggered.connect(lambda: self.knowledge_selected.emit(selection))
        if selection.path is not None:
            copy_path_action.triggered.connect(
                lambda: QApplication.clipboard().setText(str(selection.path))
            )
            for planet, action in assign_actions.items():
                action.triggered.connect(
                    lambda _checked=False, target=planet: self.assign_to_planet_requested.emit(
                        selection.path,
                        target,
                    )
                )
        menu.exec(self.knowledge_tree.mapToGlobal(position))

    def _selection_from_tree_item(self, item: QTreeWidgetItem) -> KnowledgeSelection | None:
        kind_value = item.data(0, KNOWLEDGE_KIND_ROLE)
        if not kind_value:
            return None

        path_value = item.data(0, KNOWLEDGE_PATH_ROLE)
        path = Path(path_value) if path_value else None
        description = item.data(0, KNOWLEDGE_DESCRIPTION_ROLE) or ""
        title = item.text(0).replace("星系  ", "").replace("行星  ", "").replace(
            "星球  ", ""
        ).replace("卫星  ", "")
        return KnowledgeSelection(
            kind=KnowledgeObjectKind(kind_value),
            title=title,
            path=path,
            description=description,
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
            title = child.text(0).replace("卫星  ", "")
            line_number = child.data(0, KNOWLEDGE_LINE_ROLE)
            satellites.append(
                SatelliteItem(
                    title=title,
                    kind="ui-entry",
                    host_title=item.text(0),
                    line_number=int(line_number) if line_number else None,
                    preview=child.data(0, KNOWLEDGE_DESCRIPTION_ROLE) or "",
                )
            )
        return satellites

    def _iter_note_paths(self) -> list[Path]:
        if self.notes_dir is None or not self.notes_dir.exists():
            return []
        return sorted(self.notes_dir.rglob("*.md"), key=lambda item: item.name.lower())

    def _iter_reference_paths(self) -> list[Path]:
        if self.workspace_root is None:
            return []

        candidates: list[Path] = []
        for folder_name in ("references", "attachments"):
            folder = self.workspace_root / folder_name
            if folder.exists():
                candidates.extend(
                    path
                    for path in folder.rglob("*")
                    if path.is_file() and path.suffix.lower() in {".pdf", ".bib", ".ris"}
                )
        return sorted(candidates, key=lambda item: item.name.lower())

    def _guess_planet_for_path(self, note_path: Path) -> str:
        override = self.planet_overrides.get(str(note_path.resolve()))
        if override:
            return override

        lowered = str(note_path).lower()
        if "inbox" in lowered:
            return "Inbox"
        if "reading" in lowered or "paper" in lowered or "pdf" in lowered:
            return "Reading"
        if "research" in lowered or "project" in lowered:
            return "Research"
        return "未归类"

    def _note_display_title(self, note_path: Path) -> str:
        return note_path.stem

    def _extract_note_satellites(self, note_path: Path) -> list[SatelliteItem]:
        try:
            text = note_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return []

        satellites: list[SatelliteItem] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                if title:
                    satellites.append(
                        SatelliteItem(
                            title=title[:40],
                            kind="heading",
                            host_title=note_path.stem,
                            line_number=line_number,
                            preview=f"标题锚点，第 {line_number} 行",
                        )
                    )
            elif stripped.startswith(">") and len(satellites) < 8:
                satellites.append(
                    SatelliteItem(
                        title="摘录",
                        kind="quote",
                        host_title=note_path.stem,
                        line_number=line_number,
                        preview=stripped[:80],
                    )
                )
            if len(satellites) >= 8:
                break
        return satellites

    def _infer_tags_for_title(self, title: str) -> tuple[str, ...]:
        tags = []
        lowered = title.lower()
        if "pdf" in lowered or "文献" in title:
            tags.append("文献")
        if "inbox" in lowered:
            tags.append("收集箱")
        if "笔记" in title or title.endswith(".md"):
            tags.append("笔记")
        return tuple(tags)

    def _add_disabled_item(self, list_widget: QListWidget, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        list_widget.addItem(item)

    def _add_disabled_tree_item(self, text: str) -> None:
        item = QTreeWidgetItem([text])
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.knowledge_tree.addTopLevelItem(item)
