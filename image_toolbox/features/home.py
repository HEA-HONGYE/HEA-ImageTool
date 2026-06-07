from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget


class HomePanel(QWidget):
    feature_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("LiquidHome")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)
        root.addStretch(1)
