from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QVBoxLayout, QWidget

from image_toolbox.core.config import AppConfig
from image_toolbox.core.image_ops import add_image_watermark, add_text_watermark
from image_toolbox.features.base import ToolFeature
from image_toolbox.ui.widgets import NoWheelComboBox as QComboBox
from image_toolbox.ui.widgets import NoWheelSpinBox as QSpinBox


class WatermarkFeature(ToolFeature):
    key = "watermark"
    title = "批量添加水印"
    description = "支持文字水印和图片水印，可设置位置、透明度与字体大小。"

    def __init__(self) -> None:
        self.config = AppConfig(self.key)
        self.type_combo: QComboBox | None = None
        self.text_edit: QLineEdit | None = None
        self.image_edit: QLineEdit | None = None
        self.position_combo: QComboBox | None = None
        self.opacity_slider: QSlider | None = None
        self.font_size_spin: QSpinBox | None = None
        self.image_scale_spin: QSpinBox | None = None
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

        group = QGroupBox("水印参数")
        form = QFormLayout(group)
        form.setSpacing(14)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["文字水印", "图片水印"])
        self.type_combo.setCurrentIndex(self.config.get("type_index", 0, int))
        form.addRow("类型", self.type_combo)

        self.text_edit = QLineEdit(self.config.get("text", "HEA Image Toolbox"))
        form.addRow("文字", self.text_edit)

        self.image_edit = QLineEdit(self.config.get("image_path", ""))
        browse_image = QPushButton("选择")
        browse_image.clicked.connect(self._choose_watermark_image)
        image_row = QHBoxLayout()
        image_row.addWidget(self.image_edit)
        image_row.addWidget(browse_image)
        form.addRow("水印图片", image_row)

        self.position_combo = QComboBox()
        self.position_combo.addItems(["右下", "左下", "右上", "左上", "居中", "上中", "下中"])
        saved_position = self.config.get("position", "右下")
        position_index = max(0, self.position_combo.findText(saved_position))
        self.position_combo.setCurrentIndex(position_index)
        form.addRow("位置", self.position_combo)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(5, 100)
        self.opacity_slider.setValue(self.config.get("opacity", 45, int))
        opacity_value = QLabel(str(self.opacity_slider.value()))
        self.opacity_slider.valueChanged.connect(lambda value: opacity_value.setText(str(value)))
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self.opacity_slider)
        opacity_row.addWidget(opacity_value)
        form.addRow("透明度 %", opacity_row)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 300)
        self.font_size_spin.setValue(self.config.get("font_size", 42, int))
        form.addRow("字体大小", self.font_size_spin)

        self.image_scale_spin = QSpinBox()
        self.image_scale_spin.setRange(5, 300)
        self.image_scale_spin.setValue(self.config.get("image_scale", 30, int))
        form.addRow("图片缩放 %", self.image_scale_spin)

        self.output_edit = QLineEdit(self.config.get("output_dir", str(Path.cwd() / "output")))
        browse_output = QPushButton("选择")
        browse_output.clicked.connect(self._choose_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit)
        output_row.addWidget(browse_output)
        form.addRow("保存到", output_row)

        layout.addWidget(group)
        layout.addStretch()
        return panel

    def create_processor(self, files: list[Path]) -> Callable[[Path, Callable[[str], None]], Path]:
        output_dir = Path(self.output_edit.text() if self.output_edit else "output")
        output_dir.mkdir(parents=True, exist_ok=True)
        type_index = self.type_combo.currentIndex() if self.type_combo else 0
        text = self.text_edit.text() if self.text_edit else ""
        watermark_path = Path(self.image_edit.text()) if self.image_edit and self.image_edit.text() else Path()
        position = self.position_combo.currentText() if self.position_combo else "右下"
        opacity = self.opacity_slider.value() if self.opacity_slider else 45
        font_size = self.font_size_spin.value() if self.font_size_spin else 42
        image_scale = self.image_scale_spin.value() if self.image_scale_spin else 30

        self.config.set("output_dir", str(output_dir))
        self.config.set("type_index", type_index)
        self.config.set("text", text)
        self.config.set("image_path", str(watermark_path) if watermark_path else "")
        self.config.set("position", position)
        self.config.set("opacity", opacity)
        self.config.set("font_size", font_size)
        self.config.set("image_scale", image_scale)

        if type_index == 0:
            if not text.strip():
                raise ValueError("文字水印内容不能为空")
            return lambda source, logger: add_text_watermark(source, output_dir, text, position, opacity, font_size, logger)

        if not watermark_path.exists():
            raise ValueError("请选择有效的水印图片")
        return lambda source, logger: add_image_watermark(source, output_dir, watermark_path, position, opacity, image_scale, logger)

    def get_output_dir(self) -> Path | None:
        return Path(self.output_edit.text()) if self.output_edit and self.output_edit.text() else None

    def _choose_watermark_image(self) -> None:
        if not self.image_edit:
            return
        selected, _ = QFileDialog.getOpenFileName(None, "选择水印图片", self.image_edit.text() or str(Path.cwd()), "Images (*.jpg *.jpeg *.png *.webp *.bmp)")
        if selected:
            self.image_edit.setText(selected)

    def _choose_output(self) -> None:
        if not self.output_edit:
            return
        directory = QFileDialog.getExistingDirectory(None, "选择输出目录", self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)
