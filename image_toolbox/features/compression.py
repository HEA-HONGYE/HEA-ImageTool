from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QVBoxLayout, QWidget

from image_toolbox.core.config import AppConfig
from image_toolbox.core.image_ops import compress_image
from image_toolbox.features.base import ToolFeature


class CompressionFeature(ToolFeature):
    key = "compress"
    title = "图片压缩"
    description = "批量压缩 JPG、PNG、WEBP 等图片。"

    def __init__(self) -> None:
        self.config = AppConfig(self.key)
        self.quality_slider: QSlider | None = None
        self.output_edit: QLineEdit | None = None
        self.keep_format_checkbox: QCheckBox | None = None

    def build_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        header = QLabel(self.title)
        header.setObjectName("PanelTitle")
        hint = QLabel(self.description)
        hint.setObjectName("MutedText")
        layout.addWidget(header)
        layout.addWidget(hint)

        group = QGroupBox("压缩参数")
        form = QFormLayout(group)
        form.setSpacing(14)

        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setRange(30, 95)
        self.quality_slider.setValue(self.config.get("quality", 78, int))
        quality_value = QLabel(str(self.quality_slider.value()))
        self.quality_slider.valueChanged.connect(lambda value: quality_value.setText(str(value)))
        quality_row = QHBoxLayout()
        quality_row.addWidget(self.quality_slider)
        quality_row.addWidget(quality_value)
        form.addRow("质量 / JPG、WEBP", quality_row)

        png_note = QLabel("PNG 会使用无损优化，质量滑块仅影响 JPG、WEBP 输出。")
        png_note.setObjectName("MutedText")
        png_note.setWordWrap(True)
        form.addRow("", png_note)

        self.keep_format_checkbox = QCheckBox("保持原格式")
        self.keep_format_checkbox.setChecked(self.config.get("keep_format", True, bool))
        form.addRow("输出", self.keep_format_checkbox)

        self.output_edit = QLineEdit(self.config.get("output_dir", str(Path.cwd() / "output")))
        browse_button = QPushButton("选择")
        browse_button.clicked.connect(self._choose_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit)
        output_row.addWidget(browse_button)
        form.addRow("保存到", output_row)

        layout.addWidget(group)
        layout.addStretch()
        return panel

    def create_processor(self, files: list[Path]) -> Callable[[Path, Callable[[str], None]], Path]:
        output_dir = Path(self.output_edit.text() if self.output_edit else "output")
        output_dir.mkdir(parents=True, exist_ok=True)
        quality = self.quality_slider.value() if self.quality_slider else 78
        keep_format = self.keep_format_checkbox.isChecked() if self.keep_format_checkbox else True
        self.config.set("output_dir", str(output_dir))
        self.config.set("quality", quality)
        self.config.set("keep_format", keep_format)
        return lambda source, logger: compress_image(source, output_dir, quality, keep_format, logger)

    def get_output_dir(self) -> Path | None:
        return Path(self.output_edit.text()) if self.output_edit and self.output_edit.text() else None

    def _choose_output(self) -> None:
        if not self.output_edit:
            return
        directory = QFileDialog.getExistingDirectory(None, "选择输出目录", self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)
