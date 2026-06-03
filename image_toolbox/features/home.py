from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from image_toolbox import APP_NAME, APP_VERSION


class HomePanel(QWidget):
    feature_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        title = QLabel(APP_NAME)
        title.setObjectName("HeroTitle")
        version = QLabel(f"Version {APP_VERSION}")
        version.setObjectName("MutedText")
        intro = QLabel("V3.3.8 新增智能媒体增强工作台，统一预留图片、动图、视频超分与 AI 插帧处理入口。")
        intro.setWordWrap(True)
        intro.setObjectName("IntroText")

        layout.addWidget(title)
        layout.addWidget(version)
        layout.addWidget(intro)

        grid = QGridLayout()
        grid.setSpacing(14)
        layout.addLayout(grid)

        entries = [
            ("图片压缩", "降低图片体积，保留常用格式输出。", "compress"),
            ("格式转换", "批量转换 JPG、PNG、WEBP、BMP 等格式。", "convert"),
            ("批量改尺寸", "按比例或指定宽高缩放，可保持原比例。", "resize"),
            ("智能媒体增强", "统一管理图片超分、动图增强、视频超分与 AI 插帧工作流。", "super_resolution"),
            ("批量加水印", "添加文字或图片水印，控制位置与透明度。", "watermark"),
            ("批量重命名", "组合前缀、后缀、原名和自动编号。", "rename"),
        ]
        for index, (name, desc, key) in enumerate(entries):
            card = QFrame()
            card.setObjectName("FeatureCard")
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(10)
            card_title = QLabel(name)
            card_title.setObjectName("CardTitle")
            card_desc = QLabel(desc)
            card_desc.setWordWrap(True)
            card_desc.setObjectName("MutedText")
            button = QPushButton("打开")
            button.clicked.connect(lambda _checked=False, feature_key=key: self.feature_requested.emit(feature_key))
            card_layout.addWidget(card_title)
            card_layout.addWidget(card_desc)
            card_layout.addStretch()
            card_layout.addWidget(button)
            grid.addWidget(card, index // 3, index % 3)

        layout.addStretch()
