from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from image_toolbox import APP_NAME
from image_toolbox.ui.main_window import MainWindow
from image_toolbox.ui.theme import DARK_THEME


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(True)
    app.setStyleSheet(DARK_THEME)

    window = MainWindow()
    window.show()

    return app.exec()
