from __future__ import annotations

from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFrame, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        event.ignore()


class LiquidGlassCard(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", variant: str = "default") -> None:
        super().__init__()
        self.setObjectName("LiquidGlassCard")
        self.setProperty("variant", variant)
        self.setMinimumHeight(112)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 18, 20, 18)
        self.layout.setSpacing(8)
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("LiquidCardTitle")
            self.layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("LiquidMutedText")
            subtitle_label.setWordWrap(True)
            self.layout.addWidget(subtitle_label)


class LiquidPillButton(QPushButton):
    def __init__(self, text: str = "", variant: str = "ghost") -> None:
        super().__init__(text)
        self.setObjectName("LiquidPillButton")
        self.setProperty("variant", variant)
        self.setMinimumHeight(38)


class GlassPanel(QFrame):
    def __init__(self, object_name: str = "GlassPanel", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)


class GlassSidebar(GlassPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("GlassSidebar", parent)
        self.setFixedWidth(220)


class GlassToolbar(GlassPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("GlassToolbar", parent)
        self.setFixedHeight(72)


class GlassStatusBar(GlassPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("GlassStatusBar", parent)
        self.setFixedHeight(36)


class GlassProgressBar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("GlassProgressBar")


class AppShell(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("AppShell")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 20, 24, 24)
        self.layout.setSpacing(16)

        self.toolbar = GlassToolbar()
        self.layout.addWidget(self.toolbar)

        self.body = QFrame()
        self.body.setObjectName("AppShellBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(16)

        self.workspace = QFrame()
        self.workspace.setObjectName("AppWorkspace")
        self.workspace_layout = QVBoxLayout(self.workspace)
        self.workspace_layout.setContentsMargins(0, 0, 0, 0)
        self.workspace_layout.setSpacing(16)
        self.body_layout.addWidget(self.workspace, 1)

        self.layout.addWidget(self.body, 1)
