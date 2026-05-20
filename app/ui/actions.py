from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget


def create_action(
    parent: QWidget,
    text: str,
    *,
    shortcut: str | None = None,
    status_tip: str = "",
    checkable: bool = False,
    checked: bool = False,
) -> QAction:
    action = QAction(text, parent)
    if shortcut:
        action.setShortcut(shortcut)
    if status_tip:
        action.setStatusTip(status_tip)
        action.setToolTip(status_tip)
    action.setCheckable(checkable)
    action.setChecked(checked)
    return action


@dataclass(slots=True)
class AgniActionSet:
    new_note: QAction
    open_workspace: QAction
    save_note: QAction
    delete_note: QAction
    command_palette: QAction
    focus_search: QAction
    toggle_notes: QAction
    toggle_search: QAction
    toggle_outline: QAction
    refresh_workspace: QAction
    about: QAction

    @classmethod
    def build(cls, parent: QWidget) -> "AgniActionSet":
        return cls(
            new_note=create_action(
                parent,
                "新建笔记",
                shortcut="Ctrl+N",
                status_tip="创建一篇新的 Markdown 笔记",
            ),
            open_workspace=create_action(
                parent,
                "打开工作区",
                shortcut="Ctrl+O",
                status_tip="选择一个 Agni 工作区目录",
            ),
            save_note=create_action(
                parent,
                "保存",
                shortcut="Ctrl+S",
                status_tip="保存当前笔记",
            ),
            delete_note=create_action(
                parent,
                "删除笔记",
                shortcut="Delete",
                status_tip="删除当前笔记",
            ),
            command_palette=create_action(
                parent,
                "命令面板",
                shortcut="Ctrl+K",
                status_tip="打开常用操作入口",
            ),
            focus_search=create_action(
                parent,
                "搜索",
                shortcut="Ctrl+F",
                status_tip="聚焦全局搜索面板",
            ),
            toggle_notes=create_action(
                parent,
                "左侧资源",
                status_tip="显示或隐藏左侧资源面板",
                checkable=True,
                checked=True,
            ),
            toggle_search=create_action(
                parent,
                "搜索反链",
                status_tip="显示或隐藏搜索与反向链接面板",
                checkable=True,
                checked=True,
            ),
            toggle_outline=create_action(
                parent,
                "大纲 PDF",
                status_tip="显示或隐藏大纲与 PDF 面板",
                checkable=True,
                checked=True,
            ),
            refresh_workspace=create_action(
                parent,
                "刷新工作区",
                shortcut="F5",
                status_tip="重新扫描笔记、文献与附件",
            ),
            about=create_action(
                parent,
                "关于 Agni",
                status_tip="查看当前工作台说明",
            ),
        )


