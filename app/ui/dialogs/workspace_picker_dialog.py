from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.actions import build_app_stylesheet


class WorkspacePickerDialog(QDialog):
    def __init__(
        self,
        *,
        initial_path: str | Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("选择工作区")
        self.setStyleSheet(build_app_stylesheet())
        self.resize(560, 150)

        self._build_ui()
        if initial_path is not None:
            self.path_edit.setText(str(initial_path))

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("选择 Agni 工作区", self)
        title.setObjectName("section_label")
        layout.addWidget(title)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(self)
        self.path_edit.setPlaceholderText("选择或输入工作区目录...")
        browse_button = QPushButton("浏览", self)
        browse_button.clicked.connect(self._browse_workspace)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse_button)
        layout.addLayout(path_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("选择")
        if cancel_button is not None:
            cancel_button.setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_workspace(self) -> Path | None:
        value = self.path_edit.text().strip()
        return Path(value).expanduser() if value else None

    def _browse_workspace(self) -> None:
        start_dir = self.path_edit.text().strip() or str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, "选择工作区", start_dir)
        if selected:
            self.path_edit.setText(selected)
