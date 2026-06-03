from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QVBoxLayout, QWidget

from image_toolbox.core.config import AppConfig
from image_toolbox.core.image_ops import resize_image
from image_toolbox.features.base import ToolFeature
from image_toolbox.ui.widgets import NoWheelComboBox as QComboBox
from image_toolbox.ui.widgets import NoWheelSpinBox as QSpinBox


class ResizeFeature(ToolFeature):
    key = "resize"
    title = "批量改尺寸"
    description = "按比例或指定宽高批量缩放图片，可保持原始比例。"

    def __init__(self) -> None:
        self.config = AppConfig(self.key)
        self.mode_combo: QComboBox | None = None
        self.scale_slider: QSlider | None = None
        self.width_spin: QSpinBox | None = None
        self.height_spin: QSpinBox | None = None
        self.keep_aspect_checkbox: QCheckBox | None = None
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

        group = QGroupBox("尺寸参数")
        form = QFormLayout(group)
        form.setSpacing(14)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("按比例缩放", "percent")
        self.mode_combo.addItem("按指定宽高缩放", "size")
        self.mode_combo.setCurrentIndex(self.config.get("mode_index", 0, int))
        form.addRow("模式", self.mode_combo)

        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(10, 300)
        self.scale_slider.setValue(self.config.get("scale_percent", 100, int))
        scale_value = QLabel(str(self.scale_slider.value()))
        self.scale_slider.valueChanged.connect(lambda value: scale_value.setText(str(value)))
        scale_row = QHBoxLayout()
        scale_row.addWidget(self.scale_slider)
        scale_row.addWidget(scale_value)
        form.addRow("比例 %", scale_row)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 20000)
        self.width_spin.setValue(self.config.get("width", 1280, int))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 20000)
        self.height_spin.setValue(self.config.get("height", 720, int))
        size_row = QHBoxLayout()
        size_row.addWidget(self.width_spin)
        size_row.addWidget(QLabel("x"))
        size_row.addWidget(self.height_spin)
        form.addRow("宽高", size_row)

        self.keep_aspect_checkbox = QCheckBox("保持原比例")
        self.keep_aspect_checkbox.setChecked(self.config.get("keep_aspect", True, bool))
        form.addRow("比例", self.keep_aspect_checkbox)

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
        mode_index = self.mode_combo.currentIndex() if self.mode_combo else 0
        mode = self.mode_combo.currentData() if self.mode_combo else "percent"
        scale_percent = self.scale_slider.value() if self.scale_slider else 100
        width = self.width_spin.value() if self.width_spin else 1280
        height = self.height_spin.value() if self.height_spin else 720
        keep_aspect = self.keep_aspect_checkbox.isChecked() if self.keep_aspect_checkbox else True

        self.config.set("output_dir", str(output_dir))
        self.config.set("mode_index", mode_index)
        self.config.set("scale_percent", scale_percent)
        self.config.set("width", width)
        self.config.set("height", height)
        self.config.set("keep_aspect", keep_aspect)

        return lambda source, logger: resize_image(source, output_dir, mode, scale_percent, width, height, keep_aspect, logger)

    def get_output_dir(self) -> Path | None:
        return Path(self.output_edit.text()) if self.output_edit and self.output_edit.text() else None

    def _choose_output(self) -> None:
        if not self.output_edit:
            return
        directory = QFileDialog.getExistingDirectory(None, "选择输出目录", self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)
