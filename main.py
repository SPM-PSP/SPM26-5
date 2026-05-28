import argparse
import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from app.bootstrap.startup import bootstrap_app

# from app.database.tool import connect_to_database

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agni desktop app")
    parser.add_argument(
        "--workspace",
        type=str,
        default="./workspace_template",
        help="Path to workspace root",
    )
    return parser.parse_args()


def build_fallback_window(workspace_root: str) -> QMainWindow:
    """
    当 Gao 的真正 MainWindow 还没接入时，使用一个最小占位窗口，
    保证 Zhang 这边的启动入口先可运行。
    """
    window = QMainWindow()
    window.setWindowTitle("Agni - Bootstrap Ready")
    window.resize(1000, 700)

    label = QLabel(
        f"Agni has bootstrapped successfully.\n\nWorkspace: {workspace_root}",
        parent=window,
    )
    label.setMargin(20)
    window.setCentralWidget(label)
    return window


def build_main_window(app_context):
    """
    优先尝试加载真正的 MainWindow；
    若 UI 侧尚未完成，则退回到占位窗口。
    """
    try:
        from app.ui.main_window import MainWindow  # type: ignore

        return MainWindow(app_context)
    except Exception:
        return build_fallback_window(str(app_context.workspace_root))


def main() -> int:
    args = parse_args()

    app_config, app_context = bootstrap_app(args.workspace)

    app = QApplication(sys.argv)
    app.setApplicationName(app_config.app_name)
    app.setOrganizationName(app_config.organization_name)

    window = build_main_window(app_context)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())