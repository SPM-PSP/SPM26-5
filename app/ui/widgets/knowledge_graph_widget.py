from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QEvent, QEasingCurve, QPointF, QRectF, Qt, QTimer, Signal, QVariantAnimation
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QTextOption
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QApplication,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.models.graph_layout_store import load_node_position, save_node_position
from app.ui.models.ui_items import KnowledgeGraphNode, KnowledgeObjectKind, KnowledgeSelection


SUN_COLOR = "#ffd28a"
PLANET_DEFAULT_COLOR = "#d6dde3"
PLANET_UNASSIGNED_COLOR = "#9aa8b3"
BACKLINK_COMMUNICATION_COLOR = "#6cb6ff"
CITATION_COMMUNICATION_COLOR = "#c792ea"

PLANET_COLORS = {
    "Inbox": PLANET_DEFAULT_COLOR,
    "收集箱": PLANET_DEFAULT_COLOR,
    "Reading": PLANET_DEFAULT_COLOR,
    "阅读资料": PLANET_DEFAULT_COLOR,
    "Research": PLANET_DEFAULT_COLOR,
    "研究主题": PLANET_DEFAULT_COLOR,
    "Unassigned": PLANET_UNASSIGNED_COLOR,
    "未归类": PLANET_UNASSIGNED_COLOR,
}


class KnowledgeConnectorLine(QGraphicsLineItem):
    def __init__(
        self,
        source: "KnowledgeCircleItem",
        target: "KnowledgeCircleItem",
        color: str,
        *,
        width: float = 1.4,
        dashed: bool = True,
    ) -> None:
        super().__init__()
        self.source = source
        self.target = target
        pen = QPen(QColor(color))
        pen.setWidthF(width)
        pen.setStyle(Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine)
        self.setPen(pen)
        self.setZValue(-2)
        self.setOpacity(0.0)
        self.source.add_connector(self)
        self.target.add_connector(self)
        self.update_position()

    def update_position(self) -> None:
        self.setLine(
            self.source.scenePos().x(),
            self.source.scenePos().y(),
            self.target.scenePos().x(),
            self.target.scenePos().y(),
        )


class KnowledgeCommunicationLine(QGraphicsPathItem):
    def __init__(
        self,
        source: "KnowledgeCircleItem",
        target: "KnowledgeCircleItem",
        color: str,
        *,
        curve_offset: float = 30.0,
    ) -> None:
        super().__init__()
        self.source = source
        self.target = target
        self.curve_offset = curve_offset
        self._dash_offset = 0.0

        pen = QPen(QColor(color))
        pen.setWidthF(1.85)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setDashPattern([6.0, 7.0])
        self.setPen(pen)
        self.setZValue(-3)
        self.setOpacity(0.72)
        self.source.add_connector(self)
        self.target.add_connector(self)
        self.update_position()

    def set_dash_offset(self, offset: float) -> None:
        self._dash_offset = offset
        pen = self.pen()
        pen.setDashOffset(offset)
        self.setPen(pen)

    def update_position(self) -> None:
        start_center = self.source.scenePos()
        end_center = self.target.scenePos()
        dx = end_center.x() - start_center.x()
        dy = end_center.y() - start_center.y()
        distance = math.hypot(dx, dy)
        if distance <= 0.01:
            return

        ux = dx / distance
        uy = dy / distance
        start = start_center
        end = end_center

        normal = QPointF(-uy, ux)
        mid = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
        control = QPointF(
            mid.x() + normal.x() * self.curve_offset,
            mid.y() + normal.y() * self.curve_offset,
        )

        path = QPainterPath(start)
        path.quadTo(control, end)
        self.setPath(path)


class KnowledgeCircleItem(QGraphicsEllipseItem):
    def __init__(
        self,
        node: KnowledgeGraphNode,
        radius: float,
        callback,
        context_callback=None,
        double_click_callback=None,
        move_callback=None,
        parent: QGraphicsEllipseItem | None = None,
    ) -> None:
        super().__init__(-radius, -radius, radius * 2, radius * 2, parent)
        self.node = node
        self.callback = callback
        self.context_callback = context_callback
        self.double_click_callback = double_click_callback
        self.move_callback = move_callback
        self.radius = radius
        self.system_index: int | None = None
        self._connectors: list[KnowledgeConnectorLine] = []
        self._press_scene_pos: QPointF | None = None
        self._press_button: Qt.MouseButton | None = None
        self.drag_mode = "free"
        self.orbit_center = QPointF(0, 0)
        self.orbit_radius = 0.0
        self.drag_followers: list[QGraphicsItem] = []
        self._last_scene_pos = QPointF(0, 0)
        self._moving_followers = False
        self._signal_colors: tuple[str, ...] = ()
        self._is_hovered = False
        self.setBrush(QBrush(QColor(node.color)))
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        self.label_item = QGraphicsTextItem(self)
        self.label_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.label_item.setDefaultTextColor(QColor("#d8e6f3"))
        self.label_item.setFont(self._label_font())
        self.label_item.setTextWidth(self._label_width())
        self.label_item.setPlainText(self._wrapped_title())
        self._position_label()

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        colors = self._paint_colors()
        if len(colors) >= 2:
            painter.setBrush(QBrush(colors[0]))
            painter.drawPie(self.rect(), 90 * 16, 180 * 16)
            painter.setBrush(QBrush(colors[1]))
            painter.drawPie(self.rect(), -90 * 16, 180 * 16)
            return

        painter.setBrush(QBrush(colors[0]))
        painter.drawEllipse(self.rect())

    def add_connector(self, connector: KnowledgeConnectorLine) -> None:
        self._connectors.append(connector)

    def set_signal_types(self, signal_types: set[str]) -> None:
        colors: list[str] = []
        if "backlink" in signal_types:
            colors.append(BACKLINK_COMMUNICATION_COLOR)
        if "citation" in signal_types:
            colors.append(CITATION_COMMUNICATION_COLOR)
        self._signal_colors = tuple(colors[:2])
        self.update()

    def _paint_colors(self) -> tuple[QColor, ...]:
        source_colors = self._signal_colors or (self.node.color,)
        colors = tuple(QColor(color) for color in source_colors)
        if self._is_hovered:
            return tuple(color.lighter(118) for color in colors)
        return colors

    def itemChange(self, change, value):
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and self.drag_mode == "orbit"
            and isinstance(value, QPointF)
            and self.orbit_radius > 0
        ):
            vector = value - self.orbit_center
            distance = math.hypot(vector.x(), vector.y())
            if distance <= 0.01:
                return self.pos()
            return QPointF(
                self.orbit_center.x() + vector.x() / distance * self.orbit_radius,
                self.orbit_center.y() + vector.y() / distance * self.orbit_radius,
            )

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self.drag_mode == "system" and not self._moving_followers:
                delta = self.scenePos() - self._last_scene_pos
                if abs(delta.x()) > 0.01 or abs(delta.y()) > 0.01:
                    self._moving_followers = True
                    for follower in self.drag_followers:
                        if follower is self:
                            continue
                        if isinstance(follower, (KnowledgeCircleItem, KnowledgeOrbitLabelItem)):
                            follower.orbit_center += delta
                        follower.setPos(follower.pos() + delta)
                    self._moving_followers = False
                self._last_scene_pos = self.scenePos()
            for connector in self._connectors:
                connector.update_position()
        return super().itemChange(change, value)

    def _label_font(self) -> QFont:
        font = QFont("Microsoft YaHei UI", 9 if self.radius < 24 else 10)
        font.setBold(self.radius >= 40)
        return font

    def _label_width(self) -> float:
        return max(76.0, min(154.0, self.radius * 3.6))

    def _wrapped_title(self) -> str:
        title = self.node.title.strip() or "未命名"
        limit = 8 if self.radius < 24 else 10
        max_lines = 3 if self.radius >= 30 else 2
        lines: list[str] = []
        current = ""
        current_width = 0

        for char in title:
            char_width = 2 if ord(char) > 127 else 1
            if current and current_width + char_width > limit:
                lines.append(current)
                current = char
                current_width = char_width
            else:
                current += char
                current_width += char_width

        if current:
            lines.append(current)

        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = QFontMetrics(self._label_font()).elidedText(
                lines[-1],
                Qt.TextElideMode.ElideRight,
                int(self._label_width()),
            )

        return "\n".join(lines)

    def _position_label(self) -> None:
        text_option = QTextOption()
        text_option.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
        self.label_item.document().setDefaultTextOption(text_option)
        self.label_item.setTextWidth(self._label_width())
        rect = self.label_item.boundingRect()
        self.label_item.setPos(-rect.width() / 2, self.radius + 6)

    def mousePressEvent(self, event) -> None:
        self._press_scene_pos = event.scenePos()
        self._press_button = event.button()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        moved = False
        if self._press_scene_pos is not None:
            moved = (event.scenePos() - self._press_scene_pos).manhattanLength() > 4
        super().mouseReleaseEvent(event)
        if not moved and self._press_button == Qt.MouseButton.LeftButton:
            self.callback(self.node, self)
        elif moved and self.move_callback is not None:
            self.move_callback(self.node, self)
        self._press_scene_pos = None
        self._press_button = None

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.double_click_callback is not None:
            self.double_click_callback(self.node, self)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:
        if self.context_callback is not None:
            self.context_callback(self.node, self, event)
            event.accept()
            return
        super().contextMenuEvent(event)

    def hoverEnterEvent(self, event) -> None:
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)


