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
