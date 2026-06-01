import argparse
import sys

from PySide6.QtWidgets import QApplication

from app.bootstrap.startup import bootstrap_app
from app.ui.main_window import MainWindow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agni desktop app")
    parser.add_argument(
        "--workspace",
        type=str,
        default="./workspace_template",
        help="Path to workspace root",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    app_config, app_context = bootstrap_app(args.workspace)

    app = QApplication(sys.argv)
    app.setApplicationName(app_config.app_name)
    app.setOrganizationName(app_config.organization_name)

    window = MainWindow(app_context)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
