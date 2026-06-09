from __future__ import annotations

import sys

from PySide6.QtCore import QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QLabel, QProgressBar, QVBoxLayout, QWidget

from image_toolbox import APP_NAME, APP_VERSION
from image_toolbox.core.paths import get_app_icon_image_path, get_app_icon_path
from image_toolbox.ui.theme import DARK_THEME


class StartupSplash(QWidget):
    def __init__(self, icon_path) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.SplashScreen
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(430, 372)
        self.setWindowOpacity(0.96)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)

        panel = QFrame()
        panel.setObjectName("StartupSplashPanel")
        panel.setStyleSheet(
            """
            QFrame#StartupSplashPanel {
                background: rgba(250, 252, 255, 224);
                border: 1px solid rgba(106, 151, 212, 112);
                border-radius: 26px;
            }
            QLabel#SplashTitle {
                color: #172033;
                font-family: "Segoe UI Variable", "Microsoft YaHei UI", "Segoe UI", Arial;
                font-size: 29px;
                font-weight: 800;
                letter-spacing: 0px;
            }
            QLabel#SplashSubtitle {
                color: rgba(37, 52, 79, 190);
                font-family: "Segoe UI Variable", "Microsoft YaHei UI", "Segoe UI", Arial;
                font-size: 13px;
                letter-spacing: 0px;
            }
            QLabel#SplashStatus {
                color: rgba(37, 52, 79, 210);
                font-family: "Segoe UI Variable", "Microsoft YaHei UI", "Segoe UI", Arial;
                font-size: 12px;
                letter-spacing: 0px;
            }
            QLabel#SplashPercent {
                color: rgba(31, 45, 71, 220);
                font-family: "Segoe UI Variable", "Microsoft YaHei UI", "Segoe UI", Arial;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0px;
            }
            QProgressBar#SplashProgress {
                height: 8px;
                border: none;
                border-radius: 4px;
                background: rgba(209, 223, 244, 170);
                text-align: center;
                color: transparent;
            }
            QProgressBar#SplashProgress::chunk {
                border-radius: 4px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #36c8ff,
                    stop: 0.55 #4f7cff,
                    stop: 1 #ff7bd5
                );
            }
            """
        )
        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(44)
        shadow.setOffset(0, 16)
        shadow.setColor(QColor(23, 38, 66, 96))
        panel.setGraphicsEffect(shadow)
        outer.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(34, 30, 34, 26)
        layout.setSpacing(12)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(icon_path))
        if not pixmap.isNull():
            self.icon_label.setPixmap(
                pixmap.scaled(
                    142,
                    142,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignCenter)

        title = QLabel(APP_NAME)
        title.setObjectName("SplashTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(f"AI media enhancement assistant  v{APP_VERSION}")
        subtitle.setObjectName("SplashSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(10)

        self.progress = QProgressBar()
        self.progress.setObjectName("SplashProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.percent = QLabel("0%")
        self.percent.setObjectName("SplashPercent")
        self.percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.percent)

        self.status = QLabel("\u6b63\u5728\u542f\u52a8...")
        self.status.setObjectName("SplashStatus")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

    def show_centered(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            self.move(
                geometry.center().x() - self.width() // 2,
                geometry.center().y() - self.height() // 2,
            )
        self.show()
        self.raise_()
        QApplication.processEvents()

    def set_progress(self, value: int, status: str) -> None:
        self.progress.setValue(value)
        self.percent.setText(f"{value}%")
        self.status.setText(status)
        QApplication.processEvents()

    def finish(self) -> None:
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(180)
        animation.setStartValue(self.windowOpacity())
        animation.setEndValue(0.0)
        animation.finished.connect(self.close)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        QApplication.processEvents()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    icon_path = get_app_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setQuitOnLastWindowClosed(True)
    app.setStyleSheet(DARK_THEME)

    splash_icon_path = get_app_icon_image_path()
    splash = StartupSplash(splash_icon_path if splash_icon_path.exists() else icon_path)
    splash.show_centered()
    splash.set_progress(18, "\u52a0\u8f7d\u4e3b\u9898\u4e0e\u56fe\u6807")

    splash.set_progress(34, "\u52a0\u8f7d\u754c\u9762\u6a21\u5757")
    from image_toolbox.ui.main_window import MainWindow

    splash.set_progress(62, "\u6784\u5efa\u4e3b\u754c\u9762")
    window = MainWindow()
    splash.set_progress(86, "\u51c6\u5907\u5de5\u4f5c\u53f0")
    window.showMaximized()
    splash.set_progress(100, "\u542f\u52a8\u5b8c\u6210")
    splash.finish()

    return app.exec()
