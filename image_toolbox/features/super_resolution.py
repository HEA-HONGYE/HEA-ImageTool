from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from image_toolbox.core.config import AppConfig
from image_toolbox.core.super_resolution import (
    REALESRGAN_MODELS_BY_NAME,
    ensure_realesrgan_available,
    upscale_with_realesrgan,
)
from image_toolbox.features.base import ToolFeature


class SuperResolutionFeature(ToolFeature):
    key = "super_resolution"
    title = "AI 超分"
    description = "调用本地 Real-ESRGAN 引擎批量放大图片，适合照片、动漫与素材高清化。"

    def __init__(self) -> None:
        self.config = AppConfig(self.key)
        self.model_combo: QComboBox | None = None
        self.scale_combo: QComboBox | None = None
        self.format_combo: QComboBox | None = None
        self.tile_spin: QSpinBox | None = None
        self.gpu_edit: QLineEdit | None = None
        self.threads_edit: QLineEdit | None = None
        self.tta_checkbox: QCheckBox | None = None
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
        hint.setWordWrap(True)
        layout.addWidget(header)
        layout.addWidget(hint)

        group = QGroupBox("超分参数")
        form = QFormLayout(group)
        form.setSpacing(14)

        self.model_combo = QComboBox()
        for model_name, label in REALESRGAN_MODELS_BY_NAME.items():
            self.model_combo.addItem(label, model_name)
        saved_model = self.config.get("model_name", "realesrgan-x4plus")
        model_index = max(0, self.model_combo.findData(saved_model))
        self.model_combo.setCurrentIndex(model_index)
        form.addRow("模型", self.model_combo)

        self.scale_combo = QComboBox()
        self.scale_combo.addItem("2x", 2)
        self.scale_combo.addItem("4x", 4)
        saved_scale = self.config.get("scale", 4, int)
        scale_index = max(0, self.scale_combo.findData(saved_scale))
        self.scale_combo.setCurrentIndex(scale_index)
        form.addRow("倍率", self.scale_combo)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPG", "WEBP"])
        saved_format = self.config.get("format", "PNG")
        self.format_combo.setCurrentIndex(max(0, self.format_combo.findText(saved_format)))
        form.addRow("输出格式", self.format_combo)

        self.tile_spin = QSpinBox()
        self.tile_spin.setRange(0, 2048)
        self.tile_spin.setSingleStep(32)
        self.tile_spin.setValue(self.config.get("tile_size", 0, int))
        form.addRow("Tile / 0 自动", self.tile_spin)

        self.gpu_edit = QLineEdit(self.config.get("gpu_id", "auto"))
        form.addRow("GPU", self.gpu_edit)

        self.threads_edit = QLineEdit(self.config.get("threads", "1:2:2"))
        form.addRow("线程", self.threads_edit)

        self.tta_checkbox = QCheckBox("启用 TTA 增强，速度会更慢")
        self.tta_checkbox.setChecked(self.config.get("use_tta", False, bool))
        form.addRow("增强", self.tta_checkbox)

        self.output_edit = QLineEdit(self.config.get("output_dir", str(Path.cwd() / "output")))
        browse_button = QPushButton("选择")
        browse_button.clicked.connect(self._choose_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit)
        output_row.addWidget(browse_button)
        form.addRow("保存到", output_row)

        note = QLabel("Real-ESRGAN ncnn-vulkan 使用本地素材包，不需要 CUDA 或 PyTorch；如失败，通常需要更新显卡 Vulkan 驱动。")
        note.setObjectName("MutedText")
        note.setWordWrap(True)
        form.addRow("", note)

        layout.addWidget(group)
        layout.addStretch()
        return panel

    def create_processor(self, files: list[Path]) -> Callable[[Path, Callable[[str], None]], Path]:
        ensure_realesrgan_available()

        output_dir = Path(self.output_edit.text() if self.output_edit else "output")
        output_dir.mkdir(parents=True, exist_ok=True)
        model_name = self.model_combo.currentData() if self.model_combo else "realesrgan-x4plus"
        scale = self.scale_combo.currentData() if self.scale_combo else 4
        output_format = self.format_combo.currentText() if self.format_combo else "PNG"
        tile_size = self.tile_spin.value() if self.tile_spin else 0
        gpu_id = self.gpu_edit.text() if self.gpu_edit else "auto"
        threads = self.threads_edit.text() if self.threads_edit else "1:2:2"
        use_tta = self.tta_checkbox.isChecked() if self.tta_checkbox else False

        self.config.set("output_dir", str(output_dir))
        self.config.set("model_name", model_name)
        self.config.set("scale", scale)
        self.config.set("format", output_format)
        self.config.set("tile_size", tile_size)
        self.config.set("gpu_id", gpu_id)
        self.config.set("threads", threads)
        self.config.set("use_tta", use_tta)

        return lambda source, logger: upscale_with_realesrgan(
            source,
            output_dir,
            model_name,
            scale,
            output_format,
            tile_size,
            gpu_id,
            threads,
            use_tta,
            logger,
        )

    def get_output_dir(self) -> Path | None:
        return Path(self.output_edit.text()) if self.output_edit and self.output_edit.text() else None

    def _choose_output(self) -> None:
        if not self.output_edit:
            return
        directory = QFileDialog.getExistingDirectory(None, "选择输出目录", self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)
