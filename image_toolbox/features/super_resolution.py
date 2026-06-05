from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from image_toolbox.core.config import AppConfig
from image_toolbox.core.engine_settings import get_engine_settings_store, is_engine_enabled, is_model_enabled
from image_toolbox.core.ffmpeg_tools import media_fps, probe_media
from image_toolbox.core.animated_tasks import (
    AnimatedMediaTask,
    AnimatedProcessSettings,
    is_animated_image,
    read_animated_info,
)
from image_toolbox.core.media_tasks import VideoMediaTask, VideoProcessSettings, list_interpolation_engine_models
from image_toolbox.core.model_library import resolve_interpolation_model_dir
from image_toolbox.core.media_task_utils import clear_media_task_cache, estimate_frame_bytes, format_bytes
from image_toolbox.core.super_resolution import (
    SuperResolutionBatchTask,
    SuperResolutionSettings,
    normalize_output_format,
    read_image_info,
    validate_super_resolution_inputs,
)
from image_toolbox.core.tool_manager import get_tool_manager
from image_toolbox.core.upscale_engines import DEFAULT_ENGINE_MANAGER
from image_toolbox.core.upscale_engines.presets import UPSCALE_PRESETS
from image_toolbox.features.base import ToolFeature
from image_toolbox.ui.widgets import NoWheelComboBox as QComboBox
from image_toolbox.ui.widgets import NoWheelDoubleSpinBox as QDoubleSpinBox
from image_toolbox.ui.widgets import NoWheelSpinBox as QSpinBox


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
ANIMATED_EXTENSIONS = {".gif", ".webp", ".png", ".apng"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

VIDEO_WORKFLOW_LABELS = {
    "upscale_only": "仅超分",
    "interpolate_only": "仅插帧",
    "upscale_then_interpolate": "先超分后插帧",
    "interpolate_then_upscale": "先插帧后超分",
    "extract_only": "仅拆帧",
    "encode_only": "仅合成",
}

VIDEO_WORKFLOW_STEPS = {
    "upscale_only": ["视频", "拆帧", "超分", "合成"],
    "interpolate_only": ["视频", "拆帧", "插帧", "合成"],
    "upscale_then_interpolate": ["视频", "拆帧", "超分", "插帧", "合成"],
    "interpolate_then_upscale": ["视频", "拆帧", "插帧", "超分", "合成"],
    "extract_only": ["视频", "拆帧"],
    "encode_only": ["帧目录", "合成视频"],
}

INTERPOLATION_ENGINE_HINTS = {
    "rife": "RIFE：推荐使用 rife-v4.6。旧模型如 rife-v2 兼容性较弱，建议优先换到 v4.6。",
    "ifrnet": "IFRNet：适合高质量插帧，速度通常比轻量模型慢。",
    "cain": "CAIN：适合兼容模式，TTA 参数会自动忽略。",
    "dain": "DAIN：经典插帧方案，速度较慢，建议先用短片测试；TTA 参数会自动忽略。",
}


class SuperResolutionFeature(ToolFeature):
    key = "super_resolution"
    title = "智能媒体增强"
    description = "统一处理图片超分、动图增强与视频超分/AI 插帧。v3.3.8 先开放图片增强，动图和视频参数预留。"

    def __init__(self) -> None:
        self.config = AppConfig(self.key)
        self.engine_settings_store = get_engine_settings_store()
        self.file_table: QTableWidget | None = None
        self.file_count_label: QLabel | None = None
        self.media_group: QGroupBox | None = None
        self.composition_group: QGroupBox | None = None
        self.output_group: QGroupBox | None = None
        self.upscale_group: QGroupBox | None = None
        self.interpolation_group: QGroupBox | None = None
        self.workflow_group: QGroupBox | None = None
        self.advanced_group: QGroupBox | None = None
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
        self.workflow_preview_label: QLabel | None = None
        self.task_summary_label: QLabel | None = None
        self.animated_hint_label: QLabel | None = None
        self.video_hint_label: QLabel | None = None
        self.animated_format_combo: QComboBox | None = None
        self.animated_fps_spin: QDoubleSpinBox | None = None
        self.preserve_loop_checkbox: QCheckBox | None = None
        self.keep_audio_checkbox: QCheckBox | None = None
        self.keep_temp_checkbox: QCheckBox | None = None
        self.video_fps_spin: QDoubleSpinBox | None = None
        self.video_workflow_combo: QComboBox | None = None
        self.video_frame_dir_edit: QLineEdit | None = None
        self.interpolation_enabled_checkbox: QCheckBox | None = None
        self.interpolation_engine_combo: QComboBox | None = None
        self.interpolation_scale_combo: QComboBox | None = None
        self.interpolation_model_combo: QComboBox | None = None
        self.interpolation_gpu_edit: QLineEdit | None = None
        self.interpolation_tta_checkbox: QCheckBox | None = None
        self.interpolation_preview_label: QLabel | None = None
        self.mode_buttons: dict[str, QRadioButton] = {}
        self.upscale_advanced_panel: QWidget | None = None
        self.interpolation_advanced_panel: QWidget | None = None
        self.task_waiting_label: QLabel | None = None
        self.task_running_label: QLabel | None = None
        self.task_done_label: QLabel | None = None
        self.task_failed_label: QLabel | None = None
        self.recent_log_box: QPlainTextEdit | None = None
        self.page_progress_bar: QProgressBar | None = None
        self.page_status_label: QLabel | None = None
        self.page_progress_percent_label: QLabel | None = None
        self.page_current_label: QLabel | None = None
        self.output_form: QFormLayout | None = None
        self.workflow_form: QFormLayout | None = None
        self.video_frame_dir_row: QWidget | None = None
        self.external_file_panel = None
        self._syncing_external_file_panel = False
        self._files: list[Path] = []
        self._statuses: list[str] = []
        self._selected_file: Path | None = None
        self._recent_logs: list[str] = []

    def build_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("SuperResolutionWorkbench")
        root = QVBoxLayout(panel)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        workbench_row = QHBoxLayout()
        workbench_row.setContentsMargins(0, 0, 0, 0)
        workbench_row.setSpacing(16)
        root.addLayout(workbench_row, 1)

        main = QFrame()
        main.setObjectName("SuperMainColumn")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(18, 18, 0, 0)
        main_layout.setSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(main)
        workbench_row.addWidget(scroll, 1)

        header = QHBoxLayout()
        header.setSpacing(16)
        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        title = QLabel(self.title)
        title.setObjectName("PanelTitle")
        hint = QLabel("统一处理图片、动图和视频，支持 AI 超分、插帧与多种增强处理。")
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        title_block.addWidget(title)
        title_block.addWidget(hint)
        header.addLayout(title_block, 1)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("图片增强", "image")
        self.mode_combo.addItem("动图增强", "animated")
        self.mode_combo.addItem("视频增强", "video")
        self.mode_combo.currentIndexChanged.connect(self._on_task_mode_changed)
        header.addWidget(QLabel("任务模式"))
        header.addWidget(self.mode_combo)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("自定义", "")
        for preset in UPSCALE_PRESETS:
            self.preset_combo.addItem(preset.display_name, preset.preset_id)
        self.preset_combo.currentIndexChanged.connect(self._apply_selected_preset)
        header.addWidget(QLabel("预设"))
        header.addWidget(self.preset_combo)
        main_layout.addLayout(header)

        main_layout.addWidget(self._build_mode_bar())

        cards = QGridLayout()
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setHorizontalSpacing(16)
        cards.setVerticalSpacing(16)
        cards.setAlignment(Qt.AlignmentFlag.AlignTop)
        cards.addWidget(self._build_upscale_group(), 0, 0, alignment=Qt.AlignmentFlag.AlignTop)
        cards.addWidget(self._build_output_group(), 0, 1, alignment=Qt.AlignmentFlag.AlignTop)
        cards.addWidget(self._build_interpolation_group(), 1, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignTop)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)
        cards.setRowStretch(0, 0)
        cards.setRowStretch(1, 0)
        main_layout.addLayout(cards)
        main_layout.addStretch(1)

        self._configure_video_groups()
        self.refresh_from_engine_settings()
        self._on_video_workflow_changed()
        self._on_task_mode_changed()
        return panel

    def _glass_card(self, title: str, object_name: str = "SuperGlassCard") -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        label = QLabel(title)
        label.setObjectName("CardTitle")
        layout.addWidget(label)
        return card

    def _build_mode_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("SuperModeBar")
        bar.setFixedHeight(48)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(16)
        layout.addWidget(QLabel("任务模式"))
        group = QButtonGroup(bar)
        for label, key in [("图片增强", "image"), ("动图增强", "animated"), ("视频增强", "video")]:
            button = QRadioButton(label)
            button.setObjectName("TaskModeRadio")
            button.toggled.connect(lambda checked, mode=key: checked and self._set_task_mode(mode))
            self.mode_buttons[key] = button
            group.addButton(button)
            layout.addWidget(button)
        self.mode_buttons["image"].setChecked(True)
        layout.addStretch()
        return bar

    def _build_file_area(self) -> QWidget:
        group = self._glass_card("文件区域")
        layout = group.layout()
        if not isinstance(layout, QVBoxLayout):
            layout = QVBoxLayout(group)
        drop = QLabel("拖拽文件或文件夹到这里，或点击下方按钮添加\n支持图片（JPG/PNG/WebP）、动图（GIF/APNG/WebP）和视频（MP4/MKV 等）")
        drop.setObjectName("SuperDropZone")
        drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop.setMinimumHeight(60)
        layout.addWidget(drop)

        self.file_table = QTableWidget(0, 6)
        self.file_table.setObjectName("SuperFileTable")
        self.file_table.setHorizontalHeaderLabels(["文件名", "类型", "状态", "尺寸", "预计输出", "完整路径"])
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.file_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.file_table.currentCellChanged.connect(lambda row, *_args: self._select_row(row))
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.file_table.setFixedHeight(220)
        layout.addWidget(self.file_table)
        return group

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.file_count_label = QLabel("文件数量：0")
        self.file_count_label.setObjectName("CardTitle")
        add_button = QPushButton("添加文件")
        add_folder_button = QPushButton("添加文件夹")
        remove_button = QPushButton("删除选中")
        clear_button = QPushButton("清空")
        open_output_button = QPushButton("打开输出目录")
        clear_cache_button = QPushButton("清理媒体缓存")
        add_button.clicked.connect(self.choose_files)
        add_folder_button.clicked.connect(self._choose_folder)
        remove_button.clicked.connect(self.remove_selected_file)
        clear_button.clicked.connect(self.clear_files)
        open_output_button.clicked.connect(self._open_output_from_page)
        clear_cache_button.clicked.connect(self._clear_media_cache_from_page)
        for button in [add_folder_button, remove_button, clear_button, open_output_button, clear_cache_button]:
            button.setObjectName("GhostButton")
        row.addWidget(self.file_count_label)
        row.addWidget(add_button)
        row.addWidget(add_folder_button)
        row.addWidget(remove_button)
        row.addWidget(clear_button)
        row.addStretch()
        row.addWidget(clear_cache_button)
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
        group = QGroupBox("图片 / 动图参数")
        self.media_group = group
        form = QFormLayout(group)
        self.format_combo = QComboBox()
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        form.addRow("静态图片保存为", self.format_combo)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(self.config.get("quality", 95, int))
        self.quality_spin.valueChanged.connect(self._refresh_preview)
        form.addRow("图片质量", self.quality_spin)
        self.animated_format_combo = QComboBox()
        self.animated_format_combo.addItem("GIF", "gif")
        self.animated_format_combo.addItem("WebP", "webp")
        self.animated_format_combo.addItem("APNG", "apng")
        self.animated_format_combo.setCurrentIndex(max(0, self.animated_format_combo.findData(self.config.get("animated_output_format", "gif", str))))
        self.animated_format_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow("动图输出格式", self.animated_format_combo)
        self.animated_fps_spin = QDoubleSpinBox()
        self.animated_fps_spin.setRange(0, 120)
        self.animated_fps_spin.setDecimals(3)
        self.animated_fps_spin.setSingleStep(1)
        self.animated_fps_spin.setValue(self.config.get("animated_output_fps", 0.0, float))
        self.animated_fps_spin.setToolTip("0 表示保留原始帧延迟。")
        self.animated_fps_spin.valueChanged.connect(self._refresh_preview)
        form.addRow("动图输出 FPS", self.animated_fps_spin)
        self.preserve_loop_checkbox = QCheckBox("保留原循环次数")
        self.preserve_loop_checkbox.setChecked(self.config.get("animated_preserve_loop", True, bool))
        form.addRow("动图循环", self.preserve_loop_checkbox)
        self.animated_hint_label = QLabel("动图已支持 GIF / WebP / APNG 信息读取、拆帧、逐帧处理和重新合成。")
        self.animated_hint_label.setObjectName("MutedText")
        self.animated_hint_label.setWordWrap(True)
        form.addRow("动图", self.animated_hint_label)
        return group

    def _build_composition_group(self) -> QWidget:
        group = QGroupBox("合成设置")
        self.composition_group = group
        form = QFormLayout(group)
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
        self.video_hint_label = QLabel("视频任务已支持仅超分、仅插帧、超分后插帧、插帧后超分、仅拆帧和仅合成。")
        self.video_hint_label.setObjectName("MutedText")
        self.video_hint_label.setWordWrap(True)
        form.addRow("视频", self.video_hint_label)
        return group

    def _build_output_group(self) -> QWidget:
        group = self._glass_card("输出设置")
        self.output_group = group
        form = QFormLayout()
        form.setContentsMargins(0, 6, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.output_form = form
        group.layout().addLayout(form)
        self.output_edit = QLineEdit(self.config.get("output_dir", str(Path.cwd() / "output")))
        browse_button = QPushButton("选择")
        browse_button.setObjectName("GhostButton")
        browse_button.clicked.connect(self._choose_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit)
        output_row.addWidget(browse_button)
        form.addRow("输出目录", output_row)
        self.format_combo = QComboBox()
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        form.addRow("图片格式", self.format_combo)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(self.config.get("quality", 95, int))
        self.quality_spin.valueChanged.connect(self._refresh_preview)
        form.addRow("图片质量", self.quality_spin)
        self.animated_format_combo = QComboBox()
        self.animated_format_combo.addItem("GIF", "gif")
        self.animated_format_combo.addItem("WebP", "webp")
        self.animated_format_combo.addItem("APNG", "apng")
        self.animated_format_combo.setCurrentIndex(max(0, self.animated_format_combo.findData(self.config.get("animated_output_format", "gif", str))))
        self.animated_format_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow("动图格式", self.animated_format_combo)
        self.animated_fps_spin = QDoubleSpinBox()
        self.animated_fps_spin.setRange(0, 120)
        self.animated_fps_spin.setDecimals(3)
        self.animated_fps_spin.setSingleStep(1)
        self.animated_fps_spin.setValue(self.config.get("animated_output_fps", 0.0, float))
        self.animated_fps_spin.setToolTip("0 表示保留原始帧延迟。")
        self.animated_fps_spin.valueChanged.connect(self._refresh_preview)
        form.addRow("动图 FPS", self.animated_fps_spin)
        self.video_fps_spin = QDoubleSpinBox()
        self.video_fps_spin.setRange(0, 240)
        self.video_fps_spin.setDecimals(3)
        self.video_fps_spin.setSingleStep(1)
        self.video_fps_spin.setValue(self.config.get("video_output_fps", 0.0, float))
        self.video_fps_spin.setToolTip("0 表示自动：仅超分保持原 FPS，插帧按倍率提升 FPS。")
        self.video_fps_spin.valueChanged.connect(self._refresh_preview)
        form.addRow("视频 FPS", self.video_fps_spin)
        self.conflict_combo = QComboBox()
        self.conflict_combo.addItem("自动重命名", "rename")
        self.conflict_combo.addItem("跳过", "skip")
        self.conflict_combo.addItem("覆盖", "overwrite")
        self.conflict_combo.setCurrentIndex(max(0, self.conflict_combo.findData(self.config.get("conflict_strategy", "rename"))))
        self.video_workflow_combo = QComboBox()
        for workflow_key, workflow_label in VIDEO_WORKFLOW_LABELS.items():
            self.video_workflow_combo.addItem(workflow_label, workflow_key)
        self.video_workflow_combo.setCurrentIndex(max(0, self.video_workflow_combo.findData(self.config.get("video_workflow_mode", "upscale_then_interpolate", str))))
        self.video_workflow_combo.currentIndexChanged.connect(self._on_video_workflow_changed)
        self.video_frame_dir_edit = QLineEdit(self.config.get("video_input_frame_dir", "", str))
        frame_dir_button = QPushButton("选择帧目录")
        frame_dir_button.setObjectName("GhostButton")
        frame_dir_button.clicked.connect(self._choose_video_frame_dir)
        self.video_frame_dir_row = QWidget()
        frame_dir_row = QHBoxLayout(self.video_frame_dir_row)
        frame_dir_row.setContentsMargins(0, 0, 0, 0)
        frame_dir_row.addWidget(self.video_frame_dir_edit)
        frame_dir_row.addWidget(frame_dir_button)
        form.addRow("覆盖策略", self.conflict_combo)
        form.addRow("视频流程", self.video_workflow_combo)
        form.addRow("仅合成帧目录", self.video_frame_dir_row)
        self.keep_audio_checkbox = QCheckBox("保留音频")
        self.keep_audio_checkbox.setChecked(self.config.get("keep_audio", True, bool))
        form.addRow("音频", self.keep_audio_checkbox)
        self.keep_temp_checkbox = QCheckBox("保留临时文件")
        self.keep_temp_checkbox.setChecked(self.config.get("keep_temp", False, bool))
        form.addRow("临时文件", self.keep_temp_checkbox)
        self.preserve_loop_checkbox = QCheckBox("保留动图循环次数")
        self.preserve_loop_checkbox.setChecked(self.config.get("animated_preserve_loop", True, bool))
        form.addRow("动图循环", self.preserve_loop_checkbox)
        open_output_button = QPushButton("打开输出目录")
        open_output_button.setObjectName("GhostButton")
        open_output_button.clicked.connect(self._open_output_from_page)
        form.addRow("快捷操作", open_output_button)
        return group

    def _build_upscale_group(self) -> QWidget:
        group = self._glass_card("超分设置")
        self.upscale_group = group
        form = QFormLayout()
        form.setContentsMargins(0, 6, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        group.layout().addLayout(form)
        self.upscale_enabled_checkbox = QCheckBox("启用超分 / 图片增强")
        self.upscale_enabled_checkbox.setChecked(self.config.get("upscale_enabled", True, bool))
        self.upscale_enabled_checkbox.stateChanged.connect(self._refresh_preview)
        form.addRow("", self.upscale_enabled_checkbox)
        self.engine_combo = QComboBox()
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        form.addRow("超分引擎", self.engine_combo)
        self.model_combo = QComboBox()
        form.addRow("模型", self.model_combo)
        self.scale_combo = QComboBox()
        self.scale_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow("倍率", self.scale_combo)
        self.noise_combo = QComboBox()
        form.addRow("降噪", self.noise_combo)
        self.low_memory_checkbox = QCheckBox("低显存")
        self.low_memory_checkbox.stateChanged.connect(self._refresh_preview)
        form.addRow("", self.low_memory_checkbox)

        advanced_button = QPushButton("高级设置 ▼")
        advanced_button.setObjectName("GhostButton")
        self.upscale_advanced_panel = QFrame()
        self.upscale_advanced_panel.setObjectName("SuperAdvancedPanel")
        advanced_form = QFormLayout(self.upscale_advanced_panel)
        advanced_form.setContentsMargins(0, 8, 0, 0)
        self.tile_spin = QSpinBox()
        self.tile_spin.setRange(0, 2048)
        self.tile_spin.setSingleStep(32)
        self.tile_spin.setValue(self.config.get("tile_size", 0, int))
        self.tile_spin.valueChanged.connect(self._refresh_preview)
        advanced_form.addRow("Tile", self.tile_spin)
        self.gpu_edit = QLineEdit(self.config.get("gpu_id", "auto"))
        advanced_form.addRow("GPU", self.gpu_edit)
        self.tta_checkbox = QCheckBox("启用 TTA 增强，速度会更慢")
        self.tta_checkbox.setChecked(self.config.get("use_tta", False, bool))
        advanced_form.addRow("TTA", self.tta_checkbox)
        self.threads_edit = QLineEdit(self.config.get("threads", "1:2:2"))
        advanced_form.addRow("线程", self.threads_edit)
        self.syncgap_combo = QComboBox()
        advanced_form.addRow("SyncGap", self.syncgap_combo)
        self.upscale_advanced_panel.setVisible(False)
        advanced_button.clicked.connect(lambda: self._toggle_advanced(self.upscale_advanced_panel, advanced_button))
        group.layout().addWidget(advanced_button)
        group.layout().addWidget(self.upscale_advanced_panel)
        self.engine_info_label = QLabel("")
        self.engine_info_label.setObjectName("MutedText")
        self.engine_info_label.setWordWrap(True)
        group.layout().addWidget(self.engine_info_label)
        return group

    def _build_interpolation_group(self) -> QWidget:
        group = self._glass_card("插帧设置")
        self.interpolation_group = group
        form = QFormLayout()
        form.setContentsMargins(0, 6, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        group.layout().addLayout(form)
        self.interpolation_enabled_checkbox = QCheckBox("启用插帧")
        self.interpolation_enabled_checkbox.setChecked(self.config.get("interpolation_enabled", False, bool))
        self.interpolation_enabled_checkbox.stateChanged.connect(self._on_interpolation_changed)
        form.addRow("", self.interpolation_enabled_checkbox)
        self.interpolation_engine_combo = QComboBox()
        self.interpolation_engine_combo.addItem("RIFE", "rife")
        self.interpolation_engine_combo.addItem("IFRNet", "ifrnet")
        self.interpolation_engine_combo.addItem("CAIN", "cain")
        self.interpolation_engine_combo.addItem("DAIN", "dain")
        self.interpolation_engine_combo.setCurrentIndex(max(0, self.interpolation_engine_combo.findData(self.config.get("interpolation_engine", "rife", str))))
        self.interpolation_engine_combo.currentIndexChanged.connect(self._on_interpolation_engine_changed)
        form.addRow("插帧引擎", self.interpolation_engine_combo)
        self.interpolation_scale_combo = QComboBox()
        self.interpolation_scale_combo.addItem("2x", 2)
        self.interpolation_scale_combo.addItem("4x", 4)
        self.interpolation_scale_combo.setCurrentIndex(max(0, self.interpolation_scale_combo.findData(self.config.get("interpolation_scale", 2, int))))
        self.interpolation_scale_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow("插帧倍率", self.interpolation_scale_combo)
        self.interpolation_model_combo = QComboBox()
        self._refresh_interpolation_models()
        self.interpolation_model_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow("模型", self.interpolation_model_combo)

        advanced_button = QPushButton("高级设置 ▼")
        advanced_button.setObjectName("GhostButton")
        self.interpolation_advanced_panel = QFrame()
        self.interpolation_advanced_panel.setObjectName("SuperAdvancedPanel")
        advanced_form = QFormLayout(self.interpolation_advanced_panel)
        advanced_form.setContentsMargins(0, 8, 0, 0)
        self.interpolation_gpu_edit = QLineEdit(self.config.get("interpolation_gpu_id", "auto"))
        advanced_form.addRow("GPU", self.interpolation_gpu_edit)
        self.interpolation_tta_checkbox = QCheckBox("启用 TTA（如果当前插帧引擎支持）")
        self.interpolation_tta_checkbox.setChecked(self.config.get("interpolation_tta", False, bool))
        advanced_form.addRow("TTA", self.interpolation_tta_checkbox)
        self.interpolation_preview_label = QLabel("输出 FPS：自动")
        self.interpolation_preview_label.setObjectName("MutedText")
        self.interpolation_preview_label.setWordWrap(True)
        advanced_form.addRow("引擎参数", self.interpolation_preview_label)
        self.interpolation_advanced_panel.setVisible(False)
        advanced_button.clicked.connect(lambda: self._toggle_advanced(self.interpolation_advanced_panel, advanced_button))
        group.layout().addWidget(advanced_button)
        group.layout().addWidget(self.interpolation_advanced_panel)
        self._on_interpolation_changed()
        return group

    def _build_advanced_group(self) -> QWidget:
        group = QGroupBox("高级设置")
        self.advanced_group = group
        layout = QVBoxLayout(group)
        hint = QLabel(
            "普通任务通常不需要调整这里。\n"
            "GPU ID、Tile、TTA 已按作用域放在“超分设置”和“插帧设置”中；未来的视频编码器、显卡策略和批处理高级参数会继续集中到这里。"
        )
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return group

    def _refresh_interpolation_models(self) -> None:
        if not self.interpolation_model_combo:
            return
        saved_model = self.config.get("interpolation_model", "", str)
        engine_id = self.interpolation_engine_combo.currentData() if self.interpolation_engine_combo else "rife"
        self.interpolation_model_combo.blockSignals(True)
        self.interpolation_model_combo.clear()
        models = list_interpolation_engine_models(engine_id)
        if models:
            for model in models:
                self.interpolation_model_combo.addItem(model or "默认模型目录", model)
            self.interpolation_model_combo.setCurrentIndex(max(0, self.interpolation_model_combo.findData(saved_model)))
        else:
            self.interpolation_model_combo.addItem(f"未导入 {str(engine_id).upper()} 模型", "")
        self.interpolation_model_combo.blockSignals(False)

    def _on_interpolation_engine_changed(self, *_args: object) -> None:
        self._refresh_interpolation_models()
        self._on_interpolation_changed()

    def _video_workflow_mode(self) -> str:
        return self.video_workflow_combo.currentData() if self.video_workflow_combo else "upscale_then_interpolate"

    def _workflow_needs_upscale(self) -> bool:
        return self._video_workflow_mode() in {"upscale_only", "upscale_then_interpolate", "interpolate_then_upscale"}

    def _workflow_needs_interpolation(self) -> bool:
        return self._video_workflow_mode() in {"interpolate_only", "upscale_then_interpolate", "interpolate_then_upscale"}

    def _workflow_needs_encode(self) -> bool:
        return self._video_workflow_mode() != "extract_only"

    def _workflow_label(self) -> str:
        return VIDEO_WORKFLOW_LABELS.get(self._video_workflow_mode(), self._video_workflow_mode())

    def _workflow_preview_text(self) -> str:
        mode = self.mode_combo.currentData() if self.mode_combo else "image"
        if mode == "animated":
            return "工作流：GIF/WebP/APNG → 拆帧 → 超分 → 合成"
        if mode == "image":
            return "工作流：图片 → 超分 → 输出"
        steps = VIDEO_WORKFLOW_STEPS.get(self._video_workflow_mode(), [])
        if steps:
            return "工作流：" + " → ".join(steps)
        return "工作流：视频 → 拆帧 → 超分 → 插帧 → 合成"

    def _configure_video_groups(self) -> None:
        for group in [
            self.workflow_group,
            self.upscale_group,
            self.interpolation_group,
            self.composition_group,
            self.output_group,
            self.advanced_group,
        ]:
            if not group:
                continue
            if hasattr(group, "setCheckable"):
                group.setStyleSheet("QGroupBox::title { font-weight: 600; }")
                group.setCheckable(True)
                group.toggled.connect(lambda checked, current_group=group: self._set_group_content_visible(current_group, checked))
                group.setChecked(True)
                self._set_group_content_visible(group, True)

    def _set_group_content_visible(self, group: QGroupBox, visible: bool) -> None:
        for child in group.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
            child.setVisible(visible)

    def _set_group_expanded(self, group: QGroupBox | None, expanded: bool, enabled: bool = True, tooltip: str = "") -> None:
        if not group:
            return
        if not hasattr(group, "setChecked"):
            group.setVisible(expanded)
            group.setEnabled(enabled)
            group.setToolTip("" if enabled else tooltip)
            return
        group.blockSignals(True)
        group.setChecked(expanded)
        self._set_group_content_visible(group, expanded)
        group.blockSignals(False)
        group.setEnabled(enabled)
        group.setToolTip("" if enabled else tooltip)

    def _apply_video_group_state(self) -> None:
        mode = self._video_workflow_mode()
        needs_upscale = self._workflow_needs_upscale()
        needs_interpolation = self._workflow_needs_interpolation()
        needs_encode = self._workflow_needs_encode()
        self._set_group_expanded(self.workflow_group, True, True)
        self._set_group_expanded(
            self.upscale_group,
            needs_upscale,
            needs_upscale,
            "当前模式不需要超分。",
        )
        self._set_group_expanded(
            self.interpolation_group,
            needs_interpolation,
            needs_interpolation,
            "当前模式不需要插帧。",
        )
        self._set_group_expanded(
            self.composition_group,
            needs_encode,
            needs_encode,
            "仅拆帧模式不会合成视频。",
        )
        self._set_group_expanded(self.output_group, True, True)
        self._set_group_expanded(self.advanced_group, False, True)

    def _interpolation_engine_hint(self) -> str:
        engine_id = self.interpolation_engine_combo.currentData() if self.interpolation_engine_combo else "rife"
        model_name = self.interpolation_model_combo.currentData() if self.interpolation_model_combo else ""
        hint = INTERPOLATION_ENGINE_HINTS.get(engine_id, "")
        if engine_id == "rife" and str(model_name).startswith("rife-v2"):
            hint += "\n当前选择的是旧 RIFE 模型，建议使用 rife-v4.6。"
        return hint

    def _set_effective(self, widget: QWidget | None, enabled: bool, disabled_tip: str) -> None:
        if not widget:
            return
        widget.setEnabled(enabled)
        widget.setToolTip("" if enabled else disabled_tip)

    def _set_widgets_effective(self, widgets: list[QWidget | None], enabled: bool, disabled_tip: str) -> None:
        for widget in widgets:
            self._set_effective(widget, enabled, disabled_tip)

    def _on_video_workflow_changed(self, *_args: object) -> None:
        mode = self._video_workflow_mode()
        needs_upscale = self._workflow_needs_upscale()
        needs_interpolation = self._workflow_needs_interpolation()
        needs_encode = self._workflow_needs_encode()
        self._apply_video_group_state()
        if self.upscale_enabled_checkbox:
            self.upscale_enabled_checkbox.blockSignals(True)
            self.upscale_enabled_checkbox.setChecked(needs_upscale)
            self.upscale_enabled_checkbox.setEnabled(needs_upscale)
            self.upscale_enabled_checkbox.setToolTip("" if needs_upscale else f"{self._workflow_label()} 模式不会执行超分。")
            self.upscale_enabled_checkbox.blockSignals(False)
        self._set_widgets_effective(
            [
                self.engine_combo,
                self.model_combo,
                self.scale_combo,
                self.noise_combo,
                self.syncgap_combo,
                self.tile_spin,
                self.gpu_edit,
                self.threads_edit,
                self.tta_checkbox,
                self.low_memory_checkbox,
            ],
            needs_upscale,
            f"{self._workflow_label()} 模式不会执行超分，这些参数不会生效。",
        )
        if self.interpolation_enabled_checkbox:
            self.interpolation_enabled_checkbox.blockSignals(True)
            self.interpolation_enabled_checkbox.setChecked(needs_interpolation)
            self.interpolation_enabled_checkbox.setEnabled(needs_interpolation)
            self.interpolation_enabled_checkbox.setToolTip("" if needs_interpolation else f"{self._workflow_label()} 模式不会执行插帧。")
            self.interpolation_enabled_checkbox.blockSignals(False)
        if self.video_frame_dir_edit:
            self._set_effective(self.video_frame_dir_edit, mode == "encode_only", "只有“仅合成”模式需要输入帧目录。")
        if self.video_fps_spin:
            self._set_effective(self.video_fps_spin, needs_encode, "仅拆帧模式不会合成视频，输出 FPS 不会生效。")
        if self.keep_audio_checkbox:
            self._set_effective(self.keep_audio_checkbox, mode not in {"extract_only", "encode_only"}, "该模式不会从原视频合成音频。")
        self._on_interpolation_changed()
        self._refresh_preview()

    def _on_interpolation_changed(self, *_args: object) -> None:
        enabled = self._workflow_needs_interpolation()
        engine_id = self.interpolation_engine_combo.currentData() if self.interpolation_engine_combo else "rife"
        for widget in [
            self.interpolation_engine_combo,
            self.interpolation_scale_combo,
            self.interpolation_model_combo,
            self.interpolation_gpu_edit,
        ]:
            if widget:
                widget.setEnabled(enabled)
                widget.setToolTip("" if enabled else f"{self._workflow_label()} 模式不会执行插帧，这个参数不会生效。")
        if self.interpolation_tta_checkbox:
            supports_tta = engine_id not in {"cain", "dain"}
            self.interpolation_tta_checkbox.setEnabled(enabled and supports_tta)
            if enabled and not supports_tta:
                self.interpolation_tta_checkbox.setToolTip(f"{str(engine_id).upper()} 当前不支持 TTA，任务会忽略该参数。")
            elif enabled:
                self.interpolation_tta_checkbox.setToolTip("")
            else:
                self.interpolation_tta_checkbox.setToolTip(f"{self._workflow_label()} 模式不会执行插帧，这个参数不会生效。")
            if not supports_tta:
                self.interpolation_tta_checkbox.setChecked(False)
        if self.interpolation_preview_label:
            self.interpolation_preview_label.setText(self._interpolation_engine_hint())
        self._refresh_preview()

    def _choose_video_frame_dir(self) -> None:
        if not self.video_frame_dir_edit:
            return
        directory = QFileDialog.getExistingDirectory(None, "选择仅合成输入帧目录", self.video_frame_dir_edit.text() or str(Path.cwd()))
        if directory:
            self.video_frame_dir_edit.setText(directory)
            self._refresh_preview()

    def _build_preview_group(self) -> QWidget:
        group = self._glass_card("工作流预览", "SuperWorkflowBar")
        self.workflow_group = group
        layout = group.layout()
        workflow_form = QFormLayout()
        self.workflow_form = workflow_form
        self.video_workflow_combo = QComboBox()
        self.video_workflow_combo.addItem("先超分后插帧", "upscale_then_interpolate")
        self.video_workflow_combo.addItem("仅超分", "upscale_only")
        self.video_workflow_combo.addItem("仅插帧", "interpolate_only")
        self.video_workflow_combo.addItem("先插帧后超分", "interpolate_then_upscale")
        self.video_workflow_combo.addItem("仅拆帧", "extract_only")
        self.video_workflow_combo.addItem("仅合成", "encode_only")
        self.video_workflow_combo.setCurrentIndex(max(0, self.video_workflow_combo.findData(self.config.get("video_workflow_mode", "upscale_then_interpolate", str))))
        self.video_workflow_combo.currentIndexChanged.connect(self._on_video_workflow_changed)
        workflow_form.addRow("视频流程", self.video_workflow_combo)
        self.video_frame_dir_edit = QLineEdit(self.config.get("video_input_frame_dir", "", str))
        frame_dir_button = QPushButton("选择帧目录")
        frame_dir_button.setObjectName("GhostButton")
        frame_dir_button.clicked.connect(self._choose_video_frame_dir)
        self.video_frame_dir_row = QWidget()
        frame_dir_row = QHBoxLayout(self.video_frame_dir_row)
        frame_dir_row.setContentsMargins(0, 0, 0, 0)
        frame_dir_row.addWidget(self.video_frame_dir_edit)
        frame_dir_row.addWidget(frame_dir_button)
        workflow_form.addRow("仅合成帧目录", self.video_frame_dir_row)
        layout.addLayout(workflow_form)
        self.workflow_preview_label = QLabel("")
        self.workflow_preview_label.setObjectName("SuperWorkflowText")
        self.workflow_preview_label.setWordWrap(False)
        self.task_summary_label = QLabel("")
        self.task_summary_label.setObjectName("MutedText")
        self.task_summary_label.setWordWrap(True)
        self.size_label = QLabel("请添加文件。")
        self.size_label.setObjectName("MutedText")
        self.size_label.setWordWrap(True)
        self.output_info_label = QLabel("文件大小受内容、格式、倍率、质量和编码影响较大，仅供参考。")
        self.output_info_label.setObjectName("MutedText")
        self.output_info_label.setWordWrap(True)
        layout.addWidget(self.workflow_preview_label)
        self.task_summary_label.setVisible(False)
        self.size_label.setVisible(False)
        self.output_info_label.setVisible(False)
        return group

    def _build_task_center(self) -> QWidget:
        center = QFrame()
        center.setObjectName("RightPanel")
        center.setFixedWidth(350)
        layout = QVBoxLayout(center)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("任务队列")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        stats = QGridLayout()
        stats.setHorizontalSpacing(8)
        stats.setVerticalSpacing(8)
        self.task_waiting_label = self._task_stat("等待中 0")
        self.task_running_label = self._task_stat("处理中 0")
        self.task_done_label = self._task_stat("完成 0")
        self.task_failed_label = self._task_stat("失败 0")
        stats.addWidget(self.task_waiting_label, 0, 0)
        stats.addWidget(self.task_running_label, 0, 1)
        stats.addWidget(self.task_done_label, 1, 0)
        stats.addWidget(self.task_failed_label, 1, 1)
        layout.addLayout(stats)

        empty = QLabel("暂无任务\n添加文件后点击开始处理")
        empty.setObjectName("SuperTaskEmpty")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setMinimumHeight(150)
        layout.addWidget(empty)

        layout.addStretch(1)

        actions = QVBoxLayout()
        open_log_button = QPushButton("打开日志目录")
        retry_button = QPushButton("重试失败任务")
        for button in [open_log_button, retry_button]:
            button.setObjectName("GhostButton")
            actions.addWidget(button)
        open_log_button.clicked.connect(self._open_log_dir_from_page)
        retry_button.setEnabled(False)
        layout.addLayout(actions)
        return center

    def _task_stat(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("QueueStatPill")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _build_page_status_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("GlassStatusBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(12)
        self.page_status_label = QLabel("就绪｜0%｜无当前任务｜剩余 --:--｜临时空间估算中")
        self.page_status_label.setObjectName("BottomStatusText")
        self.page_status_label.setText("状态：就绪")
        self.page_progress_bar = QProgressBar()
        self.page_progress_bar.setRange(0, 100)
        self.page_progress_bar.setValue(0)
        self.page_progress_bar.setTextVisible(False)
        self.page_progress_bar.setFixedWidth(180)
        self.page_progress_bar.setFixedHeight(16)
        layout.addWidget(self.page_status_label)
        layout.addWidget(self.page_progress_bar)
        self.page_progress_percent_label = QLabel("0%")
        self.page_progress_percent_label.setObjectName("BottomStatusText")
        self.page_progress_percent_label.setFixedWidth(42)
        layout.addWidget(self.page_progress_percent_label)
        self.page_current_label = QLabel("当前：未开始")
        self.page_current_label.setObjectName("BottomStatusText")
        layout.addWidget(self.page_current_label, 1)
        settings_button = QPushButton("设置")
        settings_button.setObjectName("BottomActionButton")
        settings_button.setFixedSize(78, 34)
        settings_button.clicked.connect(self._show_settings_from_page)
        layout.addWidget(settings_button)
        log_button = QPushButton("查看日志")
        log_button.setObjectName("BottomActionButton")
        log_button.setFixedSize(96, 34)
        log_button.clicked.connect(self._show_log_dialog_from_page)
        layout.addWidget(log_button)
        bar.setFixedHeight(48)
        return bar

    def _show_settings_from_page(self) -> None:
        window = self.window()
        if hasattr(window, "show_settings_dialog"):
            window.show_settings_dialog()

    def _show_log_dialog_from_page(self) -> None:
        window = self.window()
        if hasattr(window, "show_log_dialog"):
            window.show_log_dialog()

    def _toggle_advanced(self, panel: QWidget | None, button: QPushButton) -> None:
        if not panel:
            return
        visible = not panel.isVisible()
        panel.setVisible(visible)
        button.setText("高级设置 ▲" if visible else "高级设置 ▼")

    def _set_task_mode(self, mode: str) -> None:
        if self.mode_combo:
            index = self.mode_combo.findData(mode)
            if index >= 0 and self.mode_combo.currentIndex() != index:
                self.mode_combo.setCurrentIndex(index)

    def _on_task_mode_changed(self, *_args: object) -> None:
        mode = self.mode_combo.currentData() if self.mode_combo else "image"
        for key, button in self.mode_buttons.items():
            button.blockSignals(True)
            button.setChecked(key == mode)
            button.blockSignals(False)
        if self.upscale_group:
            self.upscale_group.setVisible(mode in {"image", "animated", "video"})
        if self.interpolation_group:
            self.interpolation_group.setVisible(mode == "video")
        if self.animated_format_combo:
            self._set_form_field_visible(self.output_form, self.animated_format_combo, mode == "animated")
        if self.animated_fps_spin:
            self._set_form_field_visible(self.output_form, self.animated_fps_spin, mode == "animated")
        if self.preserve_loop_checkbox:
            self._set_form_field_visible(self.output_form, self.preserve_loop_checkbox, mode == "animated")
        if self.keep_audio_checkbox:
            self._set_form_field_visible(self.output_form, self.keep_audio_checkbox, mode == "video")
        if self.video_fps_spin:
            self._set_form_field_visible(self.output_form, self.video_fps_spin, mode == "video")
        if self.video_workflow_combo:
            self._set_form_field_visible(self.output_form, self.video_workflow_combo, mode == "video")
        if self.video_frame_dir_row:
            self._set_form_field_visible(self.output_form, self.video_frame_dir_row, mode == "video")
        self._refresh_preview()

    def _set_form_field_visible(self, form: QFormLayout | None, field: QWidget | None, visible: bool) -> None:
        if not field:
            return
        field.setVisible(visible)
        if form:
            label = form.labelForField(field)
            if label:
                label.setVisible(visible)

    def append_log(self, message: str) -> None:
        return

    def set_page_progress(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        if self.page_progress_bar:
            self.page_progress_bar.setValue(value)
        if self.page_progress_percent_label:
            self.page_progress_percent_label.setText(f"{value}%")
        if self.page_status_label:
            selected = self._selected_file.name if self._selected_file else "无当前任务"
            state = "处理中" if value and value < 100 else ("完成" if value >= 100 else "就绪")
            self.page_status_label.setText(f"{state}｜{value}%｜{selected}｜剩余 --:--｜临时空间估算中")

        if self.page_status_label:
            state = "处理中" if value and value < 100 else ("完成" if value >= 100 else "就绪")
            self.page_status_label.setText(f"状态：{state}")
        if self.page_current_label:
            selected = self._selected_file.name if self._selected_file else "未开始"
            self.page_current_label.setText(f"当前：{selected}")

    def set_current_progress(self, message: str) -> None:
        if self.page_status_label:
            value = self.page_progress_bar.value() if self.page_progress_bar else 0
            self.page_status_label.setText(f"处理中｜{value}%｜{message}｜剩余 --:--｜临时空间估算中")

        if self.page_status_label:
            self.page_status_label.setText("状态：处理中")
        if self.page_current_label:
            self.page_current_label.setText(message)

    def choose_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            None,
            "选择媒体文件",
            str(Path.cwd()),
            "Media Files (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.gif *.apng *.mp4 *.mov *.mkv *.avi *.webm *.m4v)",
        )
        self.add_files([Path(item) for item in selected])

    def bind_file_panel(self, file_panel) -> None:
        self.external_file_panel = file_panel
        self._sync_external_file_panel()

    def _sync_external_file_panel(self) -> None:
        if not self.external_file_panel or self._syncing_external_file_panel:
            return
        self._syncing_external_file_panel = True
        try:
            if hasattr(self.external_file_panel, "set_files"):
                self.external_file_panel.set_files(self._files, self._statuses)
        finally:
            self._syncing_external_file_panel = False

    def _choose_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(None, "选择媒体文件夹", str(Path.cwd()))
        if not directory:
            return
        root = Path(directory)
        supported = IMAGE_EXTENSIONS | ANIMATED_EXTENSIONS | VIDEO_EXTENSIONS
        self.add_files([path for path in root.rglob("*") if path.suffix.lower() in supported])

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
        self._sync_external_file_panel()

    def clear_files(self) -> None:
        self._files.clear()
        self._statuses.clear()
        self._selected_file = None
        self._refresh_file_table()
        self._sync_external_file_panel()
        window = self.window()
        if hasattr(window, "_reset_bottom_status"):
            window._reset_bottom_status()

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
        self._sync_external_file_panel()

    def get_workbench_files(self) -> list[Path]:
        return list(self._files)

    def reset_statuses(self) -> None:
        for index in range(len(self._statuses)):
            self.set_file_status(index, "待处理")

    def set_file_status(self, index: int, status: str) -> None:
        if 0 <= index < len(self._statuses):
            self._statuses[index] = status
            self._refresh_file_table(keep_selection=True)
            self._sync_external_file_panel()

    def _refresh_file_table(self, keep_selection: bool = False) -> None:
        if not self.file_table:
            self._selected_file = self._files[0] if self._files else None
            if self.file_count_label:
                self.file_count_label.setText(f"文件数量：{len(self._files)}")
            self._refresh_task_center_stats()
            self._update_preview()
            return
        current = self.file_table.currentRow() if keep_selection else 0
        self.file_table.setRowCount(0)
        scale = self.scale_combo.currentData() if self.scale_combo else 4
        for row, path in enumerate(self._files):
            self.file_table.insertRow(row)
            media_type = self._media_type(path)
            original_size = self._read_size_text(path)
            output_size = self._output_size_text(path, scale)
            values = [path.name, media_type, self._statuses[row], original_size, output_size, str(path)]
            for col, value in enumerate(values):
                self.file_table.setItem(row, col, QTableWidgetItem(value))
        if self._files:
            self.file_table.setCurrentCell(max(0, min(current, len(self._files) - 1)), 0)
        if self.file_count_label:
            self.file_count_label.setText(f"文件数量：{len(self._files)}")
        self._refresh_task_center_stats()
        self._selected_file = self._files[self.file_table.currentRow()] if self._files and self.file_table.currentRow() >= 0 else (self._files[0] if self._files else None)
        self._update_preview()

    def _refresh_task_center_stats(self) -> None:
        waiting = sum(1 for status in self._statuses if "待" in status or "等待" in status)
        running = sum(1 for status in self._statuses if ("处理中" in status or "运行中" in status) and "待" not in status)
        done = sum(1 for status in self._statuses if "完成" in status or "成功" in status)
        failed = sum(1 for status in self._statuses if "失败" in status or "错误" in status)
        if self.task_waiting_label:
            self.task_waiting_label.setText(f"等待中 {waiting}")
        if self.task_running_label:
            self.task_running_label.setText(f"处理中 {running}")
        if self.task_done_label:
            self.task_done_label.setText(f"完成 {done}")
        if self.task_failed_label:
            self.task_failed_label.setText(f"失败 {failed}")

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

    def create_task(self, files: list[Path]) -> SuperResolutionBatchTask | VideoMediaTask | AnimatedMediaTask:
        actual_files = self.get_workbench_files() or files
        workflow_mode = self._video_workflow_mode()
        if workflow_mode == "encode_only" and not actual_files:
            settings = self._collect_video_settings()
            get_tool_manager().require_tool("ffmpeg")
            if not settings.input_frame_dir or not settings.input_frame_dir.exists():
                raise ValueError("仅合成模式需要选择存在的输入帧目录。")
            self._save_video_settings(settings)
            return VideoMediaTask([settings.input_frame_dir or Path("frames")], settings)
        image_files = [path for path in actual_files if self._media_type(path) == "图片"]
        video_files = [path for path in actual_files if self._media_type(path) == "视频"]
        animated_files = [path for path in actual_files if self._media_type(path) == "动图"]
        active_types = sum(1 for group in [image_files, video_files, animated_files] if group)
        if active_types > 1:
            raise ValueError("请分开执行图片、动图和视频任务，当前版本暂不支持混合队列。")
        if animated_files:
            settings = self._collect_animated_settings()
            self._save_animated_settings(settings)
            return AnimatedMediaTask(animated_files, settings)
        if video_files:
            settings = self._collect_video_settings()
            tool_manager = get_tool_manager()
            tool_manager.require_tool("ffmpeg")
            if settings.workflow_mode != "encode_only":
                tool_manager.require_tool("ffprobe")
            if settings.interpolation_enabled:
                tool_manager.require_tool(settings.interpolation_engine)
                resolve_interpolation_model_dir(settings.interpolation_engine, settings.interpolation_model)
            if settings.upscale_enabled and settings.upscale_settings:
                validate_super_resolution_inputs(video_files[:1], settings.upscale_settings)
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
        workflow_mode = self._video_workflow_mode()
        needs_upscale = self._workflow_needs_upscale()
        needs_interpolation = self._workflow_needs_interpolation()
        input_frame_dir = Path(self.video_frame_dir_edit.text().strip()) if self.video_frame_dir_edit and self.video_frame_dir_edit.text().strip() else None
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
        if workflow_mode == "encode_only":
            if input_frame_dir is None:
                raise ValueError("仅合成模式需要选择输入帧目录。")
            if self.video_fps_spin and self.video_fps_spin.value() <= 0:
                raise ValueError("仅合成模式需要手动指定 FPS。")
        return VideoProcessSettings(
            output_dir=upscale_settings.output_dir,
            output_format="mp4",
            workflow_mode=workflow_mode,
            input_frame_dir=input_frame_dir,
            keep_audio=self.keep_audio_checkbox.isChecked() if self.keep_audio_checkbox else True,
            keep_temp=self.keep_temp_checkbox.isChecked() if self.keep_temp_checkbox else False,
            upscale_enabled=needs_upscale,
            interpolation_enabled=needs_interpolation,
            interpolation_engine=self.interpolation_engine_combo.currentData() if self.interpolation_engine_combo else "rife",
            interpolation_scale=self.interpolation_scale_combo.currentData() if self.interpolation_scale_combo else 2,
            interpolation_model=self.interpolation_model_combo.currentData() if self.interpolation_model_combo else "",
            interpolation_gpu_id=self.interpolation_gpu_edit.text() if self.interpolation_gpu_edit else "auto",
            interpolation_tta=self.interpolation_tta_checkbox.isChecked() if self.interpolation_tta_checkbox else False,
            output_fps=self.video_fps_spin.value() if self.video_fps_spin else 0.0,
            video_codec=self.config.get("video_codec", "libx264", str),
            crf=self.config.get("video_crf", 18, int),
            bitrate=self.config.get("video_bitrate", "", str),
            conflict_strategy=self.conflict_combo.currentData() if self.conflict_combo else "rename",
            upscale_settings=frame_upscale_settings if needs_upscale else None,
        )

    def _collect_animated_settings(self) -> AnimatedProcessSettings:
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
        upscale_enabled = self.upscale_enabled_checkbox.isChecked() if self.upscale_enabled_checkbox else False
        return AnimatedProcessSettings(
            output_dir=upscale_settings.output_dir,
            output_format=self.animated_format_combo.currentData() if self.animated_format_combo else "gif",
            keep_temp=self.keep_temp_checkbox.isChecked() if self.keep_temp_checkbox else False,
            enable_upscale=upscale_enabled,
            output_fps=self.animated_fps_spin.value() if self.animated_fps_spin else 0.0,
            preserve_loop=self.preserve_loop_checkbox.isChecked() if self.preserve_loop_checkbox else True,
            conflict_strategy=self.conflict_combo.currentData() if self.conflict_combo else "rename",
            upscale_settings=frame_upscale_settings if upscale_enabled else None,
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
        self.config.set("video_workflow_mode", settings.workflow_mode)
        self.config.set("video_input_frame_dir", str(settings.input_frame_dir or ""))
        self.config.set("upscale_enabled", settings.upscale_enabled)
        self.config.set("keep_audio", settings.keep_audio)
        self.config.set("keep_temp", settings.keep_temp)
        self.config.set("interpolation_enabled", settings.interpolation_enabled)
        self.config.set("interpolation_engine", settings.interpolation_engine)
        self.config.set("interpolation_scale", settings.interpolation_scale)
        self.config.set("interpolation_model", settings.interpolation_model)
        self.config.set("interpolation_gpu_id", settings.interpolation_gpu_id)
        self.config.set("interpolation_tta", settings.interpolation_tta)
        self.config.set("video_output_fps", settings.output_fps)

    def _save_animated_settings(self, settings: AnimatedProcessSettings) -> None:
        if settings.upscale_settings:
            self._save_settings(settings.upscale_settings)
        self.config.set("upscale_enabled", settings.enable_upscale)
        self.config.set("animated_output_format", settings.output_format)
        self.config.set("animated_output_fps", settings.output_fps)
        self.config.set("animated_preserve_loop", settings.preserve_loop)
        self.config.set("keep_temp", settings.keep_temp)

    def update_file_context(self, files: list[Path], selected_file: Path | None, logger: Callable[[str], None] | None = None) -> None:
        if self._syncing_external_file_panel:
            self._update_preview(logger)
            return
        statuses_by_path = {path.resolve(): self._statuses[index] for index, path in enumerate(self._files)}
        self._files = list(files)
        self._statuses = [statuses_by_path.get(path.resolve(), "待处理") for path in self._files]
        self._selected_file = selected_file if selected_file in self._files else (self._files[0] if self._files else None)
        self._refresh_file_table(keep_selection=True)
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

    def _open_log_dir_from_page(self) -> None:
        log_dir = Path.cwd() / "reports"
        log_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir.resolve())))

    def _clear_media_cache_from_page(self) -> None:
        removed, released = clear_media_task_cache()
        message = f"已清理媒体缓存：{removed} 个任务目录，释放 {format_bytes(released)}。"
        if self.output_info_label:
            self.output_info_label.setText(message)

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

    def _video_probe_preview(self, path: Path) -> tuple[int, int, float, int]:
        probe_data = probe_media(path)
        width = 0
        height = 0
        frames = 0
        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") != "video":
                continue
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
            value = stream.get("nb_frames") or stream.get("nb_read_frames")
            if value and str(value).isdigit():
                frames = int(value)
            break
        fps = media_fps(probe_data) or 0.0
        if not frames:
            duration = float(probe_data.get("format", {}).get("duration") or 0)
            frames = int(duration * fps) if duration and fps else 0
        return width, height, fps, frames

    def _frame_dir_preview(self, frame_dir: Path) -> tuple[int, int, int]:
        frames = sorted(frame_dir.glob("*.png")) if frame_dir.exists() else []
        width = 0
        height = 0
        if frames:
            try:
                width, height, _fmt = read_image_info(frames[0])
            except Exception:
                width = 0
                height = 0
        return width, height, len(frames)

    def _estimated_video_temp_text(self, width: int, height: int, input_frames: int, output_frames: int, scale: int) -> str:
        if width <= 0 or height <= 0 or input_frames <= 0:
            return "估算中"
        estimated = estimate_frame_bytes(width, height, input_frames, 1, 1.5)
        if self._workflow_needs_upscale():
            estimated += estimate_frame_bytes(width, height, input_frames, scale, 1.4)
        if self._workflow_needs_interpolation():
            estimated += estimate_frame_bytes(width, height, output_frames, scale, 1.3)
        return f"{format_bytes(estimated)}（仅供参考）"

    def _video_summary_text(
        self,
        selected: Path | None,
        width: int,
        height: int,
        input_fps: float,
        input_frames: int,
    ) -> tuple[str, str]:
        mode = self._video_workflow_mode()
        needs_upscale = self._workflow_needs_upscale()
        needs_interpolation = self._workflow_needs_interpolation()
        scale = int(self.scale_combo.currentData() if self.scale_combo and self.scale_combo.currentData() else 1)
        upscale_scale = scale if needs_upscale else 1
        interpolation_scale = int(self.interpolation_scale_combo.currentData() if self.interpolation_scale_combo else 2)
        auto_fps = input_fps * interpolation_scale if needs_interpolation and input_fps else input_fps
        manual_fps = self.video_fps_spin.value() if self.video_fps_spin else 0.0
        output_fps = min(auto_fps, manual_fps) if manual_fps > 0 and auto_fps > 0 else (manual_fps if mode == "encode_only" and manual_fps > 0 else auto_fps)
        output_frames = input_frames * interpolation_scale if needs_interpolation and input_frames else input_frames
        output_width = width * upscale_scale if width else 0
        output_height = height * upscale_scale if height else 0
        output_size = f"{output_width} x {output_height}" if output_width and output_height else "未知"
        input_size = f"{width} x {height}" if width and height else "未知"
        input_fps_text = f"{input_fps:.3f}" if input_fps else "未知"
        output_fps_text = f"{output_fps:.3f}" if output_fps else "未知"
        input_frames_text = str(input_frames) if input_frames else "未知"
        output_frames_text = str(output_frames) if output_frames else "未知"
        temp_text = self._estimated_video_temp_text(width, height, max(1, input_frames), max(1, output_frames), upscale_scale)
        upscale_engine = self.engine_combo.currentText() if needs_upscale and self.engine_combo else "不执行"
        upscale_model = self.model_combo.currentText() if needs_upscale and self.model_combo else "不执行"
        interpolation_engine = self.interpolation_engine_combo.currentText() if needs_interpolation and self.interpolation_engine_combo else "不执行"
        interpolation_model = self.interpolation_model_combo.currentText() if needs_interpolation and self.interpolation_model_combo else "不执行"
        keep_audio = "是" if self.keep_audio_checkbox and self.keep_audio_checkbox.isEnabled() and self.keep_audio_checkbox.isChecked() else "否"
        source_text = selected.name if selected else (str(self.video_frame_dir_edit.text()).strip() if self.video_frame_dir_edit else "")
        size_text = (
            f"当前参考：{source_text or '未选择'}\n"
            f"输入：{input_size} / FPS {input_fps_text} / {input_frames_text} 帧\n"
            f"输出：{output_size} / FPS {output_fps_text} / 预计 {output_frames_text} 帧\n"
            f"超分倍率：{upscale_scale}x\n插帧倍率：{interpolation_scale if needs_interpolation else 1}x\n"
            f"处理模式：{self._workflow_label()}"
        )
        summary_text = (
            f"任务摘要：\n"
            f"工作流：{self._workflow_label()}\n"
            f"超分引擎：{upscale_engine}\n"
            f"超分模型：{upscale_model}\n"
            f"插帧引擎：{interpolation_engine}\n"
            f"插帧模型：{interpolation_model}\n"
            f"输出 FPS：{output_fps_text}\n"
            f"输出尺寸：{output_size}\n"
            f"保留音频：{keep_audio}\n"
            f"预计临时空间：{temp_text}"
        )
        return size_text, summary_text

    def _refresh_preview(self, *_args: object) -> None:
        self._update_preview()

    def _update_preview(self, logger: Callable[[str], None] | None = None) -> None:
        if logger is not None and not callable(logger):
            logger = None
        if not self.size_label or not self.output_info_label:
            return
        if self.workflow_preview_label:
            self.workflow_preview_label.setText(self._workflow_preview_text())
        if self.task_summary_label:
            self.task_summary_label.setText("")
        if not self._files:
            if self._video_workflow_mode() == "encode_only" and self.video_frame_dir_edit and self.video_frame_dir_edit.text().strip():
                frame_dir = Path(self.video_frame_dir_edit.text().strip())
                fps = self.video_fps_spin.value() if self.video_fps_spin else 0
                width, height, frames = self._frame_dir_preview(frame_dir)
                size_text, summary_text = self._video_summary_text(None, width, height, fps, frames)
                self.size_label.setText(size_text)
                if self.task_summary_label:
                    self.task_summary_label.setText(summary_text)
                self.output_info_label.setText("仅合成模式不会拆帧、超分或插帧；将直接把输入帧目录合成为视频。")
                return
            self.size_label.setText("请添加图片、动图或视频文件。")
            self.output_info_label.setText("文件大小受内容、格式、倍率、质量和编码影响较大，仅供参考。")
            return
        selected = self._selected_file or self._files[0]
        media_type = self._media_type(selected)
        if media_type == "动图":
            try:
                info = read_animated_info(selected)
                scale = self.scale_combo.currentData() if self.scale_combo else 4
                upscale_enabled = self.upscale_enabled_checkbox.isChecked() if self.upscale_enabled_checkbox else False
                output_width = info.width * int(scale) if upscale_enabled else info.width
                output_height = info.height * int(scale) if upscale_enabled else info.height
                output_format = self.animated_format_combo.currentData() if self.animated_format_combo else "gif"
                output_fps = self.animated_fps_spin.value() if self.animated_fps_spin else 0.0
                fps_text = f"{info.fps:.3f}" if info.fps else "按帧延迟"
                output_fps_text = f"{output_fps:.3f}" if output_fps > 0 else "保留原帧延迟"
                self.size_label.setText(
                    f"文件数量：{len(self._files)}\n当前参考动图：{selected.name}\n"
                    f"格式：{info.input_format}\n原始尺寸：{info.width} x {info.height}\n"
                    f"帧数：{info.frame_count}\nFPS：{fps_text}\n时长：{info.duration_ms / 1000:.2f}s\n"
                    f"循环次数：{info.loop_count}\n透明通道：{'是' if info.has_alpha else '否'}\n"
                    f"预计输出尺寸：{output_width} x {output_height}"
                )
                self.output_info_label.setText(
                    f"动图输出格式：{str(output_format).upper()}\n输出 FPS：{output_fps_text}\n"
                    f"处理模式：{'逐帧 AI 超分' if upscale_enabled else '不处理，仅重新合成'}\n"
                    f"文件大小受帧数、透明通道、格式、调色板和质量影响较大，仅供参考。"
                )
            except Exception as exc:
                self.size_label.setText(f"当前参考文件：{selected.name}\n动图读取失败：{exc}")
                self.output_info_label.setText("请确认文件是 GIF、动态 WebP 或 APNG。静态图片不会作为动图处理。")
                if logger:
                    logger(f"动图读取失败：{selected.name}，原因：{exc}")
            return
        if media_type != "图片":
            workflow_mode = self._video_workflow_mode()
            interpolation_enabled = self._workflow_needs_interpolation()
            interpolation_scale = self.interpolation_scale_combo.currentData() if self.interpolation_scale_combo else 2
            upscale_enabled = self._workflow_needs_upscale()
            width = 0
            height = 0
            input_fps = 0.0
            input_frames = 0
            if media_type == "视频":
                try:
                    width, height, input_fps, input_frames = self._video_probe_preview(selected)
                except Exception as exc:
                    if logger:
                        logger(f"视频预览读取失败：{selected.name}，原因：{exc}")
            size_text, summary_text = self._video_summary_text(selected, width, height, input_fps, input_frames)
            self.size_label.setText(size_text)
            if self.task_summary_label:
                self.task_summary_label.setText(summary_text)
            engine_hint = self._interpolation_engine_hint() if interpolation_enabled else ""
            self.output_info_label.setText(
                f"{engine_hint}\n视频输出大小受帧数、编码、插帧倍率、超分倍率和音频保留影响较大，仅供参考。".strip()
            )
            if self.interpolation_preview_label:
                self.interpolation_preview_label.setText(self._interpolation_engine_hint())
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
        media_type = self._media_type(path)
        if media_type == "动图":
            try:
                info = read_animated_info(path)
                return f"{info.width} x {info.height} / {info.frame_count} 帧"
            except Exception:
                return "读取失败"
        if media_type != "图片":
            return "后续识别"
        try:
            width, height, _fmt = read_image_info(path)
            return f"{width} x {height}"
        except Exception:
            return "读取失败"

    def _output_size_text(self, path: Path, scale: int) -> str:
        media_type = self._media_type(path)
        if media_type == "动图":
            try:
                info = read_animated_info(path)
                upscale_enabled = self.upscale_enabled_checkbox.isChecked() if self.upscale_enabled_checkbox else False
                applied_scale = int(scale) if upscale_enabled else 1
                return f"{info.width * applied_scale} x {info.height * applied_scale} / {info.frame_count} 帧"
            except Exception:
                return "未知"
        if media_type != "图片":
            return "后续计算"
        try:
            width, height, _fmt = read_image_info(path)
            return f"{width * int(scale)} x {height * int(scale)}"
        except Exception:
            return "未知"

    def _media_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in ANIMATED_EXTENSIONS:
            if is_animated_image(path):
                return "动图"
            if suffix in IMAGE_EXTENSIONS:
                return "图片"
        if suffix in IMAGE_EXTENSIONS:
            return "图片"
        if suffix in VIDEO_EXTENSIONS:
            return "视频"
        return "未知"
