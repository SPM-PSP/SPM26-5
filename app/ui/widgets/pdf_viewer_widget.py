from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    import fitz  # type: ignore[import-not-found]
except ModuleNotFoundError:
    fitz = None


class PdfViewerWidget(QWidget):
    def __init__(self, pdf_payload: dict[str, object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pdf_payload = dict(pdf_payload)
        self.pdf_path = Path(str(pdf_payload.get("file_path") or ""))
        self.document = fitz.open(self.pdf_path) if fitz is not None else None
        self.current_page_index = 0
        self.zoom = 1.35
        self._build_ui()
        if self.document is None:
            self._render_unavailable()
        else:
            self._render_page()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        self.prev_button = QPushButton("Prev", self)
        self.next_button = QPushButton("Next", self)
        self.page_label = QLabel(self)
        self.meta_label = QLabel(self)
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        toolbar.addWidget(self.prev_button)
        toolbar.addWidget(self.next_button)
        toolbar.addWidget(self.page_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self.meta_label)
        layout.addLayout(toolbar)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label = QLabel(self.scroll_area)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area, 1)

        self.prev_button.clicked.connect(self.show_previous_page)
        self.next_button.clicked.connect(self.show_next_page)

    def closeEvent(self, event) -> None:
        try:
            if self.document is not None:
                self.document.close()
        finally:
            super().closeEvent(event)

    def show_previous_page(self) -> None:
        if self.current_page_index <= 0:
            return
        self.current_page_index -= 1
        self._render_page()

    def show_next_page(self) -> None:
        if self.document is None or self.current_page_index >= self.document.page_count - 1:
            return
        self.current_page_index += 1
        self._render_page()

    def _render_page(self) -> None:
        if self.document is None or fitz is None:
            self._render_unavailable()
            return

        from PySide6.QtGui import QImage, QPixmap

        page = self.document.load_page(self.current_page_index)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom), alpha=False)
        image = QImage(
            pixmap.samples,
            pixmap.width,
            pixmap.height,
            pixmap.stride,
            QImage.Format.Format_RGB888,
        ).copy()
        self.image_label.setPixmap(QPixmap.fromImage(image))
        self.page_label.setText(f"Page {self.current_page_index + 1} / {self.document.page_count}")
        file_size = self.pdf_payload.get("file_size")
        file_size_text = f"{int(file_size) // 1024} KB" if isinstance(file_size, int) else ""
        self.meta_label.setText(f"{self.pdf_path.name}  {file_size_text}".strip())
        self.prev_button.setEnabled(self.current_page_index > 0)
        self.next_button.setEnabled(self.current_page_index < self.document.page_count - 1)

    def _render_unavailable(self) -> None:
        page_count = self.pdf_payload.get("page_count")
        page_text = f"Pages: {page_count}" if page_count not in (None, "") else "Pages: unknown"
        self.image_label.setText(
            f"PDF preview renderer is not available in this environment.\n\n{self.pdf_path}\n\n{page_text}"
        )
        self.page_label.setText(page_text)
        self.meta_label.setText(self.pdf_path.name)
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
