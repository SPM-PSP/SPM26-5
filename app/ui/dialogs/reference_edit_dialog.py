from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.actions import build_app_stylesheet


class ReferenceEditDialog(QDialog):
    def __init__(self, reference: dict[str, object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.reference = dict(reference)
        self.setWindowTitle("Edit Reference")
        self.setStyleSheet(build_app_stylesheet())
        self.resize(460, 280)
        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self.title_edit = QLineEdit(self)
        self.authors_edit = QLineEdit(self)
        self.year_edit = QLineEdit(self)
        self.tags_edit = QLineEdit(self)
        self.entry_type_edit = QComboBox(self)
        self.entry_type_edit.setEditable(True)
        self.entry_type_edit.addItems(["reference", "article", "book", "thesis", "pdf", "report"])

        form.addRow("Title", self.title_edit)
        form.addRow("Authors", self.authors_edit)
        form.addRow("Year", self.year_edit)
        form.addRow("Tags", self.tags_edit)
        form.addRow("Type", self.entry_type_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self) -> None:
        self.title_edit.setText(str(self.reference.get("title") or ""))
        self.authors_edit.setText(", ".join(str(author) for author in self.reference.get("authors", ())))
        year = self.reference.get("year")
        self.year_edit.setText("" if year in (None, "") else str(year))
        self.tags_edit.setText(", ".join(str(tag) for tag in self.reference.get("tags", ())))
        entry_type = str(self.reference.get("entry_type") or "reference")
        index = self.entry_type_edit.findText(entry_type)
        if index >= 0:
            self.entry_type_edit.setCurrentIndex(index)
        else:
            self.entry_type_edit.setCurrentText(entry_type)

    def payload(self) -> dict[str, object]:
        return {
            "title": self.title_edit.text().strip(),
            "authors": tuple(
                part.strip() for part in self.authors_edit.text().split(",") if part.strip()
            ),
            "year": self.year_edit.text().strip(),
            "tags": tuple(
                part.strip() for part in self.tags_edit.text().split(",") if part.strip()
            ),
            "entry_type": self.entry_type_edit.currentText().strip() or "reference",
        }
