from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QVBoxLayout, QWidget

from image_toolbox.core.config import AppConfig
from image_toolbox.core.image_ops import convert_image
from image_toolbox.features.base import ToolFeature


class ConversionFeature(ToolFeature):
    key = "convert"
    title = "格式转换"
    description = "批量转换图片格式，适合素材整理与跨平台导出。"

    def __init__(self) -> None:
        self.config = AppConfig(self.key)
        self.format_combo: QComboBox | None = None
        self.quality_slider: QSlider | None = None
        self.output_edit: QLineEdit | None = None

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

        group = QGroupBox("转换参数")
        form = QFormLayout(group)
        form.setSpacing(14)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPG", "PNG", "WEBP", "BMP", "TIFF"])
        saved_format = self.config.get("format", "JPG")
        self.format_combo.setCurrentIndex(max(0, self.format_combo.findText(saved_format)))
        form.addRow("目标格式", self.format_combo)

        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setRange(40, 100)
        self.quality_slider.setValue(self.config.get("quality", 90, int))
        quality_value = QLabel(str(self.quality_slider.value()))
        self.quality_slider.valueChanged.connect(lambda value: quality_value.setText(str(value)))
        quality_row = QHBoxLayout()
        quality_row.addWidget(self.quality_slider)
        quality_row.addWidget(quality_value)
        form.addRow("质量", quality_row)

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
        target_format = self.format_combo.currentText() if self.format_combo else "JPG"
        quality = self.quality_slider.value() if self.quality_slider else 90
        self.config.set("output_dir", str(output_dir))
        self.config.set("format", target_format)
        self.config.set("quality", quality)
        return lambda source, logger: convert_image(source, output_dir, target_format, quality, logger)

    def get_output_dir(self) -> Path | None:
        return Path(self.output_edit.text()) if self.output_edit and self.output_edit.text() else None

    def _choose_output(self) -> None:
        if not self.output_edit:
            return
        directory = QFileDialog.getExistingDirectory(None, "选择输出目录", self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)