class KnowledgeOrbitLabelItem(QGraphicsTextItem):
    def __init__(
        self,
        node: KnowledgeGraphNode,
        callback,
        context_callback=None,
        move_callback=None,
    ) -> None:
        super().__init__()
        self.node = node
        self.callback = callback
        self.context_callback = context_callback
        self.move_callback = move_callback
        self.system_index: int | None = None
        self.drag_mode = "orbit"
        self.orbit_center = QPointF(0, 0)
        self.orbit_radius = 0.0
        self._press_scene_pos: QPointF | None = None
        self._press_button: Qt.MouseButton | None = None
        self.setPlainText(node.title)
        self.setDefaultTextColor(QColor("#dbe9ff"))
        font = QFont("Microsoft YaHei UI", 10)
        font.setBold(True)
        self.setFont(font)
        self.setTextWidth(132)
        text_option = QTextOption()
        text_option.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
        self.document().setDefaultTextOption(text_option)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    def center_pos(self) -> QPointF:
        rect = self.boundingRect()
        return self.pos() + QPointF(rect.width() / 2, rect.height() / 2)

    def set_center_pos(self, position: QPointF) -> None:
        rect = self.boundingRect()
        self.setPos(position - QPointF(rect.width() / 2, rect.height() / 2))

    def itemChange(self, change, value):
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and self.drag_mode == "orbit"
            and isinstance(value, QPointF)
            and self.orbit_radius > 0
        ):
            rect = self.boundingRect()
            proposed_center = value + QPointF(rect.width() / 2, rect.height() / 2)
            vector = proposed_center - self.orbit_center
            distance = math.hypot(vector.x(), vector.y())
            if distance <= 0.01:
                return self.pos()
            constrained_center = QPointF(
                self.orbit_center.x() + vector.x() / distance * self.orbit_radius,
                self.orbit_center.y() + vector.y() / distance * self.orbit_radius,
            )
            return constrained_center - QPointF(rect.width() / 2, rect.height() / 2)
        return super().itemChange(change, value)

    def mousePressEvent(self, event) -> None:
        self._press_scene_pos = event.scenePos()
        self._press_button = event.button()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        moved = False
        if self._press_scene_pos is not None:
            moved = (event.scenePos() - self._press_scene_pos).manhattanLength() > 4
        super().mouseReleaseEvent(event)
        if not moved and self._press_button == Qt.MouseButton.LeftButton:
            self.callback(self.node, self)
        elif moved and self.move_callback is not None:
            self.move_callback(self.node, self)
        self._press_scene_pos = None
        self._press_button = None

    def contextMenuEvent(self, event) -> None:
        if self.context_callback is not None:
            self.context_callback(self.node, self, event)
            event.accept()
            return
        super().contextMenuEvent(event)

    def hoverEnterEvent(self, event) -> None:
        self.setDefaultTextColor(QColor("#ffffff"))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.setDefaultTextColor(QColor("#dbe9ff"))
        super().hoverLeaveEvent(event)


