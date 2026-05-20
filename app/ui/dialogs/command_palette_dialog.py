from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.actions import build_app_stylesheet
from app.ui.models.ui_items import CommandItem


COMMAND_ROLE = int(Qt.ItemDataRole.UserRole)


class CommandPaletteDialog(QDialog):
    def __init__(
        self,
        commands: Sequence[CommandItem],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.commands = list(commands)
        self.setObjectName("command_palette_dialog")
        self.setWindowTitle("命令面板")
        self.setStyleSheet(build_app_stylesheet())
        self.resize(420, 440)

        self._build_ui()
        self._bind_signals()
        self._populate_commands()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("选择一个常用操作", self)
        title.setObjectName("section_label")
        layout.addWidget(title)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("搜索命令...")
        layout.addWidget(self.search_input)

        self.command_list = QListWidget(self)
        layout.addWidget(self.command_list, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setText("关闭")
        layout.addWidget(buttons)

        buttons.rejected.connect(self.reject)

    def _bind_signals(self) -> None:
        self.search_input.textChanged.connect(self._filter_commands)
        self.command_list.itemActivated.connect(self._run_item)
        self.command_list.itemDoubleClicked.connect(self._run_item)

    def _populate_commands(self) -> None:
        self.command_list.clear()
        for index, command in enumerate(self.commands):
            item = QListWidgetItem(command.title)
            if command.description:
                item.setToolTip(command.description)
            item.setData(COMMAND_ROLE, index)
            self.command_list.addItem(item)

        if self.command_list.count() > 0:
            self.command_list.setCurrentRow(0)

    def _filter_commands(self, query: str) -> None:
        normalized = query.strip().lower()
        for row in range(self.command_list.count()):
            item = self.command_list.item(row)
            index = item.data(COMMAND_ROLE)
            command = self.commands[index]
            haystack = f"{command.title} {command.description}".lower()
            item.setHidden(bool(normalized) and normalized not in haystack)

    def _run_item(self, item: QListWidgetItem) -> None:
        index = item.data(COMMAND_ROLE)
        if index is None:
            return

        self.accept()
        self.commands[index].callback()
