from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from image_toolbox.core.config import AppConfig
from image_toolbox.core.engine_settings import get_engine_settings_store, is_engine_enabled, is_model_enabled
from image_toolbox.core.ffmpeg_tools import media_fps, probe_media
from image_toolbox.core.media_tasks import VideoMediaTask, VideoProcessSettings, list_rife_models
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
from image_toolbox.ui.widgets import NoWheelComboBox as QComboBox
from image_toolbox.ui.widgets import NoWheelDoubleSpinBox as QDoubleSpinBox
from image_toolbox.ui.widgets import NoWheelSpinBox as QSpinBox


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
ANIMATED_EXTENSIONS = {".gif", ".apng"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


class SuperResolutionFeature(ToolFeature):
    key = "super_resolution"
    title = "智能媒体增强"
    description = "统一处理图片超分、动图增强与视频超分/AI 插帧。v3.3.8 先开放图片增强，动图和视频参数预留。"

    def __init__(self) -> None:
        self.config = AppConfig(self.key)
        self.engine_settings_store = get_engine_settings_store()
        self.file_table: QTableWidget | None = None
        self.file_count_label: QLabel | None = None
        self.mode_combo: QComboBox | None = None
        self.engine_combo: QComboBox | None = None
        self.preset_combo: QComboBox | None = None
        self.model_combo: QComboBox | None = None
        self.scale_combo: QComboBox | None = None
        self.format_combo: QComboBox | None = None
        self.noise_combo: QComboBox | None = None
        self.syncgap_combo: QComboBox | None = None
        self.quality_spin: QSpinBox | None = None
        self.tile_spin: QSpinBox | None = None
        self.gpu_edit: QLineEdit | None = None
        self.threads_edit: QLineEdit | None = None
        self.tta_checkbox: QCheckBox | None = None
        self.low_memory_checkbox: QCheckBox | None = None
        self.upscale_enabled_checkbox: QCheckBox | None = None
        self.conflict_combo: QComboBox | None = None
        self.output_edit: QLineEdit | None = None
        self.engine_info_label: QLabel | None = None
        self.size_label: QLabel | None = None
        self.output_info_label: QLabel | None = None
        self.animated_hint_label: QLabel | None = None
        self.video_hint_label: QLabel | None = None
        self.keep_audio_checkbox: QCheckBox | None = None
        self.keep_temp_checkbox: QCheckBox | None = None
        self.video_fps_spin: QDoubleSpinBox | None = None
        self.interpolation_enabled_checkbox: QCheckBox | None = None
        self.interpolation_engine_combo: QComboBox | None = None
        self.interpolation_scale_combo: QComboBox | None = None
        self.interpolation_model_combo: QComboBox | None = None
        self.interpolation_gpu_edit: QLineEdit | None = None
        self.interpolation_tta_checkbox: QCheckBox | None = None
        self.interpolation_preview_label: QLabel | None = None
        self._files: list[Path] = []
        self._statuses: list[str] = []
        self._selected_file: Path | None = None

    def build_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel(self.title)
        title.setObjectName("PanelTitle")
        hint = QLabel(self.description)
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        title_block.addWidget(title)
        title_block.addWidget(hint)
        header.addLayout(title_block, 1)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("图片增强", "image")
        self.mode_combo.addItem("动图增强（预留）", "animated")
        self.mode_combo.addItem("视频增强与 AI 插帧（预留）", "video")
        header.addWidget(QLabel("任务类型"))
        header.addWidget(self.mode_combo)
        layout.addLayout(header)

        layout.addWidget(self._build_file_area(), 3)
        layout.addLayout(self._build_toolbar())

        settings_row = QHBoxLayout()
        settings_row.setSpacing(10)
        settings_row.addWidget(self._build_resolution_group(), 1)
        settings_row.addWidget(self._build_media_group(), 2)
        settings_row.addWidget(self._build_output_group(), 3)
        layout.addLayout(settings_row)

        enhancement_row = QHBoxLayout()
        enhancement_row.setSpacing(10)
        enhancement_row.addWidget(self._build_upscale_group(), 3)
        enhancement_row.addWidget(self._build_interpolation_group(), 1)
        layout.addLayout(enhancement_row)

        layout.addWidget(self._build_preview_group())
        self.refresh_from_engine_settings()
        return panel

    def _build_file_area(self) -> QWidget:
        group = QGroupBox("文件列表")
        layout = QVBoxLayout(group)
        self.file_table = QTableWidget(0, 6)
        self.file_table.setHorizontalHeaderLabels(["文件名", "类型", "状态", "完整路径", "原始尺寸", "预计输出尺寸"])
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.file_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.file_table.currentCellChanged.connect(lambda row, *_args: self._select_row(row))
        layout.addWidget(self.file_table)
        return group

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.file_count_label = QLabel("文件数量：0")
        self.file_count_label.setObjectName("CardTitle")
        add_button = QPushButton("添加文件")
        remove_button = QPushButton("删除选中")
        clear_button = QPushButton("清空")
        open_output_button = QPushButton("打开输出目录")
        add_button.clicked.connect(self.choose_files)
        remove_button.clicked.connect(self.remove_selected_file)
        clear_button.clicked.connect(self.clear_files)
        open_output_button.clicked.connect(self._open_output_from_page)
        for button in [remove_button, clear_button, open_output_button]:
            button.setObjectName("GhostButton")
        row.addWidget(self.file_count_label)
        row.addWidget(add_button)
        row.addWidget(remove_button)
        row.addWidget(clear_button)
        row.addSpacing(16)
        row.addWidget(QLabel("快捷预设"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("自定义", "")
        for preset in UPSCALE_PRESETS:
            self.preset_combo.addItem(preset.display_name, preset.preset_id)
        self.preset_combo.currentIndexChanged.connect(self._apply_selected_preset)
        row.addWidget(self.preset_combo, 1)
        row.addWidget(QLabel("引擎"))
        self.engine_combo = QComboBox()
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        row.addWidget(self.engine_combo, 1)
        row.addStretch()
        row.addWidget(open_output_button)
        return row

    def _build_resolution_group(self) -> QWidget:
        group = QGroupBox("尺寸与分辨率")
        form = QFormLayout(group)
        self.scale_combo = QComboBox()
        self.scale_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow("放大倍率", self.scale_combo)
        self.low_memory_checkbox = QCheckBox("低显存模式：速度较慢，但更稳定")
        self.low_memory_checkbox.stateChanged.connect(self._refresh_preview)
        form.addRow("稳定性", self.low_memory_checkbox)
        apply_all = QCheckBox("应用到全部")
        apply_all.setChecked(True)
        form.addRow("应用范围", apply_all)
        return group

    def _build_media_group(self) -> QWidget:
        group = QGroupBox("图片 / 动图 / 视频参数")
        form = QFormLayout(group)
        self.format_combo = QComboBox()
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        form.addRow("静态图片保存为", self.format_combo)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(self.config.get("quality", 95, int))
        self.quality_spin.valueChanged.connect(self._refresh_preview)
        form.addRow("图片质量", self.quality_spin)
        self.video_fps_spin = QDoubleSpinBox()
        self.video_fps_spin.setRange(0, 240)
        self.video_fps_spin.setDecimals(3)
        self.video_fps_spin.setSingleStep(1)
        self.video_fps_spin.setValue(self.config.get("video_output_fps", 0.0, float))
        self.video_fps_spin.setToolTip("0 表示自动：仅超分保持原 FPS，插帧按倍率提升 FPS。")
        self.video_fps_spin.valueChanged.connect(self._refresh_preview)
        form.addRow("视频输出 FPS", self.video_fps_spin)
        self.keep_audio_checkbox = QCheckBox("保留原音频")
        self.keep_audio_checkbox.setChecked(self.config.get("keep_audio", True, bool))
        form.addRow("音频", self.keep_audio_checkbox)
        self.keep_temp_checkbox = QCheckBox("保留临时帧目录（调试用）")
        self.keep_temp_checkbox.setChecked(self.config.get("keep_temp", False, bool))
        form.addRow("临时文件", self.keep_temp_checkbox)
        self.animated_hint_label = QLabel("动图增强、逐帧超分和帧补偿将在后续版本开放。")
        self.animated_hint_label.setObjectName("MutedText")
        self.video_hint_label = QLabel("视频任务已支持基础拆帧、图片引擎逐帧超分、RIFE 插帧和 MP4 合成。")
        self.video_hint_label.setObjectName("MutedText")
        self.animated_hint_label.setWordWrap(True)
        self.video_hint_label.setWordWrap(True)
        form.addRow("动图", self.animated_hint_label)
        form.addRow("视频", self.video_hint_label)
        return group

    def _build_output_group(self) -> QWidget:
        group = QGroupBox("输出文件夹")
        form = QFormLayout(group)
        self.output_edit = QLineEdit(self.config.get("output_dir", str(Path.cwd() / "output")))
        browse_button = QPushButton("选择")
        browse_button.clicked.connect(self._choose_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit)
        output_row.addWidget(browse_button)
        form.addRow("输出到", output_row)
        self.conflict_combo = QComboBox()
        self.conflict_combo.addItem("自动重命名", "rename")
        self.conflict_combo.addItem("跳过", "skip")
        self.conflict_combo.addItem("覆盖", "overwrite")
        self.conflict_combo.setCurrentIndex(max(0, self.conflict_combo.findData(self.config.get("conflict_strategy", "rename"))))
        form.addRow("文件已存在", self.conflict_combo)
        keep_name = QCheckBox("保留原文件名")
        keep_name.setEnabled(False)
        auto_folder = QCheckBox("自动创建输出文件夹")
        auto_folder.setChecked(True)
        form.addRow("命名", keep_name)
        form.addRow("目录", auto_folder)
        return group

    def _build_upscale_group(self) -> QWidget:
        group = QGroupBox("AI 超分与增强参数")
        form = QFormLayout(group)
        self.upscale_enabled_checkbox = QCheckBox("启用超分 / 图片增强")
        self.upscale_enabled_checkbox.setChecked(self.config.get("upscale_enabled", True, bool))
        self.upscale_enabled_checkbox.stateChanged.connect(self._refresh_preview)
        form.addRow("开关", self.upscale_enabled_checkbox)
        self.engine_info_label = QLabel("")
        self.engine_info_label.setObjectName("MutedText")
        self.engine_info_label.setWordWrap(True)
        form.addRow("引擎状态", self.engine_info_label)
        self.model_combo = QComboBox()
        form.addRow("模型", self.model_combo)
        self.noise_combo = QComboBox()
        form.addRow("降噪等级", self.noise_combo)
        self.syncgap_combo = QComboBox()
        form.addRow("SyncGap", self.syncgap_combo)
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
        return group

    def _build_interpolation_group(self) -> QWidget:
        group = QGroupBox("AI 插帧")
        form = QFormLayout(group)
        self.interpolation_enabled_checkbox = QCheckBox("启用插帧")
        self.interpolation_enabled_checkbox.setChecked(self.config.get("interpolation_enabled", False, bool))
        self.interpolation_enabled_checkbox.stateChanged.connect(self._on_interpolation_changed)
        form.addRow("开关", self.interpolation_enabled_checkbox)
        self.interpolation_engine_combo = QComboBox()
        self.interpolation_engine_combo.addItem("RIFE", "rife")
        form.addRow("插帧引擎", self.interpolation_engine_combo)
        self.interpolation_scale_combo = QComboBox()
        self.interpolation_scale_combo.addItem("2x", 2)
        self.interpolation_scale_combo.addItem("4x", 4)
        self.interpolation_scale_combo.setCurrentIndex(max(0, self.interpolation_scale_combo.findData(self.config.get("interpolation_scale", 2, int))))
        self.interpolation_scale_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow("插帧倍率", self.interpolation_scale_combo)
        self.interpolation_model_combo = QComboBox()
        self._refresh_rife_models()
        form.addRow("模型", self.interpolation_model_combo)
        self.interpolation_gpu_edit = QLineEdit(self.config.get("interpolation_gpu_id", "auto"))
        form.addRow("GPU ID", self.interpolation_gpu_edit)
        self.interpolation_tta_checkbox = QCheckBox("启用 TTA（如果当前 RIFE 版本支持）")
        self.interpolation_tta_checkbox.setChecked(self.config.get("interpolation_tta", False, bool))
        form.addRow("TTA", self.interpolation_tta_checkbox)
        self.interpolation_preview_label = QLabel("输出 FPS：自动")
        self.interpolation_preview_label.setObjectName("MutedText")
        self.interpolation_preview_label.setWordWrap(True)
        form.addRow("预览", self.interpolation_preview_label)
        self._on_interpolation_changed()
        return group

    def _refresh_rife_models(self) -> None:
        if not self.interpolation_model_combo:
            return
        saved_model = self.config.get("interpolation_model", "", str)
        self.interpolation_model_combo.blockSignals(True)
        self.interpolation_model_combo.clear()
        models = list_rife_models()
        if models:
            for model in models:
                self.interpolation_model_combo.addItem(model or "默认模型目录", model)
            self.interpolation_model_combo.setCurrentIndex(max(0, self.interpolation_model_combo.findData(saved_model)))
        else:
            self.interpolation_model_combo.addItem("未导入 RIFE 模型", "")
        self.interpolation_model_combo.blockSignals(False)

    def _on_interpolation_changed(self, *_args: object) -> None:
        enabled = self.interpolation_enabled_checkbox.isChecked() if self.interpolation_enabled_checkbox else False
        for widget in [
            self.interpolation_engine_combo,
            self.interpolation_scale_combo,
            self.interpolation_model_combo,
            self.interpolation_gpu_edit,
            self.interpolation_tta_checkbox,
        ]:
            if widget:
                widget.setEnabled(enabled)
        self._refresh_preview()

    def _build_preview_group(self) -> QWidget:
        group = QGroupBox("预计输出信息")
        layout = QVBoxLayout(group)
        self.size_label = QLabel("请添加文件。")
        self.size_label.setObjectName("MutedText")
        self.size_label.setWordWrap(True)
        self.output_info_label = QLabel("文件大小受图片内容、格式和质量影响较大，仅供参考。")
        self.output_info_label.setObjectName("MutedText")
        self.output_info_label.setWordWrap(True)
        layout.addWidget(self.size_label)
        layout.addWidget(self.output_info_label)
        return group

    def choose_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            None,
            "选择媒体文件",
            str(Path.cwd()),
            "Media Files (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.gif *.apng *.mp4 *.mov *.mkv *.avi *.webm *.m4v)",
        )
        self.add_files([Path(item) for item in selected])

    def add_files(self, paths: list[Path]) -> None:
        existing = {path.resolve() for path in self._files}
        for path in paths:
            if not path.exists() or path.resolve() in existing:
                continue
            if self._media_type(path) == "未知":
                continue
            self._files.append(path)
            self._statuses.append("待处理")
            existing.add(path.resolve())
        self._refresh_file_table()

    def clear_files(self) -> None:
        self._files.clear()
        self._statuses.clear()
        self._selected_file = None
        self._refresh_file_table()

    def remove_selected_file(self) -> None:
        if not self.file_table:
            return
        row = self.file_table.currentRow()
        if row < 0 or row >= len(self._files):
            return
        del self._files[row]
        del self._statuses[row]
        self._selected_file = self._files[0] if self._files else None
        self._refresh_file_table()

    def get_workbench_files(self) -> list[Path]:
        return list(self._files)

    def reset_statuses(self) -> None:
        for index in range(len(self._statuses)):
            self.set_file_status(index, "待处理")

    def set_file_status(self, index: int, status: str) -> None:
        if 0 <= index < len(self._statuses):
            self._statuses[index] = status
            self._refresh_file_table(keep_selection=True)

    def _refresh_file_table(self, keep_selection: bool = False) -> None:
        if not self.file_table:
            return
        current = self.file_table.currentRow() if keep_selection else 0
        self.file_table.setRowCount(0)
        scale = self.scale_combo.currentData() if self.scale_combo else 4
        for row, path in enumerate(self._files):
            self.file_table.insertRow(row)
            media_type = self._media_type(path)
            original_size = self._read_size_text(path)
            output_size = self._output_size_text(path, scale)
            values = [path.name, media_type, self._statuses[row], str(path), original_size, output_size]
            for col, value in enumerate(values):
                self.file_table.setItem(row, col, QTableWidgetItem(value))
        self.file_table.resizeColumnsToContents()
        if self._files:
            self.file_table.setCurrentCell(max(0, min(current, len(self._files) - 1)), 0)
        if self.file_count_label:
            self.file_count_label.setText(f"文件数量：{len(self._files)}")
        self._selected_file = self._files[self.file_table.currentRow()] if self._files and self.file_table.currentRow() >= 0 else (self._files[0] if self._files else None)
        self._update_preview()

    def _select_row(self, row: int) -> None:
        if 0 <= row < len(self._files):
            self._selected_file = self._files[row]
        else:
            self._selected_file = self._files[0] if self._files else None
        self._update_preview()

    def refresh_from_engine_settings(self) -> None:
        if not self.engine_combo:
            return
        current_engine = self.engine_combo.currentData() or self.engine_settings_store.global_settings.default_image_engine or self.config.get("engine_id", "realesrgan")
        self.engine_combo.blockSignals(True)
        self.engine_combo.clear()
        for engine in DEFAULT_ENGINE_MANAGER.list_enabled_engines():
            info = engine.get_info()
            label = info.display_name if info.available else f"{info.display_name}（不可用）"
            self.engine_combo.addItem(label, info.engine_id)
        index = self.engine_combo.findData(current_engine)
        self.engine_combo.setCurrentIndex(index if index >= 0 else 0)
        self.engine_combo.blockSignals(False)
        self._refresh_engine_options()

    def create_processor(self, files: list[Path]) -> Callable[[Path, Callable[[str], None]], Path]:
        raise NotImplementedError("智能媒体增强使用专用任务执行。")

    def create_task(self, files: list[Path]) -> SuperResolutionBatchTask:
        actual_files = self.get_workbench_files() or files
        image_files = [path for path in actual_files if self._media_type(path) == "图片"]
        video_files = [path for path in actual_files if self._media_type(path) == "视频"]
        animated_files = [path for path in actual_files if self._media_type(path) == "动图"]
        if animated_files:
            names = "、".join(path.name for path in animated_files[:3])
            raise ValueError(f"动图流程仍在预留阶段，暂不执行：{names}")
        if image_files and video_files:
            raise ValueError("请分开执行图片任务和视频任务，当前版本暂不支持混合队列。")
        if video_files:
            settings = self._collect_video_settings()
            self._save_video_settings(settings)
            return VideoMediaTask(video_files, settings)
        if self.upscale_enabled_checkbox and not self.upscale_enabled_checkbox.isChecked():
            raise ValueError("图片任务需要启用超分 / 图片增强。")
        settings = self._collect_settings()
        validate_super_resolution_inputs(actual_files, settings)
        self._save_settings(settings)
        return SuperResolutionBatchTask(actual_files, settings)

    def _collect_video_settings(self) -> VideoProcessSettings:
        upscale_settings = self._collect_settings()
        frame_upscale_settings = SuperResolutionSettings(
            engine_id=upscale_settings.engine_id,
            output_dir=upscale_settings.output_dir,
            model_name=upscale_settings.model_name,
            scale=upscale_settings.scale,
            output_format="png",
            keep_original_format=False,
            quality=95,
            tile_mode=upscale_settings.tile_mode,
            tile_size=upscale_settings.tile_size,
            gpu_id=upscale_settings.gpu_id,
            threads=upscale_settings.threads,
            use_tta=upscale_settings.use_tta,
            low_memory_mode=upscale_settings.low_memory_mode,
            conflict_strategy="overwrite",
            noise_level=upscale_settings.noise_level,
            syncgap_mode=upscale_settings.syncgap_mode,
        )
        interpolation_enabled = self.interpolation_enabled_checkbox.isChecked() if self.interpolation_enabled_checkbox else False
        upscale_enabled = self.upscale_enabled_checkbox.isChecked() if self.upscale_enabled_checkbox else True
        if not upscale_enabled and not interpolation_enabled:
            raise ValueError("请至少启用超分或插帧。")
        return VideoProcessSettings(
            output_dir=upscale_settings.output_dir,
            output_format="mp4",
            keep_audio=self.keep_audio_checkbox.isChecked() if self.keep_audio_checkbox else True,
            keep_temp=self.keep_temp_checkbox.isChecked() if self.keep_temp_checkbox else False,
            upscale_enabled=upscale_enabled,
            interpolation_enabled=interpolation_enabled,
            interpolation_engine=self.interpolation_engine_combo.currentData() if self.interpolation_engine_combo else "rife",
            interpolation_scale=self.interpolation_scale_combo.currentData() if self.interpolation_scale_combo else 2,
            interpolation_model=self.interpolation_model_combo.currentData() if self.interpolation_model_combo else "",
            interpolation_gpu_id=self.interpolation_gpu_edit.text() if self.interpolation_gpu_edit else "auto",
            interpolation_tta=self.interpolation_tta_checkbox.isChecked() if self.interpolation_tta_checkbox else False,
            output_fps=self.video_fps_spin.value() if self.video_fps_spin else 0.0,
            conflict_strategy=self.conflict_combo.currentData() if self.conflict_combo else "rename",
            upscale_settings=frame_upscale_settings,
        )

    def _collect_settings(self) -> SuperResolutionSettings:
        output_dir = Path(self.output_edit.text() if self.output_edit else "output")
        output_format = self.format_combo.currentData() if self.format_combo else "original"
        noise_level = self.noise_combo.currentData() if self.noise_combo else 0
        syncgap_mode = self.syncgap_combo.currentData() if self.syncgap_combo else 2
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
            noise_level=0 if noise_level is None else noise_level,
            syncgap_mode=2 if syncgap_mode is None else syncgap_mode,
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
        self.config.set("noise_level", settings.noise_level)
        self.config.set("syncgap_mode", settings.syncgap_mode)

    def _save_video_settings(self, settings: VideoProcessSettings) -> None:
        if settings.upscale_settings:
            self._save_settings(settings.upscale_settings)
        self.config.set("upscale_enabled", settings.upscale_enabled)
        self.config.set("keep_audio", settings.keep_audio)
        self.config.set("keep_temp", settings.keep_temp)
        self.config.set("interpolation_enabled", settings.interpolation_enabled)
        self.config.set("interpolation_scale", settings.interpolation_scale)
        self.config.set("interpolation_model", settings.interpolation_model)
        self.config.set("interpolation_gpu_id", settings.interpolation_gpu_id)
        self.config.set("interpolation_tta", settings.interpolation_tta)
        self.config.set("video_output_fps", settings.output_fps)

    def update_file_context(self, files: list[Path], selected_file: Path | None, logger: Callable[[str], None] | None = None) -> None:
        if not self._files and files:
            self.add_files(files)
        self._update_preview(logger)

    def get_output_dir(self) -> Path | None:
        return Path(self.output_edit.text()) if self.output_edit and self.output_edit.text() else None

    def _choose_output(self) -> None:
        if not self.output_edit:
            return
        directory = QFileDialog.getExistingDirectory(None, "选择输出目录", self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)

    def _open_output_from_page(self) -> None:
        output_dir = self.get_output_dir() or Path.cwd() / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_dir.resolve())))

    def _on_engine_changed(self, *_args: object) -> None:
        self._refresh_engine_options()
        self._refresh_file_table(keep_selection=True)

    def _refresh_engine_options(self) -> None:
        if not self.engine_combo or not self.model_combo or not self.scale_combo or not self.format_combo:
            return
        if self.engine_combo.count() == 0:
            if self.engine_info_label:
                self.engine_info_label.setText("没有启用的增强引擎，请到“引擎设置”中启用。")
            return
        engine_id = self.engine_combo.currentData() or "realesrgan"
        engine = DEFAULT_ENGINE_MANAGER.get_engine(engine_id)
        engine_settings = self.engine_settings_store.get_engine(engine_id)
        info = engine.get_info()

        models = [model for model in engine.get_model_info() if is_model_enabled(engine_id, model.name)]
        saved_model = engine_settings.default_model or self.config.get("model_name", models[0].name if models else "")
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for model in models:
            self.model_combo.addItem(model.display_name, model.name)
        self.model_combo.setCurrentIndex(max(0, self.model_combo.findData(saved_model)))
        self.model_combo.blockSignals(False)

        saved_scale = engine_settings.default_scale or self.config.get("scale", engine.supported_scales[-1], int)
        self.scale_combo.blockSignals(True)
        self.scale_combo.clear()
        for scale in engine.supported_scales:
            self.scale_combo.addItem(f"{scale}x", scale)
        self.scale_combo.setCurrentIndex(max(0, self.scale_combo.findData(saved_scale)))
        self.scale_combo.blockSignals(False)

        saved_format = engine_settings.default_output_format or self.config.get("format", "original")
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        self.format_combo.addItem("保留原格式", "original")
        for fmt in engine.supported_formats:
            self.format_combo.addItem(fmt.upper(), fmt)
        self.format_combo.setCurrentIndex(max(0, self.format_combo.findData(saved_format)))
        self.format_combo.blockSignals(False)

        if self.tile_spin:
            self.tile_spin.setEnabled(engine.supports_tile)
            self.tile_spin.setValue(engine_settings.default_tile)
        if self.low_memory_checkbox:
            self.low_memory_checkbox.setEnabled(engine.supports_tile)
            self.low_memory_checkbox.setChecked(engine_settings.low_memory_default)
        if self.tta_checkbox:
            self.tta_checkbox.setChecked(bool(engine_settings.extra_params.get("use_tta", False)))
        if self.gpu_edit:
            self.gpu_edit.setText(str(engine_settings.extra_params.get("gpu_id", self.engine_settings_store.global_settings.gpu_id)))
        if self.noise_combo:
            self.noise_combo.blockSignals(True)
            self.noise_combo.clear()
            noise_options = engine.get_noise_options()
            for option in noise_options:
                self.noise_combo.addItem(option.label, option.value)
            saved_noise = engine_settings.default_noise_level if engine.supports_noise else 0
            self.noise_combo.setCurrentIndex(max(0, self.noise_combo.findData(saved_noise)))
            self.noise_combo.setEnabled(bool(noise_options) and getattr(engine, "supports_noise", False))
            self.noise_combo.blockSignals(False)
        if self.syncgap_combo:
            self.syncgap_combo.blockSignals(True)
            self.syncgap_combo.clear()
            syncgap_options = engine.get_syncgap_options()
            for option in syncgap_options:
                self.syncgap_combo.addItem(option.label, option.value)
            saved_syncgap = engine_settings.syncgap_mode if engine.supports_syncgap else 2
            self.syncgap_combo.setCurrentIndex(max(0, self.syncgap_combo.findData(saved_syncgap)))
            self.syncgap_combo.setEnabled(bool(syncgap_options) and getattr(engine, "supports_syncgap", False))
            self.syncgap_combo.blockSignals(False)
        status = "可用" if info.available else f"不可用：{info.unavailable_reason}"
        if not is_engine_enabled(engine_id):
            status = "已禁用"
        elif not models:
            status = "当前引擎没有可用模型，请到引擎设置中迁移或导入模型"
        if self.engine_info_label:
            self.engine_info_label.setText(f"{status}：{info.display_name}\n{info.description}")
        self._on_format_changed()

    def _apply_selected_preset(self, *_args: object) -> None:
        if not self.preset_combo or not self.preset_combo.currentData():
            return
        preset = next((item for item in UPSCALE_PRESETS if item.preset_id == self.preset_combo.currentData()), None)
        if not preset:
            return
        if not is_engine_enabled(preset.engine_id) or not is_model_enabled(preset.engine_id, preset.model_name):
            if self.engine_info_label:
                self.engine_info_label.setText("预设对应的引擎或模型未启用，请到“引擎设置”中检查。")
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
        if self.noise_combo:
            self.noise_combo.setCurrentIndex(max(0, self.noise_combo.findData(preset.noise_level)))
        if self.syncgap_combo:
            self.syncgap_combo.setCurrentIndex(max(0, self.syncgap_combo.findData(preset.syncgap_mode)))
        self._refresh_file_table(keep_selection=True)

    def _on_format_changed(self, *_args: object) -> None:
        selected = self.format_combo.currentData() if self.format_combo else "original"
        if self.quality_spin:
            self.quality_spin.setEnabled(selected in {"original", "jpg", "webp"})
        self._refresh_preview()

    def _refresh_preview(self, *_args: object) -> None:
        self._update_preview()

    def _update_preview(self, logger: Callable[[str], None] | None = None) -> None:
        if logger is not None and not callable(logger):
            logger = None
        if not self.size_label or not self.output_info_label:
            return
        if not self._files:
            self.size_label.setText("请添加图片、动图或视频文件。")
            self.output_info_label.setText("文件大小受内容、格式、倍率、质量和编码影响较大，仅供参考。")
            return
        selected = self._selected_file or self._files[0]
        media_type = self._media_type(selected)
        if media_type != "图片":
            interpolation_enabled = self.interpolation_enabled_checkbox.isChecked() if self.interpolation_enabled_checkbox else False
            interpolation_scale = self.interpolation_scale_combo.currentData() if self.interpolation_scale_combo else 2
            upscale_enabled = self.upscale_enabled_checkbox.isChecked() if self.upscale_enabled_checkbox else True
            mode_text = "超分 + 插帧" if upscale_enabled and interpolation_enabled else ("仅插帧" if interpolation_enabled else "仅超分")
            fps_text = "自动"
            if media_type == "视频":
                try:
                    source_fps = media_fps(probe_media(selected))
                    selected_fps = self.video_fps_spin.value() if self.video_fps_spin else 0
                    output_fps = selected_fps or source_fps * (interpolation_scale if interpolation_enabled else 1)
                    fps_text = f"{source_fps:.3f} -> {output_fps:.3f}"
                except Exception:
                    fps_text = "需要 ffprobe 才能预览"
            self.size_label.setText(
                f"当前参考文件：{selected.name}\n类型：{media_type}\n处理模式：{mode_text}\nRIFE 倍率：{interpolation_scale}x\n输出 FPS：{fps_text}"
            )
            self.output_info_label.setText("视频输出大小受帧数、编码、插帧倍率、超分倍率和音频保留影响较大，仅供参考。")
            if self.interpolation_preview_label:
                self.interpolation_preview_label.setText(f"输出 FPS：{fps_text}")
            return
        scale = self.scale_combo.currentData() if self.scale_combo else 4
        try:
            width, height, image_format = read_image_info(selected)
            output_width = width * int(scale)
            output_height = height * int(scale)
            format_text = self._preview_format_text(selected)
            self.size_label.setText(
                f"文件数量：{len(self._files)}\n当前参考图片：{selected.name}\n原图尺寸：{width} x {height}（{image_format}）\n当前倍率：{scale}x\n预计输出尺寸：{output_width} x {output_height}"
            )
            self.output_info_label.setText(
                f"预计输出尺寸：{output_width} x {output_height}\n输出格式：{format_text}\n文件大小受图片内容、格式和质量影响较大，仅供参考。"
            )
        except Exception as exc:
            self.size_label.setText(f"当前参考图片：{selected.name}\n图片读取失败，无法预估尺寸。")
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

    def _read_size_text(self, path: Path) -> str:
        if self._media_type(path) != "图片":
            return "后续识别"
        try:
            width, height, _fmt = read_image_info(path)
            return f"{width} x {height}"
        except Exception:
            return "读取失败"

    def _output_size_text(self, path: Path, scale: int) -> str:
        if self._media_type(path) != "图片":
            return "后续计算"
        try:
            width, height, _fmt = read_image_info(path)
            return f"{width * int(scale)} x {height * int(scale)}"
        except Exception:
            return "未知"

    def _media_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            return "图片"
        if suffix in ANIMATED_EXTENSIONS:
            return "动图"
        if suffix in VIDEO_EXTENSIONS:
            return "视频"
        return "未知"
