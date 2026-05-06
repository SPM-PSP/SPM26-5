<<<<<<< HEAD
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.bootstrap import build_startup_pipeline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agni workspace bootstrap entry point.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Path to the knowledge base workspace.",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Skip launching the placeholder main window.",
    )
    return parser.parse_args(argv)


def launch_placeholder_window(window_title: str, workspace_root: str) -> int:
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle(window_title)
    window.resize(960, 640)
    window.setCentralWidget(QLabel(f"Workspace ready:\n{workspace_root}"))
    window.show()
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app_controller = build_startup_pipeline()
    result = app_controller.start_app(args.workspace)

    if not result["success"]:
        print(result["message"], file=sys.stderr)
        return 1

    main_window_payload = result["data"]["main_window"]
    if args.no_gui:
        print(result["message"])
        print(main_window_payload["workspace_root"])
        return 0

    return launch_placeholder_window(
        window_title=main_window_payload["window_title"],
        workspace_root=main_window_payload["workspace_root"],
    )


if __name__ == "__main__":
    raise SystemExit(main())
=======
import argparse
import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from app.bootstrap.startup import bootstrap_app


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
>>>>>>> 549c716 (Finish the basic code framework)
