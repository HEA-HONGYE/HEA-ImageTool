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
    SuperResolutionBatchTask,
    SuperResolutionSettings,
    normalize_output_format,
    read_image_info,
    validate_super_resolution_inputs,
)
from image_toolbox.core.upscale_engines import DEFAULT_ENGINE_MANAGER
from image_toolbox.core.upscale_engines.presets import UPSCALE_PRESETS
from image_toolbox.features.base import ToolFeature


class SuperResolutionFeature(ToolFeature):
    key = "super_resolution"
    title = "AI 超分"
    description = "调用本地超分引擎批量放大图片，适合照片、动漫与素材高清化。"

    def __init__(self) -> None:
        self.config = AppConfig(self.key)
        self.engine_combo: QComboBox | None = None
        self.preset_combo: QComboBox | None = None
        self.model_combo: QComboBox | None = None
        self.scale_combo: QComboBox | None = None
        self.format_combo: QComboBox | None = None
        self.quality_spin: QSpinBox | None = None
        self.tile_spin: QSpinBox | None = None
        self.gpu_edit: QLineEdit | None = None
        self.threads_edit: QLineEdit | None = None
        self.tta_checkbox: QCheckBox | None = None
        self.low_memory_checkbox: QCheckBox | None = None
        self.conflict_combo: QComboBox | None = None
        self.output_edit: QLineEdit | None = None
        self.engine_info_label: QLabel | None = None
        self.size_label: QLabel | None = None
        self.output_info_label: QLabel | None = None
        self._files: list[Path] = []
        self._selected_file: Path | None = None

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

        self.engine_combo = QComboBox()
        for info in DEFAULT_ENGINE_MANAGER.list_engine_info():
            label = info.display_name if info.available else f"{info.display_name}（不可用）"
            self.engine_combo.addItem(label, info.engine_id)
        self.engine_combo.setCurrentIndex(max(0, self.engine_combo.findData(self.config.get("engine_id", "realesrgan"))))
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        form.addRow("引擎", self.engine_combo)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("自定义", "")
        for preset in UPSCALE_PRESETS:
            self.preset_combo.addItem(preset.display_name, preset.preset_id)
        self.preset_combo.currentIndexChanged.connect(self._apply_selected_preset)
        form.addRow("预设", self.preset_combo)

        self.engine_info_label = QLabel("")
        self.engine_info_label.setObjectName("MutedText")
        self.engine_info_label.setWordWrap(True)
        form.addRow("引擎状态", self.engine_info_label)

        self.model_combo = QComboBox()
        form.addRow("模型", self.model_combo)

        self.scale_combo = QComboBox()
        self.scale_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow("倍率", self.scale_combo)

        self.format_combo = QComboBox()
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        form.addRow("输出格式", self.format_combo)

        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(self.config.get("quality", 95, int))
        self.quality_spin.valueChanged.connect(self._refresh_preview)
        form.addRow("JPG / WEBP 质量", self.quality_spin)

        self.tile_spin = QSpinBox()
        self.tile_spin.setRange(0, 2048)
        self.tile_spin.setSingleStep(32)
        self.tile_spin.setValue(self.config.get("tile_size", 0, int))
        self.tile_spin.valueChanged.connect(self._refresh_preview)
        form.addRow("Tile / 0 自动", self.tile_spin)

        self.gpu_edit = QLineEdit(self.config.get("gpu_id", "auto"))
        form.addRow("GPU", self.gpu_edit)

        self.threads_edit = QLineEdit(self.config.get("threads", "1:2:2"))
        form.addRow("线程", self.threads_edit)

        self.tta_checkbox = QCheckBox("启用 TTA 增强，速度会更慢")
        self.tta_checkbox.setChecked(self.config.get("use_tta", False, bool))
        form.addRow("增强", self.tta_checkbox)

        self.low_memory_checkbox = QCheckBox("低显存模式：速度较慢，但更稳定，适合大图或显存较小的电脑。")
        self.low_memory_checkbox.setChecked(self.config.get("low_memory_mode", False, bool))
        self.low_memory_checkbox.stateChanged.connect(self._refresh_preview)
        form.addRow("稳定性", self.low_memory_checkbox)

        self.conflict_combo = QComboBox()
        self.conflict_combo.addItem("自动重命名", "rename")
        self.conflict_combo.addItem("跳过", "skip")
        self.conflict_combo.addItem("覆盖", "overwrite")
        self.conflict_combo.setCurrentIndex(max(0, self.conflict_combo.findData(self.config.get("conflict_strategy", "rename"))))
        form.addRow("文件已存在", self.conflict_combo)

        self.output_edit = QLineEdit(self.config.get("output_dir", str(Path.cwd() / "output")))
        browse_button = QPushButton("选择")
        browse_button.clicked.connect(self._choose_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit)
        output_row.addWidget(browse_button)
        form.addRow("保存到", output_row)

        layout.addWidget(group)

        info_group = QGroupBox("预计输出信息")
        info_layout = QVBoxLayout(info_group)
        self.size_label = QLabel("请在右侧任务队列添加图片。")
        self.size_label.setObjectName("MutedText")
        self.size_label.setWordWrap(True)
        self.output_info_label = QLabel("文件大小受图片内容、格式和质量影响较大，仅供参考。")
        self.output_info_label.setObjectName("MutedText")
        self.output_info_label.setWordWrap(True)
        info_layout.addWidget(self.size_label)
        info_layout.addWidget(self.output_info_label)
        layout.addWidget(info_group)
        layout.addStretch()
        self._refresh_engine_options()
        return panel

    def create_processor(self, files: list[Path]) -> Callable[[Path, Callable[[str], None]], Path]:
        raise NotImplementedError("AI 超分使用专用任务执行。")

    def create_task(self, files: list[Path]) -> SuperResolutionBatchTask:
        settings = self._collect_settings()
        validate_super_resolution_inputs(files, settings)
        self._save_settings(settings)
        return SuperResolutionBatchTask(files, settings)

    def _collect_settings(self) -> SuperResolutionSettings:
        output_dir = Path(self.output_edit.text() if self.output_edit else "output")
        output_format = self.format_combo.currentData() if self.format_combo else "original"
        return SuperResolutionSettings(
            engine_id=self.engine_combo.currentData() if self.engine_combo else "realesrgan",
            output_dir=output_dir,
            model_name=self.model_combo.currentData() if self.model_combo else "realesrgan-x4plus",
            scale=self.scale_combo.currentData() if self.scale_combo else 4,
            output_format=output_format,
            keep_original_format=output_format == "original",
            quality=self.quality_spin.value() if self.quality_spin else 95,
            tile_mode="manual" if self.tile_spin and self.tile_spin.value() > 0 else "auto",
            tile_size=self.tile_spin.value() if self.tile_spin else 0,
            gpu_id=self.gpu_edit.text() if self.gpu_edit else "auto",
            threads=self.threads_edit.text() if self.threads_edit else "1:2:2",
            use_tta=self.tta_checkbox.isChecked() if self.tta_checkbox else False,
            low_memory_mode=self.low_memory_checkbox.isChecked() if self.low_memory_checkbox else False,
            conflict_strategy=self.conflict_combo.currentData() if self.conflict_combo else "rename",
        )

    def _save_settings(self, settings: SuperResolutionSettings) -> None:
        self.config.set("engine_id", settings.engine_id)
        self.config.set("output_dir", str(settings.output_dir))
        self.config.set("model_name", settings.model_name)
        self.config.set("scale", settings.scale)
        self.config.set("format", settings.output_format)
        self.config.set("quality", settings.quality)
        self.config.set("tile_size", settings.tile_size)
        self.config.set("gpu_id", settings.gpu_id)
        self.config.set("threads", settings.threads)
        self.config.set("use_tta", settings.use_tta)
        self.config.set("low_memory_mode", settings.low_memory_mode)
        self.config.set("conflict_strategy", settings.conflict_strategy)

    def update_file_context(self, files: list[Path], selected_file: Path | None, logger: Callable[[str], None] | None = None) -> None:
        self._files = files
        self._selected_file = selected_file
        self._update_preview(logger)

    def get_output_dir(self) -> Path | None:
        return Path(self.output_edit.text()) if self.output_edit and self.output_edit.text() else None

    def _choose_output(self) -> None:
        if not self.output_edit:
            return
        directory = QFileDialog.getExistingDirectory(None, "选择输出目录", self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)

    def _on_engine_changed(self, *_args: object) -> None:
        self._refresh_engine_options()
        self._update_preview()

    def _refresh_engine_options(self) -> None:
        if not self.engine_combo or not self.model_combo or not self.scale_combo or not self.format_combo:
            return
        engine_id = self.engine_combo.currentData() or "realesrgan"
        engine = DEFAULT_ENGINE_MANAGER.get_engine(engine_id)
        info = engine.get_info()

        saved_model = self.config.get("model_name", engine.get_model_info()[0].name)
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for model in engine.get_model_info():
            self.model_combo.addItem(model.display_name, model.name)
        self.model_combo.setCurrentIndex(max(0, self.model_combo.findData(saved_model)))
        self.model_combo.blockSignals(False)

        saved_scale = self.config.get("scale", engine.supported_scales[-1], int)
        self.scale_combo.blockSignals(True)
        self.scale_combo.clear()
        for scale in engine.supported_scales:
            self.scale_combo.addItem(f"{scale}x", scale)
        self.scale_combo.setCurrentIndex(max(0, self.scale_combo.findData(saved_scale)))
        self.scale_combo.blockSignals(False)

        saved_format = self.config.get("format", "original")
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        self.format_combo.addItem("保留原格式", "original")
        for fmt in engine.supported_formats:
            self.format_combo.addItem(fmt.upper(), fmt)
        self.format_combo.setCurrentIndex(max(0, self.format_combo.findData(saved_format)))
        self.format_combo.blockSignals(False)

        if self.tile_spin:
            self.tile_spin.setEnabled(engine.supports_tile)
        if self.low_memory_checkbox:
            self.low_memory_checkbox.setEnabled(engine.supports_tile)
        status = "可用" if info.available else f"不可用：{info.unavailable_reason}"
        if self.engine_info_label:
            self.engine_info_label.setText(f"{info.display_name}：{status}\n{info.description}")
        self._on_format_changed()

    def _apply_selected_preset(self, *_args: object) -> None:
        if not self.preset_combo or not self.preset_combo.currentData():
            return
        preset = next((item for item in UPSCALE_PRESETS if item.preset_id == self.preset_combo.currentData()), None)
        if not preset:
            return
        if self.engine_combo:
            self.engine_combo.setCurrentIndex(max(0, self.engine_combo.findData(preset.engine_id)))
        self._refresh_engine_options()
        if self.model_combo:
            self.model_combo.setCurrentIndex(max(0, self.model_combo.findData(preset.model_name)))
        if self.scale_combo:
            self.scale_combo.setCurrentIndex(max(0, self.scale_combo.findData(preset.scale)))
        if self.format_combo:
            self.format_combo.setCurrentIndex(max(0, self.format_combo.findData(preset.output_format)))
        if self.low_memory_checkbox:
            self.low_memory_checkbox.setChecked(preset.low_memory_mode)
        if self.tile_spin:
            self.tile_spin.setValue(preset.tile_size if preset.tile_mode == "manual" else 0)
        self._update_preview()

    def _on_format_changed(self, *_args: object) -> None:
        selected = self.format_combo.currentData() if self.format_combo else "original"
        if self.quality_spin:
            self.quality_spin.setEnabled(selected in {"original", "jpg", "webp"})
        self._update_preview()

    def _refresh_preview(self, *_args: object) -> None:
        self._update_preview()

    def _update_preview(self, logger: Callable[[str], None] | None = None) -> None:
        if logger is not None and not callable(logger):
            logger = None
        if not self.size_label or not self.output_info_label:
            return
        if not self._files:
            self.size_label.setText("请在右侧任务队列添加图片。")
            self.output_info_label.setText("文件大小受图片内容、格式和质量影响较大，仅供参考。")
            return

        selected = self._selected_file or self._files[0]
        scale = self.scale_combo.currentData() if self.scale_combo else 4
        count_text = f"已选择 {len(self._files)} 张图片。" if len(self._files) > 1 else "已选择 1 张图片。"
        try:
            width, height, image_format = read_image_info(selected)
            output_width = width * int(scale)
            output_height = height * int(scale)
            format_text = self._preview_format_text(selected)
            tile_text = ""
            if self.low_memory_checkbox and self.low_memory_checkbox.isChecked():
                engine = DEFAULT_ENGINE_MANAGER.get_engine(self.engine_combo.currentData() if self.engine_combo else "realesrgan")
                tile_text = f"\n低显存模式已开启，将使用更保守的 Tile：{engine.get_default_tile(True)}。"
            self.size_label.setText(
                f"{count_text}\n当前参考图片：{selected.name}\n原图尺寸：{width} × {height}（{image_format}）\n当前倍率：{scale}x\n预计输出尺寸：{output_width} × {output_height}{tile_text}"
            )
            self.output_info_label.setText(
                f"预计输出尺寸：{output_width} × {output_height}\n输出格式：{format_text}\n文件大小受图片内容、格式和质量影响较大，仅供参考。"
            )
        except Exception as exc:
            self.size_label.setText(f"{count_text}\n当前参考图片：{selected.name}\n图片读取失败，无法预估尺寸。")
            self.output_info_label.setText("文件大小受图片内容、格式和质量影响较大，仅供参考。")
            if logger:
                logger(f"图片读取失败：{selected.name}，原因：{exc}")

    def _preview_format_text(self, selected: Path) -> str:
        selected_format = self.format_combo.currentData() if self.format_combo else "original"
        engine_id = self.engine_combo.currentData() if self.engine_combo else "realesrgan"
        output_format = normalize_output_format(selected, selected_format, engine_id)
        if selected_format == "original":
            return f"保留原格式（预计 {output_format.upper()}）"
        if output_format in {"jpg", "webp"} and self.quality_spin:
            return f"{output_format.upper()}，质量 {self.quality_spin.value()}（仅供参考）"
        return output_format.upper()
