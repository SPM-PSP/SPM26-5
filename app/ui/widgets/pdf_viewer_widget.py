from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Signal, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.models.ui_items import PdfAnnotationDraft, PdfDocumentItem

try:
    import fitz  # PyMuPDF

    PYMUPDF_IMPORT_ERROR: Exception | None = None
except Exception as error:  # pragma: no cover - depends on local environment.
    fitz = None  # type: ignore[assignment]
    PYMUPDF_IMPORT_ERROR = error


class PdfPageLabel(QLabel):
    selection_completed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_origin: QPoint | None = None
        self._drag_rect = QRect()
        self._selection_rects: list[QRect] = []
        self._page_pixmap = QPixmap()
        self._page_size = QSize()
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.IBeamCursor)

    def set_rendered_page(self, pixmap: QPixmap, display_size: QSize) -> None:
        self._page_pixmap = pixmap
        self._page_size = display_size
        self.clear()
        self.resize(display_size)
        self.setMinimumSize(display_size)
        self.update()

    def clear_rendered_page(self) -> None:
        self._page_pixmap = QPixmap()
        self._page_size = QSize()
        self.clear_selection()

    def set_selection_rects(self, rects: list[QRect]) -> None:
        self._selection_rects = [rect.normalized() for rect in rects]
        self.update()

    def clear_selection(self) -> None:
        self._drag_origin = None
        self._drag_rect = QRect()
        self._selection_rects = []
        self.update()

    def mousePressEvent(self, event) -> None:
        position = event.position().toPoint()
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._page_pixmap.isNull()
            and self._pixmap_rect().contains(position)
        ):
            self._drag_origin = position
            self._drag_rect = QRect(self._drag_origin, self._drag_origin)
            self.update()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_origin is not None:
            self._drag_rect = QRect(self._drag_origin, event.position().toPoint()).normalized()
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_origin is not None:
            self._drag_rect = QRect(self._drag_origin, event.position().toPoint()).normalized()
            finished = self._widget_rect_to_image_rect(self._drag_rect)
            self._drag_origin = None
            self._drag_rect = QRect()
            if finished.width() >= 3 and finished.height() >= 3:
                self.selection_completed.emit(finished)
            self.update()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        if self._page_pixmap.isNull():
            super().paintEvent(event)
            return

        pixmap_rect = self._pixmap_rect()
        if pixmap_rect.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(pixmap_rect, self._page_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(QColor(103, 188, 255, 210), 1))
        painter.setBrush(QColor(103, 188, 255, 65))
        for rect in self._selection_rects:
            painter.drawRoundedRect(rect.translated(pixmap_rect.topLeft()), 1, 1)
        if not self._drag_rect.isNull():
            visible_drag_rect = self._drag_rect.intersected(pixmap_rect)
            if visible_drag_rect.isNull():
                return
            painter.setPen(QPen(QColor(120, 214, 255, 230), 1, Qt.PenStyle.DashLine))
            painter.setBrush(QColor(120, 214, 255, 35))
            painter.drawRoundedRect(visible_drag_rect, 1, 1)

    def _pixmap_rect(self) -> QRect:
        if self._page_pixmap.isNull() or self._page_size.isEmpty():
            return QRect()

        rect = self.contentsRect()
        x = rect.left()
        y = rect.top()
        alignment = self.alignment()
        if alignment & Qt.AlignmentFlag.AlignHCenter:
            x += max(0, (rect.width() - self._page_size.width()) // 2)
        elif alignment & Qt.AlignmentFlag.AlignRight:
            x += max(0, rect.width() - self._page_size.width())
        if alignment & Qt.AlignmentFlag.AlignVCenter:
            y += max(0, (rect.height() - self._page_size.height()) // 2)
        elif alignment & Qt.AlignmentFlag.AlignBottom:
            y += max(0, rect.height() - self._page_size.height())
        return QRect(x, y, self._page_size.width(), self._page_size.height())

    def _widget_rect_to_image_rect(self, rect: QRect) -> QRect:
        pixmap_rect = self._pixmap_rect()
        if pixmap_rect.isNull():
            return QRect()

        clipped = rect.normalized().intersected(pixmap_rect)
        if clipped.isNull():
            return QRect()
        clipped.translate(-pixmap_rect.left(), -pixmap_rect.top())
        return clipped


class PdfViewerWidget(QWidget):
    page_changed = Signal(int)
    zoom_changed = Signal(float)
    annotation_requested = Signal(object)
    excerpt_insert_requested = Signal(str)
    citation_insert_requested = Signal(str)
    external_open_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pdf_item: PdfDocumentItem | None = None
        self.pdf_document = None
        self.current_page = 1
        self.page_count = 1
        self.zoom_factor = 1.0
        self._last_extracted_page = 0
        self._current_words: list[tuple[float, float, float, float, str, int, int, int]] = []
        self._selected_rects: tuple[dict[str, float], ...] = ()
        self._page_sidebar_visible = False
        self._inspector_visible = False
        self._metadata_title = ""
        self._metadata_relative_path = ""
        self._metadata_file_size = 0
        self._render_quality_scale = 3.0
        self._last_render_source_size: tuple[int, int] = (0, 0)

        self.setObjectName("pdf_viewer_widget")
        self._build_ui()
        self._bind_signals()
        self._set_empty_state()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.title_label = QLabel("PDF 阅读器", self)
        self.title_label.setObjectName("section_label")
        self.path_label = QLabel("尚未打开 PDF", self)
        self.path_label.setObjectName("muted_label")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.path_label, 1)
        root_layout.addLayout(header_layout)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(6)

        self.page_sidebar_button = QToolButton(self)
        self.page_sidebar_button.setText("页栏")
        self.page_sidebar_button.setCheckable(True)
        self.page_sidebar_button.setChecked(self._page_sidebar_visible)
        self.page_sidebar_button.setToolTip("显示或隐藏左侧页码列表")
        self.prev_button = QToolButton(self)
        self.prev_button.setText("上一页")
        self.next_button = QToolButton(self)
        self.next_button.setText("下一页")
        self.page_spin = QSpinBox(self)
        self.page_spin.setObjectName("pdf_page_spin")
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.page_spin.setKeyboardTracking(False)
        self.page_spin.setFixedWidth(52)
        self.page_spin.setToolTip("输入页码后按 Enter 跳转")
        self.page_label = QLabel("/ 1", self)

        self.zoom_out_button = QToolButton(self)
        self.zoom_out_button.setText("缩小")
        self.zoom_in_button = QToolButton(self)
        self.zoom_in_button.setText("放大")
        self.fit_width_button = QToolButton(self)
        self.fit_width_button.setText("适宽")

        self.open_external_button = QToolButton(self)
        self.open_external_button.setText("外部打开")
        self.highlight_button = QPushButton("批注", self)
        self.excerpt_button = QPushButton("摘录到笔记", self)
        self.citation_button = QPushButton("插入引用", self)
        self.inspector_button = QToolButton(self)
        self.inspector_button.setText("信息")
        self.inspector_button.setCheckable(True)
        self.inspector_button.setChecked(self._inspector_visible)
        self.inspector_button.setToolTip("显示或隐藏右侧文献信息")

        toolbar_layout.addWidget(self.page_sidebar_button)
        toolbar_layout.addSpacing(4)
        toolbar_layout.addWidget(self.prev_button)
        toolbar_layout.addWidget(self.page_spin)
        toolbar_layout.addWidget(self.page_label)
        toolbar_layout.addWidget(self.next_button)
        toolbar_layout.addSpacing(8)
        toolbar_layout.addWidget(self.zoom_out_button)
        toolbar_layout.addWidget(self.zoom_in_button)
        toolbar_layout.addWidget(self.fit_width_button)
        toolbar_layout.addSpacing(8)
        toolbar_layout.addWidget(self.highlight_button)
        toolbar_layout.addWidget(self.excerpt_button)
        toolbar_layout.addWidget(self.citation_button)
        toolbar_layout.addWidget(self.inspector_button)
        toolbar_layout.addWidget(self.open_external_button)
        toolbar_layout.addStretch(1)
        root_layout.addLayout(toolbar_layout)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setObjectName("pdf_splitter")

        self.thumbnail_list = QListWidget(self.splitter)
        self.thumbnail_list.setObjectName("pdf_thumbnail_list")
        self.thumbnail_list.setFixedWidth(150)

        preview_panel = QWidget(self.splitter)
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(8)

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal, preview_panel)
        self.content_splitter.setObjectName("pdf_content_splitter")
        self.content_splitter.setChildrenCollapsible(False)

        self.scroll_area = QScrollArea(self.content_splitter)
        self.scroll_area.setObjectName("pdf_preview_surface")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_image_label = PdfPageLabel(self.scroll_area)
        self.page_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_image_label.setWordWrap(True)
        self.page_image_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.scroll_area.setWidget(self.page_image_label)

        self.selection_box = QTextEdit(self.content_splitter)
        self.selection_box.setObjectName("pdf_selection_box")
        self.selection_box.setPlaceholderText("拖拽选择文字，摘录内容会显示在这里。")
        self.selection_box.setToolTip(
            "在 PDF 页面上拖拽划词，选中文字会显示在这里；可编辑后摘录、批注或插入引用。"
        )
        self.selection_box.setMinimumWidth(280)
        self.content_splitter.addWidget(self.scroll_area)
        self.content_splitter.addWidget(self.selection_box)
        self.content_splitter.setSizes([900, 360])
        preview_layout.addWidget(self.content_splitter, 1)

        self.inspector_panel = QWidget(self.splitter)
        self.inspector_panel.setObjectName("pdf_inspector_panel")
        inspector_layout = QVBoxLayout(self.inspector_panel)
        inspector_layout.setContentsMargins(8, 0, 0, 0)
        inspector_layout.setSpacing(8)

        inspector_title = QLabel("文献信息", self.inspector_panel)
        inspector_title.setObjectName("section_label")
        self.reference_key_input = QLineEdit(self.inspector_panel)
        self.reference_key_input.setPlaceholderText("citation key，例如 smith2023")
        self.pdf_state_label = QLabel("等待 PDF 打开", self.inspector_panel)
        self.pdf_state_label.setObjectName("inspector_label")
        self.pdf_state_label.setWordWrap(True)
        self.pdf_state_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        inspector_layout.addWidget(inspector_title)
        inspector_layout.addWidget(self.reference_key_input)
        inspector_layout.addWidget(self.pdf_state_label, 1)

        self.splitter.addWidget(self.thumbnail_list)
        self.splitter.addWidget(preview_panel)
        self.splitter.addWidget(self.inspector_panel)
        self._apply_outer_panel_visibility()
        root_layout.addWidget(self.splitter, 1)

    def _bind_signals(self) -> None:
        self.prev_button.clicked.connect(self.go_previous_page)
        self.next_button.clicked.connect(self.go_next_page)
        self.page_sidebar_button.toggled.connect(self._set_page_sidebar_visible)
        self.inspector_button.toggled.connect(self._set_inspector_visible)
        self.page_spin.valueChanged.connect(self.go_to_page)
        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self.fit_width_button.clicked.connect(self.fit_width)
        self.thumbnail_list.itemActivated.connect(self._open_thumbnail_page)
        self.thumbnail_list.itemClicked.connect(self._open_thumbnail_page)
        self.highlight_button.clicked.connect(self.request_highlight)
        self.excerpt_button.clicked.connect(self.request_excerpt_insert)
        self.citation_button.clicked.connect(self.request_citation_insert)
        self.open_external_button.clicked.connect(self._emit_external_open_requested)
        self.page_image_label.selection_completed.connect(self._handle_page_selection)

    def load_pdf(self, pdf_path: str | Path, *, page_count: int | None = None, reference_key: str = "") -> None:
        path = Path(pdf_path)
        self._close_pdf_document()
        self.pdf_item = PdfDocumentItem(
            title=path.name,
            path=path,
            page_count=page_count,
            reference_key=reference_key,
        )
        self.current_page = 1
        self.zoom_factor = 1.0
        self.reference_key_input.setText(reference_key)
        self.title_label.setText(path.name)
        self.path_label.setText(str(path))
        self._metadata_title = path.name
        self._metadata_relative_path = path.name
        self._metadata_file_size = path.stat().st_size if path.exists() else 0

        if fitz is None:
            self.page_count = max(1, int(page_count or 1))
            self._set_page_spin_range(self.page_count)
            self._sync_page_controls()
            self._populate_thumbnails()
            self._show_render_error(path, self._pymupdf_missing_message())
            return

        try:
            self.pdf_document = fitz.open(str(path))
        except Exception as error:
            self.page_count = max(1, int(page_count or 1))
            self._set_page_spin_range(self.page_count)
            self._sync_page_controls()
            self._populate_thumbnails()
            self._show_render_error(path, f"PDF 加载失败：{error}")
            return

        self.page_count = max(1, int(getattr(self.pdf_document, "page_count", 0) or page_count or 1))
        self._set_page_spin_range(self.page_count)
        self._sync_page_controls()
        self._populate_thumbnails()
        self._render_current_page()
        self._prepare_selection_box()
        self._update_pdf_state(self._build_document_info_text())

    def set_pdf_document_info(self, *, page_count: int | None = None, reference_key: str = "") -> None:
        if page_count is not None and self.pdf_document is None:
            self.page_count = max(1, int(page_count))
            self._set_page_spin_range(self.page_count)
            self._populate_thumbnails()
        if reference_key:
            self.reference_key_input.setText(reference_key)
        self._sync_page_controls()

    def show_pdf_metadata(self, pdf_data: dict[str, object]) -> None:
        title = str(pdf_data.get("title") or self.title_label.text())
        file_path = str(pdf_data.get("file_path") or "")
        relative_path = str(pdf_data.get("relative_path") or "")
        file_size = int(pdf_data.get("file_size") or 0)
        page_count = pdf_data.get("page_count")
        if page_count is not None and self.pdf_document is None:
            self.set_pdf_document_info(page_count=int(page_count))
        self.title_label.setText(title)
        if file_path:
            self.path_label.setText(file_path)
        self._metadata_title = title
        self._metadata_relative_path = relative_path
        self._metadata_file_size = file_size

        self._update_pdf_state(
            self._build_document_info_text(
                title=title,
                relative_path=relative_path,
                file_size=file_size,
                page_count=page_count,
            )
        )

    def show_rendered_page(self, page_number: int, description: str) -> None:
        self.current_page = max(1, min(page_number, self.page_count))
        self._sync_page_controls()
        self._render_current_page()
        self._prepare_selection_box()
        self._update_pdf_state(description)
        self.page_changed.emit(self.current_page)

    def go_previous_page(self) -> None:
        self.go_to_page(self.current_page - 1)

    def go_next_page(self) -> None:
        self.go_to_page(self.current_page + 1)

    def go_to_page(self, page_number: int) -> None:
        page = max(1, min(int(page_number), self.page_count))
        if page == self.current_page:
            self._render_current_page()
            return
        self.current_page = page
        self._sync_page_controls()
        self._render_current_page()
        self._prepare_selection_box()
        self.page_changed.emit(page)
        self._update_pdf_state(self._build_document_info_text())

    def zoom_in(self) -> None:
        self.zoom_factor = min(4.0, round(self.zoom_factor + 0.1, 2))
        self._render_current_page()
        self.zoom_changed.emit(self.zoom_factor)

    def zoom_out(self) -> None:
        self.zoom_factor = max(0.35, round(self.zoom_factor - 0.1, 2))
        self._render_current_page()
        self.zoom_changed.emit(self.zoom_factor)

    def fit_width(self) -> None:
        if self.pdf_document is None:
            self._update_pdf_state("请先打开一个 PDF。")
            return
        page = self.pdf_document.load_page(self.current_page - 1)
        page_width = max(float(page.rect.width), 1.0)
        available_width = max(self.scroll_area.viewport().width() - 28, 120)
        self.zoom_factor = max(0.35, min(4.0, round(available_width / page_width, 2)))
        self._render_current_page()
        self.zoom_changed.emit(self.zoom_factor)

    def request_highlight(self) -> None:
        if self.pdf_item is None:
            return
        text = self._selected_or_current_page_text()
        if not text:
            self._update_pdf_state("当前页没有可提取文字，无法创建批注。")
            return
        self.annotation_requested.emit(
            PdfAnnotationDraft(
                pdf_path=self.pdf_item.path,
                page_number=self.current_page,
                kind="highlight",
                text=text,
                citation_key=self.reference_key_input.text().strip(),
                rects=self._selected_rects,
            )
        )
        self._update_pdf_state("已提交当前页批注。")

    def request_excerpt_insert(self) -> None:
        text = self._selected_or_current_page_text()
        if not text:
            self._update_pdf_state("当前页没有可提取文字，无法摘录。")
            return
        key = self.reference_key_input.text().strip()
        citation = f" [@{key}, p. {self.current_page}]" if key else f" [p. {self.current_page}]"
        excerpt_lines = "\n".join(f"> {line}" if line else ">" for line in text.splitlines())
        self.excerpt_insert_requested.emit(
            f"{excerpt_lines}\n>\n> Source: {self.title_label.text()}{citation}\n\n"
        )
        self._update_pdf_state("已把当前页摘录发送到 Markdown 笔记。")

    def request_citation_insert(self) -> None:
        key = self.reference_key_input.text().strip()
        if not key and self.pdf_item is not None:
            key = self.pdf_item.path.stem
        token = f"[@{key}, p. {self.current_page}]" if key else f"[p. {self.current_page}]"
        self.citation_insert_requested.emit(token)
        self._update_pdf_state("已把引用标记发送到 Markdown 笔记。")

    def _set_page_sidebar_visible(self, visible: bool) -> None:
        self._page_sidebar_visible = bool(visible)
        self.thumbnail_list.setVisible(self._page_sidebar_visible)
        self.page_sidebar_button.blockSignals(True)
        self.page_sidebar_button.setChecked(self._page_sidebar_visible)
        self.page_sidebar_button.setText("隐藏页栏" if self._page_sidebar_visible else "页栏")
        self.page_sidebar_button.blockSignals(False)
        self._apply_outer_panel_visibility()

    def _set_inspector_visible(self, visible: bool) -> None:
        self._inspector_visible = bool(visible)
        self.inspector_panel.setVisible(self._inspector_visible)
        self.inspector_button.blockSignals(True)
        self.inspector_button.setChecked(self._inspector_visible)
        self.inspector_button.setText("隐藏信息" if self._inspector_visible else "信息")
        self.inspector_button.blockSignals(False)
        self._apply_outer_panel_visibility()

    def _apply_outer_panel_visibility(self) -> None:
        self.thumbnail_list.setVisible(self._page_sidebar_visible)
        self.inspector_panel.setVisible(self._inspector_visible)
        sidebar_width = 150 if self._page_sidebar_visible else 0
        inspector_width = 280 if self._inspector_visible else 0
        self.splitter.setSizes([sidebar_width, 920, inspector_width])

    def _build_document_info_text(
        self,
        *,
        title: str | None = None,
        relative_path: str = "",
        file_size: int = 0,
        page_count: object | None = None,
    ) -> str:
        item_title = title or (self.pdf_item.title if self.pdf_item is not None else self.title_label.text())
        if not title and self._metadata_title:
            item_title = self._metadata_title
        if not relative_path:
            relative_path = self._metadata_relative_path
        if not relative_path and self.pdf_item is not None:
            relative_path = self.pdf_item.path.name
        if not file_size:
            file_size = self._metadata_file_size
        effective_page_count = page_count if page_count is not None else self.page_count
        size_line = f"\n大小：{self._format_file_size(file_size)}" if file_size else ""
        return (
            "当前文献已就绪。\n\n"
            f"文件：{item_title}\n"
            f"位置：{relative_path or '当前工作区附件'}{size_line}\n"
            f"页数：{effective_page_count}\n"
            f"当前：第 {self.current_page} 页\n\n"
            "可用操作：\n"
            "1. 在页面上拖拽选择文字，选区会显示在下方编辑框。\n"
            "2. 编辑选区内容后，可摘录到当前笔记或保存为批注。\n"
            "3. 使用“插入引用”可把当前页引用标记写入笔记。"
        )

    def _populate_thumbnails(self) -> None:
        self.thumbnail_list.clear()
        for page_number in range(1, self.page_count + 1):
            item = QListWidgetItem(f"第 {page_number} 页")
            item.setData(Qt.ItemDataRole.UserRole, page_number)
            self.thumbnail_list.addItem(item)

    def _open_thumbnail_page(self, item: QListWidgetItem) -> None:
        page_number = item.data(Qt.ItemDataRole.UserRole)
        if page_number:
            self.go_to_page(int(page_number))

    def _render_current_page(self) -> None:
        if self.pdf_document is None:
            return
        try:
            page = self.pdf_document.load_page(self.current_page - 1)
            render_zoom = self.zoom_factor * self._render_quality_scale
            matrix = fitz.Matrix(render_zoom, render_zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            self._last_render_source_size = (pixmap.width, pixmap.height)
            image = QImage(
                pixmap.samples,
                pixmap.width,
                pixmap.height,
                pixmap.stride,
                QImage.Format.Format_RGB888,
            ).copy()
            page_pixmap = QPixmap.fromImage(image)
            display_width = max(1, round(float(page.rect.width) * self.zoom_factor))
            display_height = max(1, round(float(page.rect.height) * self.zoom_factor))
            display_size = QSize(display_width, display_height)
            self.page_image_label.set_rendered_page(page_pixmap, display_size)
            self._current_words = self._extract_current_page_words()
            self._selected_rects = ()
            self.page_image_label.clear_selection()
        except Exception as error:
            self._show_render_error(
                self.pdf_item.path if self.pdf_item is not None else Path("PDF"),
                f"PDF 页面渲染失败：{error}",
            )

    def _prepare_selection_box(self) -> None:
        if self.pdf_document is None:
            return
        self._last_extracted_page = self.current_page
        self.selection_box.clear()
        self.selection_box.setPlaceholderText("拖拽选择文字，摘录内容会显示在这里。")

    def _selected_or_current_page_text(self) -> str:
        return self.selection_box.toPlainText().strip()

    def _extract_current_page_words(self) -> list[tuple[float, float, float, float, str, int, int, int]]:
        if self.pdf_document is None:
            return []
        try:
            page = self.pdf_document.load_page(self.current_page - 1)
            return [
                (float(x0), float(y0), float(x1), float(y1), str(word), int(block), int(line), int(word_no))
                for x0, y0, x1, y1, word, block, line, word_no in page.get_text("words")
            ]
        except Exception:
            return []

    def _handle_page_selection(self, selection_rect: QRect) -> None:
        if not self._current_words:
            self.selection_box.clear()
            self._selected_rects = ()
            self.page_image_label.clear_selection()
            self._update_pdf_state("当前页没有可选择的文本。")
            return

        pdf_rect = self._label_rect_to_pdf_rect(selection_rect)
        selected_words = [
            word for word in self._current_words if self._word_intersects_rect(word, pdf_rect)
        ]
        selected_words.sort(key=lambda item: (item[5], item[6], item[7]))
        if not selected_words:
            self.selection_box.clear()
            self._selected_rects = ()
            self.page_image_label.clear_selection()
            self._update_pdf_state("未选中文字，请在文字区域拖拽。")
            return

        self.selection_box.setPlainText(self._words_to_text(selected_words))
        self._adjust_selection_editor_width(len(selected_words))
        self._selected_rects = tuple(
            {
                "x": word[0],
                "y": word[1],
                "width": word[2] - word[0],
                "height": word[3] - word[1],
            }
            for word in selected_words
        )
        self.page_image_label.set_selection_rects(self._pdf_words_to_label_line_rects(selected_words))
        self._update_pdf_state(f"已选择 {len(selected_words)} 个词，可编辑后摘录或批注。")

    def _adjust_selection_editor_width(self, word_count: int) -> None:
        if word_count >= 140:
            editor_width = 520
        elif word_count >= 70:
            editor_width = 460
        elif word_count >= 30:
            editor_width = 400
        else:
            editor_width = 340
        self.content_splitter.setSizes([max(520, self.width() - editor_width), editor_width])

    def _label_rect_to_pdf_rect(self, rect: QRect) -> tuple[float, float, float, float]:
        scale = max(self.zoom_factor, 0.01)
        return (
            rect.left() / scale,
            rect.top() / scale,
            rect.right() / scale,
            rect.bottom() / scale,
        )

    def _pdf_word_to_label_rect(
        self, word: tuple[float, float, float, float, str, int, int, int]
    ) -> QRect:
        return QRect(
            round(word[0] * self.zoom_factor),
            round(word[1] * self.zoom_factor),
            max(1, round((word[2] - word[0]) * self.zoom_factor)),
            max(1, round((word[3] - word[1]) * self.zoom_factor)),
        )

    def _pdf_words_to_label_line_rects(
        self, words: list[tuple[float, float, float, float, str, int, int, int]]
    ) -> list[QRect]:
        line_rects: dict[tuple[int, int], QRect] = {}
        for word in words:
            key = (word[5], word[6])
            word_rect = self._pdf_word_to_label_rect(word)
            if key in line_rects:
                line_rects[key] = line_rects[key].united(word_rect)
            else:
                line_rects[key] = QRect(word_rect)
        return [rect.adjusted(-2, -1, 2, 1) for rect in line_rects.values()]

    def _word_intersects_rect(
        self,
        word: tuple[float, float, float, float, str, int, int, int],
        rect: tuple[float, float, float, float],
    ) -> bool:
        x0, y0, x1, y1 = word[:4]
        rx0, ry0, rx1, ry1 = rect
        return not (x1 < rx0 or x0 > rx1 or y1 < ry0 or y0 > ry1)

    def _words_to_text(
        self, words: list[tuple[float, float, float, float, str, int, int, int]]
    ) -> str:
        lines: list[str] = []
        current_key: tuple[int, int] | None = None
        current_line: list[str] = []
        for word in words:
            key = (word[5], word[6])
            if current_key is not None and key != current_key:
                lines.append(" ".join(current_line))
                current_line = []
            current_key = key
            current_line.append(word[4])
        if current_line:
            lines.append(" ".join(current_line))
        return "\n".join(lines).strip()

    def _current_page_text(self) -> str:
        if self.pdf_document is None:
            return ""
        try:
            page = self.pdf_document.load_page(self.current_page - 1)
            return page.get_text("text").strip()
        except Exception:
            return ""

    def _show_render_error(self, pdf_path: Path, message: str) -> None:
        self.page_image_label.clear_rendered_page()
        self.page_image_label.setMinimumSize(320, 180)
        self.page_image_label.setText(f"{pdf_path.name}\n\n{message}")
        self._update_pdf_state(message)

    def _set_page_spin_range(self, page_count: int) -> None:
        self.page_count = max(1, int(page_count))
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(self.page_count)
        self.page_spin.setValue(min(self.current_page, self.page_spin.maximum()))
        self.page_spin.blockSignals(False)
        self.page_label.setText(f"/ {self.page_count}")

    def _sync_page_controls(self) -> None:
        self.page_label.setText(f"/ {self.page_count}")
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(self.current_page)
        self.page_spin.blockSignals(False)

    def _set_empty_state(self) -> None:
        self.page_image_label.setText("从左侧文献列表或右侧 PDF 面板打开一个 PDF。")
        self._sync_page_controls()
        self._update_pdf_state("尚未打开 PDF。")

    def _update_pdf_state(self, text: str) -> None:
        self.pdf_state_label.setText(text)

    def _emit_external_open_requested(self) -> None:
        if self.pdf_item is not None:
            self.external_open_requested.emit(self.pdf_item.path)

    def _close_pdf_document(self) -> None:
        if self.pdf_document is not None:
            try:
                self.pdf_document.close()
            except Exception:
                pass
        self.pdf_document = None

    def _pymupdf_missing_message(self) -> str:
        detail = f"\n\n底层错误：{PYMUPDF_IMPORT_ERROR}" if PYMUPDF_IMPORT_ERROR else ""
        return (
            "当前环境缺少 PyMuPDF，无法在应用内渲染 PDF。"
            "请按 environment.yml 更新环境，确保 pip 依赖 pymupdf 已安装。"
            f"{detail}"
        )

    def _format_file_size(self, size: int) -> str:
        if size <= 0:
            return "未知"
        units = ("B", "KB", "MB", "GB")
        value = float(size)
        unit_index = 0
        while value >= 1024 and unit_index < len(units) - 1:
            value /= 1024
            unit_index += 1
        return f"{value:.1f} {units[unit_index]}" if unit_index else f"{int(value)} {units[unit_index]}"

    def closeEvent(self, event) -> None:
        self._close_pdf_document()
        super().closeEvent(event)