def build_app_stylesheet() -> str:
    return """
    QMainWindow#agni_main_window {
        background: #08111f;
    }

    QWidget {
        color: #d8e6f3;
        font-family: "Microsoft YaHei UI", "Segoe UI", Arial;
        font-size: 13px;
    }

    QMenuBar {
        background: #08111f;
        color: #d8e6f3;
        padding: 4px 8px;
        border-bottom: 1px solid #182a3d;
    }

    QMenuBar::item {
        padding: 6px 10px;
        border-radius: 6px;
    }

    QMenuBar::item:selected {
        background: #10243a;
        color: #8bd8ff;
    }

    QMenu {
        background: #0d1b2d;
        border: 1px solid #203957;
        padding: 6px;
    }

    QMenu::item {
        padding: 7px 26px 7px 12px;
        border-radius: 5px;
    }

    QMenu::item:selected {
        background: #143454;
        color: #a8e5ff;
    }

    QToolBar {
        background: #0b1728;
        border: 0;
        border-bottom: 1px solid #18304b;
        spacing: 6px;
        padding: 6px 10px;
    }

    QToolButton {
        background: #10243a;
        border: 1px solid #24476b;
        color: #d8e6f3;
        padding: 7px 10px;
        border-radius: 6px;
    }

    QToolButton:hover {
        background: #153554;
        border-color: #43b8ff;
    }

    QStatusBar {
        background: #08111f;
        color: #8da9bd;
        border-top: 1px solid #18304b;
    }

    QDialog,
    QMessageBox,
    QInputDialog {
        background: #0b1728;
        color: #d8e6f3;
    }

    QDialog#command_palette_dialog {
        background: #0b1728;
        border: 1px solid #23496f;
        border-radius: 10px;
    }

    QDialog QLabel,
    QMessageBox QLabel,
    QInputDialog QLabel {
        color: #d8e6f3;
        background: transparent;
    }

    QDialogButtonBox {
        background: transparent;
        padding-top: 8px;
    }

    QMessageBox QPushButton,
    QInputDialog QPushButton,
    QDialogButtonBox QPushButton {
        min-width: 74px;
        min-height: 28px;
    }

    QDockWidget {
        background: #0b1728;
        titlebar-close-icon: none;
        titlebar-normal-icon: none;
    }

    QDockWidget::title {
        background: #0e2035;
        color: #9fdcff;
        padding: 8px 10px;
        border-bottom: 1px solid #1d3a59;
    }

    QFrame#dock_surface,
    QWidget#dock_surface {
        background: #0b1728;
        border: 1px solid #18304b;
        border-radius: 8px;
    }

    QTabWidget::pane {
        border: 1px solid #18304b;
        border-radius: 8px;
        background: #0b1728;
        top: -1px;
    }

    QTabBar::tab {
        background: #0f2034;
        color: #8da9bd;
        padding: 7px 12px;
        border-top-left-radius: 7px;
        border-top-right-radius: 7px;
        margin-right: 3px;
    }

    QTabBar::tab:selected {
        background: #163956;
        color: #a8e5ff;
    }

    QLineEdit,
    QPlainTextEdit,
    QTextEdit {
        background: #07101c;
        border: 1px solid #1d3a59;
        color: #d8e6f3;
        border-radius: 7px;
        padding: 8px;
        selection-background-color: #1f6fa4;
    }

    QLineEdit:focus,
    QPlainTextEdit:focus,
    QTextEdit:focus {
        border-color: #43b8ff;
    }

    QListWidget,
    QTreeWidget {
        background: #07101c;
        border: 1px solid #1d3a59;
        border-radius: 7px;
        padding: 4px;
        outline: 0;
    }

    QListWidget::item,
    QTreeWidget::item {
        padding: 7px 8px;
        border-radius: 5px;
    }

    QListWidget::item:selected,
    QTreeWidget::item:selected {
        background: #17476b;
        color: #ffffff;
    }

    QListWidget::item:hover,
    QTreeWidget::item:hover {
        background: #102b45;
    }

    QPushButton {
        background: #143454;
        border: 1px solid #2b638c;
        color: #e6f4ff;
        padding: 7px 11px;
        border-radius: 7px;
    }

    QPushButton:hover {
        background: #1b4f78;
        border-color: #60c7ff;
    }

    QPushButton#destructive_button {
        background: #3a1620;
        border-color: #7f3046;
        color: #ffdce4;
    }

    QPushButton#destructive_button:hover {
        background: #5a2030;
        border-color: #ff6b8a;
    }

    QLabel#section_label,
    QLabel#note_editor_title_label {
        color: #a8e5ff;
        font-weight: 600;
    }

    QLabel#knowledge_dashboard,
    QLabel#inspector_label {
        background: #07101c;
        border: 1px solid #1d3a59;
        border-radius: 8px;
        color: #d8e6f3;
        line-height: 1.5;
    }

    QDialog QLabel#section_label {
        color: #a8e5ff;
        font-size: 15px;
    }

    QSplitter::handle {
        background: #12263c;
    }
    """