class KnowledgeGraphWidget(QWidget):
    node_selected = Signal(object)
    add_planet_requested = Signal(object)
    delete_planet_requested = Signal(object)
    add_star_requested = Signal(object)
    delete_star_requested = Signal(object)
    assign_to_planet_requested = Signal(object, str)

    def __init__(self, parent: QWidget | None = None, *, cover_mode: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("knowledge_graph_widget")
        self._cover_mode = cover_mode
        self.galaxy: KnowledgeGraphNode | None = None
        self.planets: list[KnowledgeGraphNode] = []
        self.stars_by_planet: dict[str, list[KnowledgeGraphNode]] = {}
        self._galaxy_systems: list[
            tuple[KnowledgeGraphNode, list[KnowledgeGraphNode], dict[str, list[KnowledgeGraphNode]]]
        ] = []
        self._active_system_index = 0
        self.current_layer = "galaxy"
        self.current_planet = ""
        self._animations: list[QVariantAnimation] = []
        self._pending_entrance: list[tuple[object, QPointF]] = []
        self._pending_fade: list[object] = []
        self._is_transitioning = False
        self._cover_zoom = 1.0
        self._cover_zoom_min = 0.42
        self._cover_zoom_max = 2.35
        self._cover_star_return_layer = "cover_system"
        self._current_star_detail_key = ""

        self._build_ui()
        self._render_empty_state()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        self.back_button = QPushButton("返回", self)
        self.back_button.setFixedWidth(58)
        self.back_button.clicked.connect(self.go_back)
        self.layer_label = QLabel("星系", self)
        self.layer_label.setObjectName("section_label")
        header_layout.addWidget(self.back_button)
        header_layout.addWidget(self.layer_label, 1)
        root_layout.addLayout(header_layout)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setObjectName("knowledge_graph_view")
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.viewport().installEventFilter(self)
        root_layout.addWidget(self.view, 1)

    def set_graph(
        self,
        *,
        galaxy: KnowledgeGraphNode,
        planets: Iterable[KnowledgeGraphNode],
        stars_by_planet: dict[str, list[KnowledgeGraphNode]],
    ) -> None:
        self.galaxy = galaxy
        self.planets = list(planets)
        self.stars_by_planet = stars_by_planet
        self._galaxy_systems = [(self.galaxy, list(self.planets), dict(self.stars_by_planet))]
        self._active_system_index = 0
        self.current_layer = "cover_overview" if self._cover_mode else "galaxy"
        self.current_planet = ""
        if self._cover_mode:
            self.render_cover_overview()
            self.render_galaxy()

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is self.view.viewport()
            and self._cover_mode
            and event.type() == QEvent.Type.Wheel
            and QApplication.mouseButtons() & Qt.MouseButton.LeftButton
        ):
            delta = event.angleDelta().y()
            if delta:
                self._zoom_cover_graph(1.12 if delta > 0 else 1 / 1.12)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _zoom_cover_graph(self, factor: float) -> None:
        next_zoom = max(self._cover_zoom_min, min(self._cover_zoom_max, self._cover_zoom * factor))
        factor = next_zoom / self._cover_zoom
        if abs(factor - 1.0) < 0.001:
            return
        self.view.scale(factor, factor)
        self._cover_zoom = next_zoom

    def set_cover_graphs(
        self,
        systems: Iterable[
            tuple[KnowledgeGraphNode, Iterable[KnowledgeGraphNode], dict[str, list[KnowledgeGraphNode]]]
        ],
    ) -> None:
        self._galaxy_systems = [
            (galaxy, list(planets), dict(stars_by_planet))
            for galaxy, planets, stars_by_planet in systems
        ]
        if self._galaxy_systems:
            self.galaxy, self.planets, self.stars_by_planet = self._galaxy_systems[0]
        else:
            self.galaxy = None
            self.planets = []
            self.stars_by_planet = {}
        self._active_system_index = 0
        if self._cover_mode:
            self.render_cover_overview()
        elif self.galaxy is not None:
            self.render_galaxy()
        else:
            self._render_empty_state()

    def render_galaxy(self) -> None:
        self._stop_animations()
        self.current_layer = "galaxy"
        self.current_planet = ""
        self.layer_label.setText("星系")
        self.back_button.setEnabled(False)
        self._clear_scene_for_render()
        if self.galaxy is None:
            self._render_empty_state()
            return
        self._set_scene_rect()
        self._add_circle(self.galaxy, QPointF(0, 0), 62)
        self._animate_items_in()
        self._fit_scene()

    def render_cover_overview(self) -> None:
        self._stop_animations()
        self.current_layer = "cover_overview"
        self.current_planet = ""
        self.layer_label.setText("星系总览")
        self.back_button.setEnabled(False)
        self._clear_scene_for_render()
        if not self._galaxy_systems:
            self._render_empty_state()
            return

        self._set_scene_rect()
        centers = self._cover_system_centers(len(self._galaxy_systems))
        for system_index, (galaxy, planets, stars_by_planet) in enumerate(self._galaxy_systems):
            self._render_orbit_system(
                system_index,
                galaxy,
                planets,
                stars_by_planet,
                centers[system_index],
                compact=True,
            )

        self._animate_items_in()
        self._fit_scene()

    def render_cover_system(self, system_index: int) -> None:
        if not 0 <= system_index < len(self._galaxy_systems):
            return
        self._stop_animations()
        self._active_system_index = system_index
        galaxy, planets, stars_by_planet = self._galaxy_systems[system_index]
        self.galaxy = galaxy
        self.planets = list(planets)
        self.stars_by_planet = dict(stars_by_planet)
        self.current_layer = "cover_system"
        self.current_planet = ""
        self.layer_label.setText(f"{galaxy.title} 星系")
        self.back_button.setEnabled(True)
        self._clear_scene_for_render()
        self._set_scene_rect()

        self._render_orbit_system(
            system_index,
            galaxy,
            planets,
            stars_by_planet,
            QPointF(0, 0),
            compact=False,
        )

        self._animate_items_in()
        self._fit_scene()

    def render_cover_star_detail(self, star: KnowledgeGraphNode, system_index: int | None = None) -> None:
        if system_index is not None:
            self._active_system_index = system_index
        self._stop_animations()
        self.current_layer = "cover_star_detail"
        self.current_planet = star.planet
        self.layer_label.setText(f"{star.title} -> 卫星")
        self.back_button.setEnabled(True)
        self._clear_scene_for_render()
        self._set_scene_rect()

        self._render_star_satellite_system(
            star,
            center_radius=42,
            system_index=self._active_system_index,
        )
        self._animate_items_in()
        self._fit_scene()
        return

    def _render_orbit_system(
        self,
        system_index: int,
        galaxy: KnowledgeGraphNode,
        planets: list[KnowledgeGraphNode],
        stars_by_planet: dict[str, list[KnowledgeGraphNode]],
        center: QPointF,
        *,
        compact: bool,
    ) -> None:
        sun_radius = 28 if compact else 38
        orbit_gap = 46 if compact else 58
        first_orbit = 74 if compact else 96
        star_radius = 7 if compact else 10
        system_items: list[QGraphicsItem] = []
        star_items: list[tuple[KnowledgeGraphNode, KnowledgeCircleItem]] = []
        center = self._saved_or_default_position(system_index, "orbit", galaxy, center)

        sun = self._add_circle(
            galaxy,
            center,
            sun_radius,
            system_index=system_index,
            drag_mode="system",
        )
        sun._last_scene_pos = center
        system_items.append(sun)

        for planet_index, planet in enumerate(planets):
            orbit_radius = first_orbit + planet_index * orbit_gap
            orbit = self._add_orbit(center, orbit_radius)
            system_items.append(orbit)
            orbit_nodes = list(stars_by_planet.get(planet.title, []))
            orbit_nodes = self._deduplicate_orbit_nodes(orbit_nodes)
            orbit_slots = max(2, len(orbit_nodes) + 1)

            marker_node = self._planet_marker_node(planet)
            marker_angle = self._orbit_angle(
                galaxy.title,
                planet.title,
                marker_node.title,
                0,
                orbit_slots,
            )
            marker_position = QPointF(
                center.x() + math.cos(marker_angle) * orbit_radius,
                center.y() + math.sin(marker_angle) * orbit_radius,
            )
            marker_position = self._saved_or_default_position(
                system_index,
                "orbit",
                marker_node,
                marker_position,
            )
            marker_drag_radius = math.hypot(marker_position.x() - center.x(), marker_position.y() - center.y())
            if marker_drag_radius <= 0.01:
                marker_drag_radius = orbit_radius
            marker_item = self._add_orbit_label(
                marker_node,
                marker_position,
                system_index=system_index,
                orbit_center=center,
                orbit_radius=marker_drag_radius,
            )
            system_items.append(marker_item)

            for node_index, node in enumerate(orbit_nodes):
                angle = self._orbit_angle(
                    galaxy.title,
                    planet.title,
                    node.title,
                    node_index + 1,
                    orbit_slots,
                )
                position = QPointF(
                    center.x() + math.cos(angle) * orbit_radius,
                    center.y() + math.sin(angle) * orbit_radius,
                )
                position = self._saved_or_default_position(system_index, "orbit", node, position)
                node_drag_radius = math.hypot(position.x() - center.x(), position.y() - center.y())
                if node_drag_radius <= 0.01:
                    node_drag_radius = orbit_radius
                item = self._add_circle(
                    node,
                    position,
                    star_radius,
                    system_index=system_index,
                    drag_mode="orbit",
                    orbit_center=center,
                    orbit_radius=node_drag_radius,
                )
                system_items.append(item)
                if node.kind in (KnowledgeObjectKind.STAR_NOTE, KnowledgeObjectKind.STAR_REFERENCE):
                    star_items.append((node, item))

        sun.drag_followers = system_items
        self._add_backlink_communication_lines(star_items)

    def _planet_marker_node(self, planet: KnowledgeGraphNode) -> KnowledgeGraphNode:
        return KnowledgeGraphNode(
            kind=KnowledgeObjectKind.PLANET,
            title=planet.title,
            color=planet.color,
            path=planet.path,
            description=planet.description or "行星类别",
            planet=planet.title,
            tags=planet.tags,
        )

    def _deduplicate_orbit_nodes(
        self,
        nodes: list[KnowledgeGraphNode],
    ) -> list[KnowledgeGraphNode]:
        seen: set[tuple[str, str]] = set()
        result: list[KnowledgeGraphNode] = []
        for node in nodes:
            key = (node.kind.value, node.title)
            if key in seen:
                continue
            seen.add(key)
            result.append(node)
        return result

    def _orbit_angle(
        self,
        galaxy_title: str,
        planet_title: str,
        node_title: str,
        index: int,
        count: int,
    ) -> float:
        if count <= 1:
            base = 0.0
        else:
            base = 2 * math.pi * index / count
        offset = self._stable_unit(f"orbit:{galaxy_title}:{planet_title}:offset") * math.pi
        jitter = (self._stable_unit(f"orbit:{galaxy_title}:{planet_title}:{node_title}") - 0.5) * 0.24
        return base + offset + jitter

    def _add_backlink_communication_lines(
        self,
        star_items: list[tuple[KnowledgeGraphNode, KnowledgeCircleItem]],
    ) -> None:
        if len(star_items) < 2:
            return

        title_index: dict[str, list[int]] = {}
        for index, (node, _item) in enumerate(star_items):
            for key in self._node_link_keys(node):
                title_index.setdefault(key, []).append(index)

        directed_links: set[tuple[int, int, str]] = set()
        signal_types_by_index: defaultdict[int, set[str]] = defaultdict(set)
        for source_index, (source_node, _source_item) in enumerate(star_items):
            for link_title, link_type in self._outgoing_note_links(source_node):
                for target_index in title_index.get(link_title, ()):
                    if source_index == target_index:
                        continue
                    directed_links.add((target_index, source_index, link_type))
                    signal_types_by_index[target_index].add(link_type)
                    signal_types_by_index[source_index].add(link_type)

        for index, _node_item in enumerate(star_items):
            signal_types = signal_types_by_index.get(index)
            if signal_types:
                star_items[index][1].set_signal_types(signal_types)

        unordered_counts = Counter(tuple(sorted((source, target))) for source, target, _link_type in directed_links)
        unordered_seen: defaultdict[tuple[int, int], int] = defaultdict(int)
        for source_index, target_index, link_type in sorted(directed_links):
            pair_key = tuple(sorted((source_index, target_index)))
            ordinal = unordered_seen[pair_key]
            unordered_seen[pair_key] += 1
            pair_count = unordered_counts[pair_key]
            side = -1.0 if ordinal % 2 else 1.0
            if source_index > target_index:
                side *= -1.0
            magnitude = 28.0 + (ordinal // 2) * 14.0
            if pair_count == 1:
                magnitude = 24.0
            line = KnowledgeCommunicationLine(
                star_items[source_index][1],
                star_items[target_index][1],
                self._communication_color(link_type),
                curve_offset=side * magnitude,
            )
            self.scene.addItem(line)
            self._animate_communication_line(line)

    def _node_link_keys(self, node: KnowledgeGraphNode) -> set[str]:
        keys = set(self._link_key_variants(node.title))
        if node.path is not None:
            keys.update(self._link_key_variants(node.path.stem))
            keys.update(self._link_key_variants(node.path.name))
        return {key for key in keys if key}

    def _outgoing_note_links(self, node: KnowledgeGraphNode) -> set[tuple[str, str]]:
        if node.path is None or node.path.suffix.lower() != ".md":
            return set()
        try:
            text = node.path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return set()

        links: set[tuple[str, str]] = set()
        for match in re.finditer(r"\[\[([^\]|#]+)", text):
            title = match.group(1).strip()
            if title.endswith(".md"):
                title = title[:-3]
            if title:
                links.update((key, "backlink") for key in self._link_key_variants(title))

        for citation_group in re.finditer(r"\[([^\]]*@[^\]]+)\]", text):
            for token in re.finditer(r"@([^\s,;\]]+)", citation_group.group(1)):
                citation_key = token.group(1).strip()
                if citation_key:
                    links.update((key, "citation") for key in self._link_key_variants(citation_key))
        return links

    def _communication_color(self, link_type: str) -> str:
        if link_type == "citation":
            return CITATION_COMMUNICATION_COLOR
        return BACKLINK_COMMUNICATION_COLOR

    def _link_key_variants(self, value: str) -> set[str]:
        text = value.strip()
        if not text:
            return set()
        variants = {text}
        for suffix in (".md", ".pdf"):
            if text.lower().endswith(suffix):
                variants.add(text[: -len(suffix)])
        expanded = set(variants)
        for item in variants:
            expanded.add(item.replace(" ", "_"))
            expanded.add(item.replace("_", " "))
        return {item.strip() for item in expanded if item.strip()}

    def render_planets(self) -> None:
        self._stop_animations()
        self.current_layer = "planets"
        self.current_planet = ""
        self.layer_label.setText("行星")
        self.back_button.setEnabled(True)
        self._clear_scene_for_render()
        self._set_scene_rect()
        positions = self._radial_positions(len(self.planets), 118)
        for planet, position in zip(self.planets, positions, strict=False):
            self._add_circle(planet, position, 42)
        self._animate_items_in()
        self._fit_scene()

    def render_planet_detail(self, planet_title: str) -> None:
        self._stop_animations()
        self.current_layer = "planet_detail"
        self.current_planet = planet_title
        self.layer_label.setText(f"{planet_title} -> 星球")
        self.back_button.setEnabled(True)
        self._clear_scene_for_render()
        self._set_scene_rect()
        stars = self.stars_by_planet.get(planet_title, [])
        if not stars:
            self._add_center_text("暂无星球")
            self._animate_items_in()
            self._fit_scene()
            return

        positions = self._grid_positions(len(stars), 92)
        for star, position in zip(stars, positions, strict=False):
            self._add_star_with_satellites(star, position)
        self._animate_items_in()
        self._fit_scene()

    def render_star_detail(self, star: KnowledgeGraphNode) -> None:
        self._stop_animations()
        self.current_layer = "star_detail"
        self.current_planet = star.planet
        self.layer_label.setText(f"{star.title} -> 卫星")
        self.back_button.setEnabled(True)
        self._clear_scene_for_render()
        self._set_scene_rect()

        self._render_star_satellite_system(star, center_radius=38)
        self._animate_items_in()
        self._fit_scene()
        return
    def go_back(self) -> None:
        if self._is_transitioning:
            return
        if self._cover_mode:
            if self.current_layer == "cover_star_detail":
                if self._cover_star_return_layer == "cover_overview":
                    self._transition_to(self.render_cover_overview)
                else:
                    self._transition_to(lambda: self.render_cover_system(self._active_system_index))
                return
            if self.current_layer == "cover_system":
                self._transition_to(self.render_cover_overview)
            return
        if self.current_layer == "star_detail":
            if self.current_planet:
                self._transition_to(lambda: self.render_planet_detail(self.current_planet))
            else:
                self._transition_to(self.render_planets)
        elif self.current_layer == "planet_detail":
            self._transition_to(self.render_planets)
        elif self.current_layer == "planets":
            self._transition_to(self.render_galaxy)

    def _on_node_clicked(self, node: KnowledgeGraphNode, item: KnowledgeCircleItem) -> None:
        if self._is_transitioning:
            return
        if self._cover_mode:
            self._on_cover_node_clicked(node, item)
            return
        if node.kind == KnowledgeObjectKind.GALAXY:
            self._pulse_item(item, lambda: self._transition_to(self.render_planets))
            return
        if node.kind == KnowledgeObjectKind.PLANET:
            self._pulse_item(item, lambda: self._transition_to(lambda: self.render_planet_detail(node.title)))
            return
        if node.kind in (KnowledgeObjectKind.STAR_NOTE, KnowledgeObjectKind.STAR_REFERENCE):
            if self.current_layer == "star_detail":
                return
            self._pulse_item(item, lambda: self._transition_to(lambda: self.render_star_detail(node)))
            return
        if node.kind == KnowledgeObjectKind.SATELLITE:
            self._pulse_item(item, lambda: self.node_selected.emit(self._selection_from_node(node)))
            return
        self._pulse_item(item, lambda: self.node_selected.emit(self._selection_from_node(node)))

    def _on_cover_node_clicked(self, node: KnowledgeGraphNode, item: KnowledgeCircleItem) -> None:
        if node.kind == KnowledgeObjectKind.GALAXY:
            system_index = item.system_index if item.system_index is not None else self._active_system_index
            self._pulse_item(item, lambda: self._transition_to(lambda: self.render_cover_system(system_index)))
            return
        if node.kind in (KnowledgeObjectKind.STAR_NOTE, KnowledgeObjectKind.STAR_REFERENCE):
            if self.current_layer == "cover_star_detail":
                return
            if self.current_layer in ("cover_system", "cover_overview"):
                system_index = item.system_index if item.system_index is not None else self._active_system_index
                self._cover_star_return_layer = self.current_layer
                self._pulse_item(item, lambda: self._transition_to(lambda: self.render_cover_star_detail(node, system_index)))
                return
        if node.kind == KnowledgeObjectKind.SATELLITE:
            self._pulse_item(item, lambda: self.node_selected.emit(self._selection_from_node(node)))

    def _on_node_double_clicked(self, node: KnowledgeGraphNode, item: KnowledgeCircleItem) -> None:
        if self._is_transitioning:
            return
        if node.kind not in (KnowledgeObjectKind.STAR_NOTE, KnowledgeObjectKind.STAR_REFERENCE):
            return
        if self.current_layer not in ("star_detail", "cover_star_detail"):
            return
        self._pulse_item(item, lambda: self.node_selected.emit(self._selection_from_node(node)))

    def _on_node_moved(self, node: KnowledgeGraphNode, item) -> None:
        self._save_item_position(node, item)
        followers = getattr(item, "drag_followers", ())
        for follower in followers:
            if follower is item or not isinstance(follower, (KnowledgeCircleItem, KnowledgeOrbitLabelItem)):
                continue
            self._save_item_position(follower.node, follower)

    def _on_node_context_requested(self, node: KnowledgeGraphNode, item: KnowledgeCircleItem, event) -> None:
        if not self._cover_mode:
            return

        system_index = item.system_index if item.system_index is not None else self._active_system_index
        payload = {
            "node": node,
            "system_index": system_index,
            "planet": node.planet or node.title,
        }
        menu = self._make_graph_menu()

        if node.kind == KnowledgeObjectKind.GALAXY:
            add_planet_action = QAction("新增行星", menu)
            delete_planet_action = QAction("删除行星", menu)
            menu.addAction(add_planet_action)
            menu.addAction(delete_planet_action)
            add_planet_action.triggered.connect(lambda: self.add_planet_requested.emit(payload))
            delete_planet_action.triggered.connect(lambda: self.delete_planet_requested.emit(payload))
        elif node.kind == KnowledgeObjectKind.PLANET:
            add_star_action = QAction("新增星球", menu)
            delete_star_action = QAction("删除星球", menu)
            menu.addAction(add_star_action)
            menu.addAction(delete_star_action)
            add_star_action.triggered.connect(lambda: self.add_star_requested.emit(payload))
            delete_star_action.triggered.connect(lambda: self.delete_star_requested.emit(payload))
        elif node.kind == KnowledgeObjectKind.STAR_NOTE:
            open_action = QAction("打开 / 查看", menu)
            copy_path_action = QAction("复制路径", menu)
            assign_menu = self._build_assignment_menu(menu, payload)
            menu.addAction(open_action)
            if node.path is not None:
                menu.addAction(copy_path_action)
            menu.addMenu(assign_menu)
            menu.addSeparator()
            open_action.triggered.connect(lambda: self.node_selected.emit(self._selection_from_node(node)))
            if node.path is not None:
                copy_path_action.triggered.connect(lambda: QApplication.clipboard().setText(str(node.path)))
            delete_star_action = QAction("删除星球", menu)
            menu.addAction(delete_star_action)
            delete_star_action.triggered.connect(lambda: self.delete_star_requested.emit(payload))
        elif node.kind == KnowledgeObjectKind.STAR_REFERENCE:
            open_action = QAction("打开 / 查看", menu)
            copy_path_action = QAction("复制路径", menu)
            assign_menu = self._build_assignment_menu(menu, payload)
            menu.addAction(open_action)
            if node.path is not None:
                menu.addAction(copy_path_action)
            menu.addMenu(assign_menu)
            open_action.triggered.connect(lambda: self.node_selected.emit(self._selection_from_node(node)))
            if node.path is not None:
                copy_path_action.triggered.connect(lambda: QApplication.clipboard().setText(str(node.path)))
        else:
            return

        menu.exec(event.screenPos())

    def _make_graph_menu(self, title: str = "", parent: QWidget | None = None) -> QMenu:
        menu = QMenu(title, parent or self) if title else QMenu(parent or self)
        return self._style_graph_menu(menu)

    def _style_graph_menu(self, menu: QMenu) -> QMenu:
        menu.setObjectName("star_map_context_menu")
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        menu_scale = max(0.66, min(1.08, self._cover_zoom if self._cover_mode else 1.0))
        font_size = max(8, round(9 * menu_scale))
        radius = max(7, round(10 * menu_scale))
        outer_padding = max(4, round(5 * menu_scale))
        item_v_padding = max(4, round(5 * menu_scale))
        item_h_padding = max(11, round(14 * menu_scale))
        min_width = max(86, round(102 * menu_scale))
        separator_margin_h = max(6, round(8 * menu_scale))
        font = QFont("Microsoft YaHei UI", font_size)
        menu.setFont(font)
        menu.setStyleSheet(
            """
            QMenu#star_map_context_menu {{
                background-color: rgba(7, 19, 34, 238);
                border: 1px solid rgba(126, 190, 255, 118);
                border-radius: {radius}px;
                padding: {outer_padding}px;
                color: #e4f3ff;
            }}
            QMenu#star_map_context_menu::item {{
                min-width: {min_width}px;
                padding: {item_v_padding}px {item_h_padding}px;
                margin: 2px 0;
                border-radius: {item_radius}px;
                background: transparent;
            }}
            QMenu#star_map_context_menu::item:selected {{
                background-color: rgba(67, 184, 255, 46);
                color: #ffffff;
            }}
            QMenu#star_map_context_menu::separator {{
                height: 1px;
                margin: {separator_margin_v}px {separator_margin_h}px;
                background-color: rgba(151, 177, 201, 62);
            }}
            QMenu#star_map_context_menu::right-arrow {{
                width: {arrow_size}px;
                height: {arrow_size}px;
            }}
            """.format(
                radius=radius,
                outer_padding=outer_padding,
                min_width=min_width,
                item_v_padding=item_v_padding,
                item_h_padding=item_h_padding,
                item_radius=max(5, radius - 3),
                separator_margin_v=max(4, round(5 * menu_scale)),
                separator_margin_h=separator_margin_h,
                arrow_size=max(6, round(7 * menu_scale)),
            )
        )
        return menu

    def _build_assignment_menu(self, parent: QMenu, payload: dict[str, object]) -> QMenu:
        assign_menu = self._make_graph_menu("归入行星", parent)
        for planet in self._assignment_planets():
            action = QAction(planet.title, assign_menu)
            assign_menu.addAction(action)
            action.triggered.connect(
                lambda _checked=False, target=planet.title: self.assign_to_planet_requested.emit(
                    payload,
                    target,
                )
            )
        return assign_menu

    def _assignment_planets(self) -> list[KnowledgeGraphNode]:
        if self.current_layer == "cover_system":
            return list(self.planets)
        if 0 <= self._active_system_index < len(self._galaxy_systems):
            return list(self._galaxy_systems[self._active_system_index][1])
        return list(self.planets)

    def _selection_from_node(self, node: KnowledgeGraphNode) -> KnowledgeSelection:
        return KnowledgeSelection(
            kind=node.kind,
            title=node.title,
            path=node.path,
            description=node.description,
            tags=node.tags,
            satellites=node.satellites,
        )

    def _saved_or_default_position(
        self,
        system_index: int | None,
        scope: str,
        node: KnowledgeGraphNode,
        default: QPointF,
    ) -> QPointF:
        root = self._workspace_root_for_system(system_index)
        saved = load_node_position(root, self._layout_view_key(scope), self._node_layout_key(node))
        if saved is None:
            return default
        return QPointF(saved[0], saved[1])

    def _save_item_position(self, node: KnowledgeGraphNode, item) -> None:
        system_index = getattr(item, "system_index", None)
        root = self._workspace_root_for_system(system_index)
        if root is None:
            return
        scope = "star-detail" if self.current_layer in {"star_detail", "cover_star_detail"} else "orbit"
        if isinstance(item, KnowledgeOrbitLabelItem):
            position = item.center_pos()
        else:
            position = item.scenePos()
        save_node_position(
            root,
            self._layout_view_key(scope),
            self._node_layout_key(node),
            position.x(),
            position.y(),
        )

    def _workspace_root_for_system(self, system_index: int | None) -> Path | None:
        index = self._active_system_index if system_index is None else system_index
        if 0 <= index < len(self._galaxy_systems):
            root = self._galaxy_systems[index][0].path
            if root is not None and root.is_dir():
                return root
        if self.galaxy is not None and self.galaxy.path is not None and self.galaxy.path.is_dir():
            return self.galaxy.path
        return None

    def _layout_view_key(self, scope: str) -> str:
        if scope == "star-detail":
            return f"star-detail:{self._current_star_detail_key}"
        return "orbit"

    def _node_layout_key(self, node: KnowledgeGraphNode) -> str:
        path_key = str(node.path.resolve()) if node.path is not None else ""
        satellite_key = ""
        if node.satellites:
            satellite = node.satellites[0]
            satellite_key = (
                f":{getattr(satellite, 'kind', '')}"
                f":{getattr(satellite, 'line_number', '')}"
                f":{getattr(satellite, 'title', '')}"
            )
        return f"{node.kind.value}:{node.planet}:{path_key}:{node.title}{satellite_key}"

    def _render_star_satellite_system(
        self,
        star: KnowledgeGraphNode,
        *,
        center_radius: float,
        system_index: int | None = None,
    ) -> None:
        self._current_star_detail_key = self._node_layout_key(star)
        center = self._saved_or_default_position(system_index, "star-detail", star, QPointF(0, 0))
        system_items: list[QGraphicsItem] = []
        star_item = self._add_circle(
            star,
            center,
            center_radius,
            system_index=system_index,
            drag_mode="system",
        )
        star_item._last_scene_pos = center
        system_items.append(star_item)
        satellites = list(star.satellites[:18])
        if not satellites:
            self._add_text_at("暂无卫星", QPointF(0, center_radius + 92))
            star_item.drag_followers = system_items
            return

        layer_base_radii = [center_radius + 94, center_radius + 184, center_radius + 268]
        layers = self._satellite_layers(satellites)
        layer_bands = {
            index: self._satellite_layer_bands(layer, layer_base_radii[index])
            for index, layer in enumerate(layers)
            if layer
        }
        for layer_index, bands in layer_bands.items():
            for band_index, (_band, band_radius) in enumerate(bands):
                orbit = self._add_orbit(center, band_radius)
                orbit.setOpacity(0.12 + layer_index * 0.035)
                system_items.append(orbit)
                if band_index == 0:
                    label = self._satellite_layer_label(layer_index)
                    caption_pos = center + QPointF(-band_radius * 0.82, -band_radius * 0.56)
                    caption = self._add_text_at(label, caption_pos, font_size=9, color="#7f9bb2")
                    system_items.append(caption)

        for layer_index, bands in layer_bands.items():
            for band_index, (band, radius) in enumerate(bands):
                phase = (layer_index + 1) * math.pi / 7 + band_index * math.pi / 9
                for index, satellite in enumerate(band):
                    satellite_node = self._satellite_node(star, satellite)
                    relative_position, default_orbit_radius = self._satellite_default_position(
                        star,
                        satellite,
                        layer_index,
                        band_index,
                        index,
                        len(band),
                        radius,
                        phase,
                    )
                    default_position = center + relative_position
                    position = self._saved_or_default_position(
                        system_index,
                        "star-detail",
                        satellite_node,
                        default_position,
                    )
                    orbit_radius = math.hypot(position.x() - center.x(), position.y() - center.y())
                    if orbit_radius <= 0.01:
                        orbit_radius = default_orbit_radius
                    satellite_item = self._add_circle(
                        satellite_node,
                        position,
                        self._satellite_radius(satellite),
                        system_index=system_index,
                        drag_mode="orbit",
                        orbit_center=center,
                        orbit_radius=orbit_radius,
                    )
                    system_items.append(satellite_item)
                    self._add_dashed_line(
                        star_item,
                        satellite_item,
                        satellite_node.color,
                        width=0.95,
                    )
        star_item.drag_followers = system_items

    def _satellite_default_position(
        self,
        star: KnowledgeGraphNode,
        satellite,
        layer_index: int,
        band_index: int,
        index: int,
        count: int,
        radius: float,
        phase: float,
    ) -> tuple[QPointF, float]:
        angle = (
            self._orbit_angle(
                star.planet or "satellite",
                f"{star.title}:{layer_index}:{band_index}",
                satellite.title,
                index,
                count,
            )
            + phase
        )
        radial_jitter = (
            self._stable_unit(f"satellite-radius:{star.title}:{satellite.title}:{band_index}") - 0.5
        ) * 8
        satellite_orbit_radius = radius + radial_jitter
        return (
            QPointF(
                math.cos(angle) * satellite_orbit_radius,
                math.sin(angle) * satellite_orbit_radius,
            ),
            satellite_orbit_radius,
        )

    def _satellite_layer_bands(self, layer: list[object], base_radius: float) -> list[tuple[list[object], float]]:
        if not layer:
            return []
        per_band = 4 if len(layer) <= 4 else 6
        bands: list[tuple[list[object], float]] = []
        for start in range(0, len(layer), per_band):
            bands.append((layer[start : start + per_band], base_radius + len(bands) * 54))
        return bands

    def _satellite_layers(self, satellites) -> list[list[object]]:
        layers: list[list[object]] = [[], [], []]
        for satellite in satellites:
            category = self._satellite_category(satellite)
            if category in {"heading", "excerpt", "annotation"}:
                layer_index = 0
            elif category in {"citation", "link", "backlink", "reference"}:
                layer_index = 1
            else:
                layer_index = 2
            layers[layer_index].append(satellite)
        if not layers[0] and sum(bool(layer) for layer in layers) == 1:
            for index, layer in enumerate(layers):
                if layer:
                    layers[1] = layer
                    layers[index] = [] if index != 1 else layers[index]
                    break
        return layers

    def _satellite_layer_label(self, layer_index: int) -> str:
        labels = ("内容", "关系", "元数据")
        return labels[layer_index] if 0 <= layer_index < len(labels) else "卫星"

    def _satellite_node(self, star: KnowledgeGraphNode, satellite) -> KnowledgeGraphNode:
        category = self._satellite_category(satellite)
        category_label = self._satellite_category_label(category)
        preview = str(getattr(satellite, "preview", "")).strip()
        description = f"{category_label}"
        if preview:
            description = f"{description}\n{preview}"
        return KnowledgeGraphNode(
            kind=KnowledgeObjectKind.SATELLITE,
            title=str(getattr(satellite, "title", "")),
            color=self._satellite_color(satellite),
            path=star.path,
            description=description,
            planet=star.planet,
            tags=star.tags,
            satellites=(satellite,),
        )

    def _satellite_color(self, satellite) -> str:
        category = self._satellite_category(satellite)
        if category == "heading":
            return "#9ed0ff"
        if category in {"excerpt", "pdf"}:
            return "#f6c177"
        if category == "annotation":
            return "#ffd166"
        if category in {"citation", "reference"}:
            return CITATION_COMMUNICATION_COLOR
        if category in {"backlink", "link"}:
            return BACKLINK_COMMUNICATION_COLOR
        if category == "tag":
            return "#8be6c1"
        return "#d6dde3"

    def _satellite_radius(self, satellite) -> float:
        category = self._satellite_category(satellite)
        if category == "heading":
            return 16
        if category in {"excerpt", "annotation", "citation", "reference", "backlink", "link"}:
            return 14
        return 12

    def _satellite_category(self, satellite) -> str:
        kind = str(getattr(satellite, "kind", "")).lower()
        if "heading" in kind or "outline" in kind:
            return "heading"
        if "quote" in kind or "excerpt" in kind:
            return "excerpt"
        if "annotation" in kind or "comment" in kind or "note" in kind:
            return "annotation"
        if "citation" in kind:
            return "citation"
        if "reference" in kind or "pdf" in kind:
            return "reference"
        if "backlink" in kind:
            return "backlink"
        if "link" in kind:
            return "link"
        if "tag" in kind:
            return "tag"
        return "other"

    def _satellite_category_label(self, category: str) -> str:
        return {
            "heading": "标题卫星",
            "excerpt": "摘录卫星",
            "annotation": "批注卫星",
            "citation": "引用卫星",
            "reference": "文献卫星",
            "backlink": "反链卫星",
            "link": "链接卫星",
            "tag": "标签卫星",
        }.get(category, "信息卫星")

    def _add_star_with_satellites(self, star: KnowledgeGraphNode, position: QPointF) -> None:
        star_item = self._add_circle(star, position, 30)
        satellites = list(star.satellites[:6])
        if not satellites:
            return

        satellite_nodes = [self._satellite_node(star, satellite) for satellite in satellites]
        for satellite_node, offset in zip(
            satellite_nodes,
            self._radial_positions(len(satellite_nodes), 62),
            strict=False,
        ):
            satellite_item = self._add_circle(satellite_node, position + offset, 18)
            self._add_dashed_line(star_item, satellite_item, satellite_node.color)

    def _add_circle(
        self,
        node: KnowledgeGraphNode,
        position: QPointF,
        radius: float,
        *,
        system_index: int | None = None,
        drag_mode: str = "free",
        orbit_center: QPointF | None = None,
        orbit_radius: float = 0.0,
    ) -> KnowledgeCircleItem:
        item = KnowledgeCircleItem(
            node,
            radius,
            self._on_node_clicked,
            self._on_node_context_requested,
            self._on_node_double_clicked,
            self._on_node_moved,
        )
        item.system_index = system_index
        item.drag_mode = drag_mode
        item.orbit_center = QPointF(orbit_center) if orbit_center is not None else QPointF(0, 0)
        item.orbit_radius = orbit_radius
        if node.description:
            item.setToolTip(node.description)
        item.setPos(position if self._cover_mode else QPointF(0, 0))
        item._last_scene_pos = item.scenePos()
        item.setOpacity(0.0)
        item.setScale(0.88 if self._cover_mode else 0.72)
        self.scene.addItem(item)
        self._pending_entrance.append((item, position))
        return item

    def _add_orbit_label(
        self,
        node: KnowledgeGraphNode,
        position: QPointF,
        *,
        system_index: int | None = None,
        orbit_center: QPointF | None = None,
        orbit_radius: float = 0.0,
    ) -> KnowledgeOrbitLabelItem:
        item = KnowledgeOrbitLabelItem(
            node,
            self._on_node_clicked,
            self._on_node_context_requested,
            self._on_node_moved,
        )
        item.system_index = system_index
        item.orbit_center = QPointF(orbit_center) if orbit_center is not None else QPointF(0, 0)
        item.orbit_radius = orbit_radius
        item.set_center_pos(position if self._cover_mode else QPointF(0, 0))
        item.setOpacity(0.0)
        item.setScale(0.88 if self._cover_mode else 0.72)
        item.setZValue(2)
        self.scene.addItem(item)
        self._pending_entrance.append((item, position))
        return item

    def _add_orbit(self, center: QPointF, radius: float) -> QGraphicsEllipseItem:
        orbit = QGraphicsEllipseItem(-radius, -radius, radius * 2, radius * 2)
        orbit.setPos(center)
        pen = QPen(QColor("#d8e6f3"))
        pen.setWidthF(0.48)
        pen.setCosmetic(True)
        orbit.setPen(pen)
        orbit.setBrush(Qt.BrushStyle.NoBrush)
        orbit.setOpacity(0.0)
        orbit.setZValue(-4)
        self.scene.addItem(orbit)
        self._pending_fade.append(orbit)
        return orbit

    def _add_dashed_line(
        self,
        source: KnowledgeCircleItem,
        target: KnowledgeCircleItem,
        color: str,
        *,
        width: float = 1.4,
        dashed: bool = True,
    ) -> None:
        line = KnowledgeConnectorLine(source, target, color, width=width, dashed=dashed)
        self.scene.addItem(line)
        self._pending_fade.append(line)

    def _add_center_text(self, text: str) -> None:
        self._add_text_at(text, QPointF(0, 0))

    def _add_text_at(
        self,
        text: str,
        position: QPointF,
        *,
        font_size: int = 12,
        color: str = "#8da9bd",
    ) -> QGraphicsTextItem:
        item = QGraphicsTextItem(text)
        item.setDefaultTextColor(QColor(color))
        item.setFont(QFont("Microsoft YaHei UI", font_size))
        rect = item.boundingRect()
        item.setPos(position.x() - rect.width() / 2, position.y() - rect.height() / 2)
        self.scene.addItem(item)
        self._pending_fade.append(item)
        return item

    def _render_empty_state(self) -> None:
        self._stop_animations()
        self._clear_scene_for_render()
        self._set_scene_rect()
        self._add_center_text("等待工作区模型")
        self.back_button.setEnabled(False)
        self._animate_items_in()
        self._fit_scene()

    def _clear_scene_for_render(self) -> None:
        self.scene.clear()
        self._pending_entrance = []
        self._pending_fade = []

    def _transition_to(self, render_callback) -> None:
        self._stop_animations()
        self._is_transitioning = True
        items = self.scene.items()
        if not items:
            render_callback()
            self._is_transitioning = False
            return

        remaining = {"count": len(items)}

        def mark_finished() -> None:
            remaining["count"] -= 1
            if remaining["count"] <= 0:
                render_callback()
                self._is_transitioning = False

        for item in items:
            animation = QVariantAnimation(self)
            animation.setDuration(150)
            animation.setStartValue(1.0)
            animation.setEndValue(0.0)
            animation.setEasingCurve(QEasingCurve.Type.InQuad)
            animation.valueChanged.connect(lambda value, target=item: target.setOpacity(float(value)))
            animation.finished.connect(mark_finished)
            self._animations.append(animation)
            animation.start()

    def _animate_items_in(self) -> None:
        for item, final_position in self._pending_entrance:
            self._animate_item_opacity(item, 0.0, 1.0, 230)
            if self._cover_mode:
                self._animate_item_scale(item, 0.88, 1.0, 180)
            else:
                self._animate_item_scale(item, 0.72, 1.0, 230)
                self._animate_item_position(item, QPointF(0, 0), final_position, 260)

        for item in self._pending_fade:
            self._animate_item_opacity(item, 0.0, 1.0, 260)

    def _pulse_item(self, item: KnowledgeCircleItem, finished_callback) -> None:
        self._stop_animations()
        self._is_transitioning = True
        animation = QVariantAnimation(self)
        animation.setDuration(150)
        animation.setStartValue(1.0)
        animation.setKeyValueAt(0.5, 1.16)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.valueChanged.connect(lambda value: item.setScale(float(value)))

        def finish() -> None:
            self._is_transitioning = False
            finished_callback()

        animation.finished.connect(finish)
        self._animations.append(animation)
        animation.start()

    def _animate_item_opacity(self, item, start: float, end: float, duration: int) -> None:
        animation = QVariantAnimation(self)
        animation.setDuration(duration)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.valueChanged.connect(lambda value, target=item: target.setOpacity(float(value)))
        self._animations.append(animation)
        animation.start()

    def _animate_item_scale(self, item, start: float, end: float, duration: int) -> None:
        animation = QVariantAnimation(self)
        animation.setDuration(duration)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.setEasingCurve(QEasingCurve.Type.OutBack)
        animation.valueChanged.connect(lambda value, target=item: target.setScale(float(value)))
        self._animations.append(animation)
        animation.start()

    def _animate_item_position(self, item, start: QPointF, end: QPointF, duration: int) -> None:
        animation = QVariantAnimation(self)
        animation.setDuration(duration)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        def apply_position(value, target=item) -> None:
            if isinstance(target, KnowledgeOrbitLabelItem):
                target.set_center_pos(value)
            else:
                target.setPos(value)

        animation.valueChanged.connect(apply_position)
        self._animations.append(animation)
        animation.start()

    def _animate_communication_line(self, line: KnowledgeCommunicationLine) -> None:
        animation = QVariantAnimation(self)
        animation.setDuration(1250)
        animation.setStartValue(0.0)
        animation.setEndValue(-26.0)
        animation.setLoopCount(-1)
        animation.setEasingCurve(QEasingCurve.Type.Linear)
        animation.valueChanged.connect(lambda value, target=line: target.set_dash_offset(float(value)))
        self._animations.append(animation)
        animation.start()

    def _stop_animations(self) -> None:
        for animation in self._animations:
            animation.stop()
        self._animations.clear()

    def _set_scene_rect(self) -> None:
        if self._cover_mode:
            self.scene.setSceneRect(-720, -460, 1440, 920)
        else:
            self.scene.setSceneRect(-300, -220, 600, 440)

    def _fit_scene(self) -> None:
        if self._cover_mode:
            rect = self._planned_items_rect() or self.scene.itemsBoundingRect()
            if rect.isNull() or rect.width() < 40 or rect.height() < 40:
                rect = self.scene.sceneRect()
            margin = 72
            rect = rect.adjusted(-margin, -margin, margin, margin)
            self.scene.setSceneRect(rect)
            self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self._cover_zoom = 1.0
            return
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _planned_items_rect(self) -> QRectF | None:
        if not self._pending_entrance:
            return None

        left = math.inf
        top = math.inf
        right = -math.inf
        bottom = -math.inf
        for item, position in self._pending_entrance:
            if isinstance(item, KnowledgeCircleItem):
                horizontal_pad = max(item.radius, item._label_width() / 2)
                vertical_top = item.radius
                vertical_bottom = item.radius + item.label_item.boundingRect().height() + 10
            else:
                rect = item.boundingRect()
                horizontal_pad = rect.width() / 2
                vertical_top = rect.height() / 2
                vertical_bottom = rect.height() / 2
            left = min(left, position.x() - horizontal_pad)
            top = min(top, position.y() - vertical_top)
            right = max(right, position.x() + horizontal_pad)
            bottom = max(bottom, position.y() + vertical_bottom)

        if not math.isfinite(left):
            return None
        return QRectF(QPointF(left, top), QPointF(right, bottom))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._queue_fit_scene()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._queue_fit_scene()

    def _queue_fit_scene(self) -> None:
        self._fit_scene()
        if self._cover_mode:
            QTimer.singleShot(0, self._fit_scene)
            QTimer.singleShot(80, self._fit_scene)
            QTimer.singleShot(220, self._fit_scene)

    def _radial_positions(self, count: int, radius: float) -> list[QPointF]:
        if count <= 0:
            return []
        if count == 1:
            return [QPointF(0, 0)]
        return [
            QPointF(math.cos(2 * math.pi * index / count) * radius, math.sin(2 * math.pi * index / count) * radius)
            for index in range(count)
        ]

    def _cover_system_centers(self, count: int) -> list[QPointF]:
        if count <= 0:
            return []
        if count == 1:
            return [QPointF(0, 0)]
        columns = max(1, math.ceil(math.sqrt(count)))
        rows = math.ceil(count / columns)
        spacing_x = 540
        spacing_y = 410
        start_x = -((columns - 1) * spacing_x) / 2
        start_y = -((rows - 1) * spacing_y) / 2
        centers: list[QPointF] = []
        for index in range(count):
            base = QPointF(
                start_x + (index % columns) * spacing_x,
                start_y + (index // columns) * spacing_y,
            )
            centers.append(base + self._jitter_vector(f"galaxy:{index}", 36, 26))
        return centers

    def _jittered_radial_positions(
        self,
        labels: Iterable[str],
        center: QPointF,
        *,
        radius: float,
        spread: float,
        salt: str,
    ) -> list[QPointF]:
        titles = list(labels)
        count = len(titles)
        if count <= 0:
            return []
        if count == 1:
            return [center + self._jitter_vector(f"{salt}:single:{titles[0]}", spread, spread)]

        positions: list[QPointF] = []
        angle_offset = self._stable_unit(f"{salt}:offset") * math.pi
        for index, title in enumerate(titles):
            angle_jitter = (self._stable_unit(f"{salt}:{title}:angle") - 0.5) * 0.48
            distance_jitter = (self._stable_unit(f"{salt}:{title}:distance") - 0.5) * spread
            angle = 2 * math.pi * index / count + angle_offset + angle_jitter
            distance = radius + distance_jitter
            positions.append(
                center
                + QPointF(
                    math.cos(angle) * distance,
                    math.sin(angle) * distance,
                )
            )
        return positions

    def _jitter_vector(self, key: str, max_x: float, max_y: float) -> QPointF:
        return QPointF(
            (self._stable_unit(f"{key}:x") - 0.5) * max_x,
            (self._stable_unit(f"{key}:y") - 0.5) * max_y,
        )

    def _stable_unit(self, key: str) -> float:
        seed = sum((index + 1) * ord(char) for index, char in enumerate(key))
        return math.sin(seed * 12.9898) % 1.0

    def _grid_positions(self, count: int, spacing: float) -> list[QPointF]:
        if count <= 0:
            return []
        columns = max(1, math.ceil(math.sqrt(count)))
        rows = math.ceil(count / columns)
        start_x = -((columns - 1) * spacing) / 2
        start_y = -((rows - 1) * spacing) / 2
        return [
            QPointF(start_x + (index % columns) * spacing, start_y + (index // columns) * spacing)
            for index in range(count)
        ]
