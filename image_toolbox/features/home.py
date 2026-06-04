from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from image_toolbox import APP_NAME, APP_VERSION
from image_toolbox.ui.widgets import LiquidGlassCard, LiquidPillButton


class HomePanel(QWidget):
    feature_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("LiquidHome")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(24)

        shell = QFrame()
        shell.setObjectName("LiquidShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(32, 32, 32, 32)
        shell_layout.setSpacing(24)
        root.addWidget(shell, 1)

        shell_layout.addLayout(self._build_header())
        shell_layout.addLayout(self._build_status_row())
        shell_layout.addWidget(self._build_quick_start())
        shell_layout.addWidget(self._build_recent_tasks(), 1)

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(16)

        title_block = QVBoxLayout()
        title_block.setSpacing(8)
        title = QLabel(f"Welcome to {APP_NAME}")
        title.setObjectName("LiquidHeroTitle")
        subtitle = QLabel("A professional AI media enhancement assistant for images, video, and animated assets.")
        subtitle.setObjectName("LiquidMutedText")
        subtitle.setWordWrap(True)
        version = QLabel(f"High-quality Enhancement Assistant  v{APP_VERSION}")
        version.setObjectName("LiquidMutedText")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        title_block.addWidget(version)

        row.addLayout(title_block, 1)
        for label in ["Search", "Alerts", "Settings"]:
            button = LiquidPillButton(label, "soft")
            button.setEnabled(False)
            row.addWidget(button)
        return row

    def _build_status_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(16)
        status_items = [
            ("Model Library", "Ready", "128 models indexed", "blue"),
            ("Tool Status", "Ready", "8 tools detected", "green"),
            ("GPU Status", "NVIDIA GeForce RTX 3060", "8.0 GB / 12.0 GB", "purple"),
            ("Task Status", "2 running", "3 waiting", "default"),
        ]
        for title, value, hint, variant in status_items:
            card = LiquidGlassCard(title, hint, variant)
            card.setMinimumSize(180, 120)
            value_label = QLabel(value)
            value_label.setObjectName("LiquidMetricValue")
            card.layout.insertWidget(1, value_label)
            row.addWidget(card, 1)
        return row

    def _build_quick_start(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("LiquidHeroPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Quick Start")
        title.setObjectName("LiquidSectionTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(16)
        layout.addLayout(grid)

        entries = [
            ("Image Enhance", "Upscale, denoise, sharpen", "blue"),
            ("Video Enhance", "Upscale, interpolate, stabilize", "green"),
            ("Animated Media", "GIF, WebP, APNG pipelines", "purple"),
            ("Batch Workflow", "Convert, rename, normalize", "default"),
            ("Toolbox", "Compress, convert, watermark", "blue"),
        ]
        for column, (name, desc, variant) in enumerate(entries):
            card = LiquidGlassCard(name, desc, variant)
            card.setMinimumSize(150, 140)
            button = LiquidPillButton("Preview", "soft")
            button.setEnabled(False)
            card.layout.addStretch()
            card.layout.addWidget(button)
            grid.addWidget(card, 0, column)
        return panel

    def _build_recent_tasks(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("LiquidHeroPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Recent Tasks")
        title.setObjectName("LiquidSectionTitle")
        view_all = LiquidPillButton("View All", "soft")
        view_all.setEnabled(False)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(view_all)
        layout.addLayout(header)

        task_list = QFrame()
        task_list.setObjectName("LiquidTaskList")
        task_layout = QVBoxLayout(task_list)
        task_layout.setContentsMargins(0, 0, 0, 0)
        task_layout.setSpacing(0)
        task_layout.addWidget(self._build_task_row(("File", "Type", "Status", "Finished", "Output"), header=True))

        rows = [
            ("beautiful_girl_4k.png", "Image", "Done", "05-20 14:30", "output/beautiful_girl_4k_upscaled.png"),
            ("demo_video.mp4", "Video", "Processing 65%", "05-20 12:10", "output/demo_video_enhanced.mp4"),
            ("animation.gif", "Animated", "Done", "05-20 11:05", "output/animation_enhanced.gif"),
            ("landscape.jpg", "Image", "Done", "05-20 09:22", "output/landscape_denoise.png"),
            ("short_clip.mp4", "Video", "Done", "05-19 22:18", "output/short_clip_enhanced.mp4"),
        ]
        for values in rows:
            task_layout.addWidget(self._build_task_row(values))
        task_layout.addStretch(1)
        layout.addWidget(task_list)
        return panel

    def _build_task_row(self, values: tuple[str, ...], header: bool = False) -> QWidget:
        row = QFrame()
        row.setObjectName("LiquidTaskHeaderRow" if header else "LiquidGlassCard")
        if not header:
            row.setMinimumHeight(54)
        grid = QGridLayout(row)
        grid.setContentsMargins(16, 10, 16, 10)
        grid.setHorizontalSpacing(16)
        widths = [2, 1, 1, 1, 2]
        for column, value in enumerate(values):
            label = QLabel(value)
            label.setObjectName("LiquidTaskHeaderText" if header else "LiquidTaskText")
            label.setWordWrap(False)
            grid.addWidget(label, 0, column)
            grid.setColumnStretch(column, widths[column])
        return row
