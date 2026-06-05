from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from image_toolbox.core.engine_settings import EngineSettings, ModelSettings, get_engine_settings_store
from image_toolbox.core.media_task_utils import format_bytes
from image_toolbox.core.model_library import (
    detect_external_dependencies,
    import_custom_model,
    list_interpolation_model_info,
    migrate_model_library,
)
from image_toolbox.core.paths import get_engine_models_dir, get_models_root, get_video_interpolation_models_dir
from image_toolbox.core.tool_manager import get_tool_manager
from image_toolbox.core.upscale_engines import DEFAULT_ENGINE_MANAGER
from image_toolbox.ui.widgets import NoWheelComboBox as QComboBox
from image_toolbox.ui.widgets import NoWheelSpinBox as QSpinBox


ENGINE_TAB_ORDER = ["waifu2x", "anime4k", "realesrgan", "realcugan", "srmd", "realsr"]
VIDEO_INTERPOLATION_TAB_ORDER = ["rife", "ifrnet", "cain", "dain"]
VIDEO_INTERPOLATION_DISPLAY = {
    "rife": "RIFE",
    "ifrnet": "IFRNet",
    "cain": "CAIN",
    "dain": "DAIN",
}
VIDEO_INTERPOLATION_HINTS = {
    "rife": "推荐使用 rife-v4.6，适合通用视频插帧。",
    "ifrnet": "适合高质量插帧，速度通常比轻量模型慢。",
    "cain": "兼容性较好；当前命令行不支持 TTA。",
    "dain": "经典插帧方案，速度较慢，建议先用短片测试；不支持 TTA。",
}


class EngineSettingsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.store = get_engine_settings_store()
        self.widgets: dict[str, dict[str, Any]] = {}
        self.video_widgets: dict[str, dict[str, Any]] = {}
        self.default_image_combo: QComboBox | None = None
        self.default_animated_combo: QComboBox | None = None
        self.default_video_combo: QComboBox | None = None
        self.default_interpolation_combo: QComboBox | None = None
        self.image_threads_spin: QSpinBox | None = None
        self.animated_threads_spin: QSpinBox | None = None
        self.video_threads_spin: QSpinBox | None = None
        self.gpu_id_edit: QLineEdit | None = None
        self.multi_gpu_checkbox: QCheckBox | None = None
        self.multi_gpu_id_edit: QLineEdit | None = None
        self.multi_gpu_tile_spin: QSpinBox | None = None
        self.status_label: QLabel | None = None
        self.tabs: QTabWidget | None = None
        self.video_tabs: QTabWidget | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("引擎设置")
        title.setObjectName("PanelTitle")
        hint = QLabel("管理默认处理引擎、项目模型库、图片超分引擎和视频插帧引擎。")
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self._build_top_bar())
        layout.addWidget(self._build_model_library_bar())

        image_group = QGroupBox("图片超分引擎")
        image_layout = QVBoxLayout(image_group)
        self.tabs = QTabWidget()
        engines = {engine.engine_id: engine for engine in DEFAULT_ENGINE_MANAGER.list_engines()}
        for engine_id in ENGINE_TAB_ORDER:
            if engine_id in engines:
                self.tabs.addTab(self._build_engine_tab(engines[engine_id]), engines[engine_id].display_name)
        image_layout.addWidget(self.tabs)
        layout.addWidget(image_group, 2)

        video_group = QGroupBox("视频插帧引擎")
        video_layout = QVBoxLayout(video_group)
        self.video_tabs = QTabWidget()
        for engine_id in VIDEO_INTERPOLATION_TAB_ORDER:
            self.video_tabs.addTab(self._build_interpolation_engine_tab(engine_id), VIDEO_INTERPOLATION_DISPLAY[engine_id])
        video_layout.addWidget(self.video_tabs)
        layout.addWidget(video_group, 1)
        layout.addWidget(self._build_bottom_bar())

    def _build_top_bar(self) -> QWidget:
        group = QGroupBox("默认处理引擎")
        row = QHBoxLayout(group)
        row.setSpacing(12)
        self.default_image_combo = QComboBox()
        for engine in DEFAULT_ENGINE_MANAGER.list_engines():
            self.default_image_combo.addItem(engine.display_name, engine.engine_id)
        self.default_image_combo.setCurrentIndex(max(0, self.default_image_combo.findData(self.store.global_settings.default_image_engine)))
        self.default_animated_combo = QComboBox()
        self.default_video_combo = QComboBox()
        for combo, default_value in [
            (self.default_animated_combo, self.store.global_settings.default_animated_engine or self.store.global_settings.default_image_engine),
            (self.default_video_combo, self.store.global_settings.default_video_engine or self.store.global_settings.default_image_engine),
        ]:
            for engine in DEFAULT_ENGINE_MANAGER.list_engines():
                combo.addItem(engine.display_name, engine.engine_id)
            combo.setCurrentIndex(max(0, combo.findData(default_value)))
        self.default_interpolation_combo = QComboBox()
        for engine_id in VIDEO_INTERPOLATION_TAB_ORDER:
            self.default_interpolation_combo.addItem(VIDEO_INTERPOLATION_DISPLAY[engine_id], engine_id)
        self.default_interpolation_combo.setCurrentIndex(
            max(0, self.default_interpolation_combo.findData(self.store.global_settings.default_video_interpolation_engine))
        )
        optimize_button = QPushButton("优化设定")
        optimize_button.setEnabled(False)
        help_button = QPushButton("帮助")
        help_button.setEnabled(False)
        row.addWidget(QLabel("图片"))
        row.addWidget(self.default_image_combo, 1)
        row.addWidget(QLabel("动态图片"))
        row.addWidget(self.default_animated_combo, 1)
        row.addWidget(QLabel("视频超分"))
        row.addWidget(self.default_video_combo, 1)
        row.addWidget(QLabel("视频插帧"))
        row.addWidget(self.default_interpolation_combo, 1)
        row.addWidget(optimize_button)
        row.addWidget(help_button)
        return group

    def _build_model_library_bar(self) -> QWidget:
        group = QGroupBox("项目模型库")
        row = QHBoxLayout(group)
        path_label = QLabel(f"项目模型库：{get_models_root()}")
        path_label.setObjectName("MutedText")
        open_button = QPushButton("打开模型库")
        migrate_button = QPushButton("迁移模型库")
        check_button = QPushButton("检查外部依赖")
        import_button = QPushButton("导入当前引擎模型")
        restore_button = QPushButton("恢复当前引擎默认路径")
        open_button.clicked.connect(self._open_model_library)
        migrate_button.clicked.connect(self._migrate_model_library)
        check_button.clicked.connect(self._check_external_dependencies)
        import_button.clicked.connect(self._import_current_engine_model)
        restore_button.clicked.connect(lambda: self._restore_default_model_dir(self._current_engine_id()))
        row.addWidget(path_label, 1)
        row.addWidget(open_button)
        row.addWidget(migrate_button)
        row.addWidget(check_button)
        row.addWidget(import_button)
        row.addWidget(restore_button)
        return group

    def _build_engine_tab(self, engine) -> QWidget:
        settings = self.store.get_engine(engine.engine_id)
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(14)
        outer.setWidget(content)

        status_group = QGroupBox(f"{engine.display_name} 基础设置")
        form = QFormLayout(status_group)
        enabled = QCheckBox("启用该引擎")
        enabled.setChecked(settings.enabled)
        status = QLabel(self._status_text(engine, settings))
        status.setObjectName("MutedText")
        status.setWordWrap(True)
        exe_edit = QLineEdit(settings.executable_path or str(engine.executable_path))
        model_dir = self._engine_model_root(engine)
        model_edit = QLineEdit(settings.model_dir or (str(model_dir) if model_dir else ""))
        form.addRow("引擎状态", status)
        form.addRow("启用", enabled)
        form.addRow("引擎程序", self._path_row(exe_edit, "file"))
        form.addRow("模型目录", self._path_row(model_edit, "dir"))
        form.addRow("推荐场景", QLabel(engine.recommendation()))
        layout.addWidget(status_group)

        defaults_group = QGroupBox("默认参数")
        params = QFormLayout(defaults_group)
        model_combo = QComboBox()
        scale_combo = QComboBox()
        for scale in engine.supported_scales:
            scale_combo.addItem(f"{scale}x", scale)
        scale_combo.setCurrentIndex(max(0, scale_combo.findData(settings.default_scale or (engine.supported_scales[0] if engine.supported_scales else 0))))
        tile_spin = QSpinBox()
        tile_spin.setRange(0, 2048)
        tile_spin.setSingleStep(128)
        tile_spin.setValue(settings.default_tile)
        tile_spin.setEnabled(engine.supports_tile)
        tta_checkbox = QCheckBox("启用 TTA 增强，速度会更慢")
        tta_checkbox.setChecked(bool(settings.extra_params.get("use_tta", False)))
        gpu_edit = QLineEdit(str(settings.extra_params.get("gpu_id", self.store.global_settings.gpu_id)))
        low_memory = QCheckBox("默认低显存模式")
        low_memory.setChecked(settings.low_memory_default)
        low_memory.setEnabled(engine.supports_tile)
        noise_combo = QComboBox()
        for option in engine.get_noise_options():
            noise_combo.addItem(option.label, option.value)
        noise_combo.setEnabled(engine.supports_noise and noise_combo.count() > 0)
        noise_combo.setCurrentIndex(max(0, noise_combo.findData(settings.default_noise_level)))
        syncgap_combo = QComboBox()
        for option in engine.get_syncgap_options():
            syncgap_combo.addItem(option.label, option.value)
        syncgap_combo.setEnabled(engine.supports_syncgap and syncgap_combo.count() > 0)
        syncgap_combo.setCurrentIndex(max(0, syncgap_combo.findData(settings.syncgap_mode)))
        format_combo = QComboBox()
        for label, value in [("保留原格式", "original"), ("PNG", "png"), ("JPG", "jpg"), ("WEBP", "webp")]:
            format_combo.addItem(label, value)
        format_combo.setCurrentIndex(max(0, format_combo.findData(settings.default_output_format)))
        params.addRow("默认模型", model_combo)
        params.addRow("默认倍率", scale_combo)
        params.addRow("块大小 Tile（0=自动）", tile_spin)
        params.addRow("GPU ID", self._gpu_row(gpu_edit))
        params.addRow("低显存", low_memory)
        params.addRow("默认输出格式", format_combo)
        layout.addWidget(defaults_group)

        advanced_group = QGroupBox("高级参数")
        advanced_group.setCheckable(True)
        advanced_group.setChecked(False)
        advanced = QFormLayout(advanced_group)
        advanced.addRow("TTA", tta_checkbox)
        advanced.addRow("默认降噪", noise_combo)
        advanced.addRow("SyncGap", syncgap_combo)
        self._add_engine_specific_rows(engine.engine_id, advanced, settings)
        self._make_collapsible(advanced_group, False)
        layout.addWidget(advanced_group)

        models_group = QGroupBox("模型管理")
        models_layout = QVBoxLayout(models_group)
        buttons = QHBoxLayout()
        scan_button = QPushButton("扫描模型")
        test_button = QPushButton("测试引擎")
        save_button = QPushButton("保存设置")
        buttons.addWidget(scan_button)
        buttons.addWidget(test_button)
        buttons.addStretch()
        buttons.addWidget(save_button)
        table = QTableWidget(0, 8)
        table.setHorizontalHeaderLabels(["启用", "默认", "模型名称", "模型路径", "备注", "质量", "速度", "显存"])
        table.verticalHeader().setVisible(False)
        models_layout.addLayout(buttons)
        models_layout.addWidget(table)
        layout.addWidget(models_group, 1)

        self.widgets[engine.engine_id] = {
            "enabled": enabled,
            "status": status,
            "exe": exe_edit,
            "model_dir": model_edit,
            "model_combo": model_combo,
            "scale_combo": scale_combo,
            "tile": tile_spin,
            "tta": tta_checkbox,
            "gpu": gpu_edit,
            "low_memory": low_memory,
            "noise": noise_combo,
            "syncgap": syncgap_combo,
            "format": format_combo,
            "table": table,
        }
        scan_button.clicked.connect(lambda _checked=False, e=engine: self.scan_models(e.engine_id))
        test_button.clicked.connect(lambda _checked=False, e=engine, label=status: self._test_engine(e, label))
        save_button.clicked.connect(self.save_settings)
        self.scan_models(engine.engine_id)
        return outer

    def _make_collapsible(self, group: QGroupBox, expanded: bool = False) -> None:
        group.setCheckable(True)
        group.setChecked(expanded)

        def update(checked: bool) -> None:
            for child in group.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
                child.setVisible(checked)

        group.toggled.connect(update)
        update(expanded)

    def _build_interpolation_engine_tab(self, engine_id: str) -> QWidget:
        settings = self.store.get_engine(engine_id)
        manager = get_tool_manager()
        health = manager.check_tool(engine_id)
        models = list_interpolation_model_info(engine_id)
        model_root = get_video_interpolation_models_dir(engine_id)
        display_name = VIDEO_INTERPOLATION_DISPLAY[engine_id]

        outer = QScrollArea()
        outer.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(14)
        outer.setWidget(content)

        basic_group = QGroupBox(f"{display_name} 基础设置")
        basic = QFormLayout(basic_group)
        enabled = QCheckBox("启用该插帧引擎")
        enabled.setChecked(settings.enabled)
        status_text = "可用" if health.available else f"不可用：{health.reason or '缺少可执行文件，请到工具管理中配置'}"
        model_status = "模型可用" if any(model.available for model in models) else "缺少模型，请导入模型到项目模型库"
        status = QLabel(f"{status_text}\n{model_status}")
        status.setObjectName("MutedText")
        status.setWordWrap(True)
        exe_edit = QLineEdit(settings.executable_path or (str(health.path) if health.path else ""))
        exe_edit.setPlaceholderText("缺 exe 时请到工具管理中配置，或在这里选择后保存。")
        configured_model_dir = Path(settings.model_dir) if settings.model_dir else model_root
        if "video_interpolation" not in configured_model_dir.as_posix():
            configured_model_dir = model_root
            settings.model_dir = str(model_root)
        model_edit = QLineEdit(str(configured_model_dir))
        model_edit.setReadOnly(True)
        model_edit.setToolTip("视频插帧模型必须位于项目模型库，运行时不会引用外部素材库。")
        basic.addRow("启用", enabled)
        basic.addRow("引擎状态", status)
        basic.addRow("exe 路径", self._path_row(exe_edit, "file"))
        basic.addRow("模型目录", model_edit)
        basic.addRow("推荐场景", QLabel(VIDEO_INTERPOLATION_HINTS[engine_id]))
        layout.addWidget(basic_group)

        defaults_group = QGroupBox("默认参数")
        defaults = QFormLayout(defaults_group)
        model_combo = QComboBox()
        for model in models:
            label = model.name or "默认模型目录"
            suffix = "" if model.available else "（缺少模型文件）"
            model_combo.addItem(label + suffix, model.name)
        if model_combo.count() == 0:
            model_combo.addItem("未导入模型", "")
        model_combo.setCurrentIndex(max(0, model_combo.findData(settings.default_model)))
        scale_combo = QComboBox()
        for scale in [2, 4]:
            scale_combo.addItem(f"{scale}x", scale)
        scale_combo.setCurrentIndex(max(0, scale_combo.findData(settings.default_scale or 2)))
        gpu_edit = QLineEdit(str(settings.extra_params.get("gpu_id", self.store.global_settings.gpu_id)))
        tta_checkbox = QCheckBox("启用 TTA")
        tta_supported = engine_id not in {"cain", "dain"}
        tta_checkbox.setChecked(bool(settings.extra_params.get("use_tta", False)) and tta_supported)
        tta_checkbox.setEnabled(tta_supported)
        if not tta_supported:
            tta_checkbox.setToolTip(f"{display_name} 当前不支持 TTA，任务会忽略该参数。")
        defaults.addRow("默认模型", model_combo)
        defaults.addRow("默认插帧倍率", scale_combo)
        defaults.addRow("GPU ID", gpu_edit)
        defaults.addRow("TTA", tta_checkbox)
        layout.addWidget(defaults_group)

        advanced_group = QGroupBox("高级参数")
        advanced = QFormLayout(advanced_group)
        threads_edit = QLineEdit(str(settings.extra_params.get("threads", "")))
        threads_edit.setPlaceholderText("预留：后续版本接入")
        threads_edit.setEnabled(False)
        multi_gpu = QCheckBox("多显卡（后续版本支持）")
        multi_gpu.setEnabled(False)
        advanced.addRow("线程", threads_edit)
        advanced.addRow("多显卡", multi_gpu)
        advanced.addRow("说明", QLabel("插帧高级参数默认折叠；不支持的参数会保持禁用。"))
        self._make_collapsible(advanced_group, False)
        layout.addWidget(advanced_group)

        models_group = QGroupBox("模型列表")
        models_layout = QVBoxLayout(models_group)
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["模型", "路径", "文件数", "大小", "状态"])
        table.verticalHeader().setVisible(False)
        for model in models:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(model.name or "默认模型目录"))
            table.setItem(row, 1, QTableWidgetItem(str(model.path)))
            table.setItem(row, 2, QTableWidgetItem(str(model.file_count)))
            table.setItem(row, 3, QTableWidgetItem(format_bytes(model.size_bytes)))
            table.setItem(row, 4, QTableWidgetItem("可用" if model.available else "缺少模型文件"))
        table.resizeColumnsToContents()
        models_layout.addWidget(table)
        layout.addWidget(models_group)

        self.video_widgets[engine_id] = {
            "enabled": enabled,
            "status": status,
            "exe": exe_edit,
            "model_dir": model_edit,
            "model_combo": model_combo,
            "scale_combo": scale_combo,
            "gpu": gpu_edit,
            "tta": tta_checkbox,
            "table": table,
        }
        return outer

    def _add_engine_specific_rows(self, engine_id: str, form: QFormLayout, settings: EngineSettings) -> None:
        if engine_id == "realesrgan":
            photo_model = QComboBox()
            anime_model = QComboBox()
            force_x4 = QCheckBox("强制 x4 / x2 相关选项（后续版本支持）")
            imported_model = QCheckBox("使用导入的模型（后续版本支持）")
            import_button = QPushButton("导入模型文件")
            select_button = QPushButton("选择模型")
            native_scale = QSpinBox()
            native_scale.setRange(1, 8)
            native_scale.setValue(int(settings.extra_params.get("native_scale", 4)))
            for widget in [force_x4, imported_model, import_button, select_button, native_scale]:
                widget.setEnabled(False)
            form.addRow("3D 写实模型", photo_model)
            form.addRow("2D 动漫模型", anime_model)
            form.addRow("强制倍率", force_x4)
            form.addRow("导入模型", imported_model)
            form.addRow("导入模型文件", import_button)
            form.addRow("选择模型", select_button)
            form.addRow("原生放大倍率", native_scale)
        elif engine_id == "waifu2x":
            version_combo = QComboBox()
            version_combo.addItems(["最新版", "兼容版"])
            version_combo.setEnabled(False)
            form.addRow("版本选择", version_combo)
        elif engine_id == "anime4k":
            for label in ["ACNet", "HDN 模式", "快速模式", "GPU 模式", "预处理", "后期处理"]:
                checkbox = QCheckBox(label)
                checkbox.setChecked(label in {"快速模式", "GPU 模式"})
                checkbox.setEnabled(False)
                form.addRow(label, checkbox)
            backend = QComboBox()
            backend.addItems(["OpenCL", "CUDA"])
            backend.setEnabled(False)
            passes = QSpinBox()
            passes.setRange(1, 8)
            passes.setValue(int(settings.extra_params.get("passes", 2)))
            passes.setEnabled(False)
            form.addRow("GPU 后端", backend)
            form.addRow("处理次数", passes)
        elif engine_id == "realcugan":
            always_2x = QCheckBox("总是使用 2x 模型（后续版本支持）")
            always_2x.setEnabled(False)
            form.addRow("模型策略", always_2x)

    def _build_bottom_bar(self) -> QWidget:
        group = QGroupBox("线程数量与 GPU 设置")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self.image_threads_spin = QSpinBox()
        self.image_threads_spin.setRange(1, 64)
        self.image_threads_spin.setValue(self.store.global_settings.image_threads)
        self.animated_threads_spin = QSpinBox()
        self.animated_threads_spin.setRange(1, 64)
        self.animated_threads_spin.setValue(self.store.global_settings.animated_threads)
        self.animated_threads_spin.setEnabled(False)
        self.video_threads_spin = QSpinBox()
        self.video_threads_spin.setRange(1, 64)
        self.video_threads_spin.setValue(self.store.global_settings.video_threads)
        self.video_threads_spin.setEnabled(False)
        self.gpu_id_edit = QLineEdit(self.store.global_settings.gpu_id)
        gpu_button = QPushButton("查询可用 GPU ID")
        gpu_button.setEnabled(False)
        self.multi_gpu_checkbox = QCheckBox("启用多显卡")
        self.multi_gpu_checkbox.setChecked(self.store.global_settings.multi_gpu_enabled)
        self.multi_gpu_checkbox.setEnabled(False)
        self.multi_gpu_id_edit = QLineEdit(self.store.global_settings.multi_gpu_id)
        self.multi_gpu_id_edit.setEnabled(False)
        self.multi_gpu_tile_spin = QSpinBox()
        self.multi_gpu_tile_spin.setRange(32, 2048)
        self.multi_gpu_tile_spin.setValue(self.store.global_settings.multi_gpu_tile)
        self.multi_gpu_tile_spin.setEnabled(False)
        save = QPushButton("保存全部设置")
        save.clicked.connect(self.save_settings)
        self.status_label = QLabel(f"配置文件：{self.store.path}")
        self.status_label.setObjectName("MutedText")
        self.gpu_id_edit.setMinimumWidth(140)
        self.multi_gpu_id_edit.setMinimumWidth(80)
        grid.addWidget(QLabel("图片线程"), 0, 0)
        grid.addWidget(self.image_threads_spin, 0, 1)
        grid.addWidget(QLabel("动态图片线程"), 0, 2)
        grid.addWidget(self.animated_threads_spin, 0, 3)
        grid.addWidget(QLabel("视频线程"), 0, 4)
        grid.addWidget(self.video_threads_spin, 0, 5)
        grid.addWidget(QLabel("GPU ID"), 1, 0)
        grid.addWidget(self.gpu_id_edit, 1, 1, 1, 2)
        grid.addWidget(gpu_button, 1, 3)
        grid.addWidget(self.multi_gpu_checkbox, 1, 4)
        grid.addWidget(QLabel("多显卡 ID"), 1, 5)
        grid.addWidget(self.multi_gpu_id_edit, 1, 6)
        grid.addWidget(QLabel("块大小"), 1, 7)
        grid.addWidget(self.multi_gpu_tile_spin, 1, 8)
        grid.addWidget(save, 0, 8)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(6, 1)
        return group

    def _path_row(self, edit: QLineEdit, mode: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        browse = QPushButton("选择")
        clear = QPushButton("清空")
        browse.clicked.connect(lambda: self._browse_path(edit, mode))
        clear.clicked.connect(lambda: edit.clear())
        layout.addWidget(edit, 1)
        layout.addWidget(browse)
        layout.addWidget(clear)
        return row

    def _gpu_row(self, edit: QLineEdit) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        query = QPushButton("查询可用 GPU ID")
        query.setEnabled(False)
        multi = QCheckBox("启用多显卡")
        multi.setEnabled(False)
        multi_button = QPushButton("多显卡设置")
        multi_button.setEnabled(False)
        layout.addWidget(edit)
        layout.addWidget(query)
        layout.addWidget(multi)
        layout.addWidget(multi_button)
        return row

    def _open_model_library(self) -> None:
        root = get_models_root()
        root.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(root)))

    def _migrate_model_library(self) -> None:
        source = QFileDialog.getExistingDirectory(self, "选择外部素材库根目录", str(Path.cwd()))
        if not source:
            return
        stats = migrate_model_library(Path(source), "skip")
        for engine_id, widgets in self.widgets.items():
            widgets["model_dir"].setText(str(get_engine_models_dir(engine_id)))
            self.store.get_engine(engine_id).model_dir = str(get_engine_models_dir(engine_id))
            self.scan_models(engine_id)
        self.store.save()
        message = f"迁移完成：复制 {stats.copied}，跳过 {stats.skipped}，失败 {stats.failed}"
        if self.status_label:
            self.status_label.setText(message)
        QMessageBox.information(self, "迁移模型库", message + "\n\n" + "\n".join(stats.logs[-20:]))

    def _check_external_dependencies(self) -> None:
        self.save_settings()
        try:
            import json

            data = json.loads(self.store.path.read_text(encoding="utf-8")) if self.store.path.exists() else {}
        except Exception:
            data = {}
        findings = detect_external_dependencies(data)
        if not findings:
            QMessageBox.information(self, "检查外部依赖", "未发现配置中的外部素材库模型路径。")
            return
        QMessageBox.warning(
            self,
            "检查外部依赖",
            "发现以下外部素材库路径，请迁移模型后恢复默认项目模型路径：\n\n" + "\n".join(findings[:30]),
        )

    def _restore_default_model_dir(self, engine_id: str) -> None:
        widgets = self.widgets.get(engine_id)
        if not widgets:
            return
        default_dir = get_engine_models_dir(engine_id)
        widgets["model_dir"].setText(str(default_dir))
        settings = self.store.get_engine(engine_id)
        settings.model_dir = str(default_dir)
        settings.extra_params.pop("legacy_model_dir", None)
        settings.extra_params.pop("needs_model_migration", None)
        self.store.save()
        self.scan_models(engine_id)

    def _current_engine_id(self) -> str:
        if not self.tabs:
            return ENGINE_TAB_ORDER[0]
        index = self.tabs.currentIndex()
        if 0 <= index < len(ENGINE_TAB_ORDER):
            return ENGINE_TAB_ORDER[index]
        return ENGINE_TAB_ORDER[0]

    def _import_current_engine_model(self) -> None:
        self._import_custom_model(self._current_engine_id())

    def _import_custom_model(self, engine_id: str) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "选择模型文件", str(Path.cwd()), "Model Files (*.bin *.param *.onnx *.pth *.model *.weights);;All Files (*)")
        if not selected:
            directory = QFileDialog.getExistingDirectory(self, "或选择模型文件夹", str(Path.cwd()))
            selected = directory
        if not selected:
            return
        model_id, stats = import_custom_model(engine_id, Path(selected))
        model = self.store.get_model(engine_id, model_id)
        model.display_name = model_id
        model.path = str(get_engine_models_dir(engine_id) / model_id)
        model.enabled = True
        model.note = "手动导入到项目模型库"
        self.store.save()
        self.scan_models(engine_id)
        QMessageBox.information(self, "导入模型", f"导入完成：{model_id}\n复制 {stats.copied}，跳过 {stats.skipped}，失败 {stats.failed}")

    def _browse_path(self, edit: QLineEdit, mode: str) -> None:
        if mode == "file":
            selected, _ = QFileDialog.getOpenFileName(self, "选择引擎程序", edit.text() or str(Path.cwd()), "Executable (*.exe)")
        else:
            selected = QFileDialog.getExistingDirectory(self, "选择模型目录", edit.text() or str(Path.cwd()))
        if selected:
            edit.setText(selected)

    def _engine_model_root(self, engine) -> Path | None:
        return getattr(engine, "models_path", None)

    def _status_text(self, engine, settings: EngineSettings) -> str:
        if not settings.enabled:
            return "已禁用"
        available, reason = engine.health_check()
        return f"可用：{engine.executable_path}" if available else f"不可用：{reason}"

    def _test_engine(self, engine, label: QLabel) -> None:
        if hasattr(engine, "_health_cache"):
            engine._health_cache = None
        available, reason = engine.health_check()
        label.setText(f"可用：{engine.executable_path}" if available else f"不可用：{reason}")

    def scan_models(self, engine_id: str) -> None:
        engine = DEFAULT_ENGINE_MANAGER.get_engine(engine_id)
        settings = self.store.get_engine(engine_id)
        widgets = self.widgets[engine_id]
        table: QTableWidget = widgets["table"]
        combo: QComboBox = widgets["model_combo"]
        models = engine.scan_models()
        table.setRowCount(0)
        combo.clear()
        for model in models:
            model_settings = settings.models.get(model.name) or ModelSettings(
                model_id=model.name,
                display_name=model.display_name,
                path=str(engine.get_model_path(model.name) or ""),
                recommended_use=model.description,
            )
            settings.models[model.name] = model_settings
            row = table.rowCount()
            table.insertRow(row)
            values = [
                QTableWidgetItem(),
                QTableWidgetItem(),
                QTableWidgetItem(model.display_name or model.name),
                QTableWidgetItem(model_settings.path or str(engine.get_model_path(model.name) or "")),
                QTableWidgetItem(model_settings.note),
                QTableWidgetItem(str(model_settings.quality_score)),
                QTableWidgetItem(str(model_settings.speed_score)),
                QTableWidgetItem(str(model_settings.memory_score)),
            ]
            values[0].setCheckState(Qt.CheckState.Checked if model_settings.enabled else Qt.CheckState.Unchecked)
            values[1].setCheckState(Qt.CheckState.Checked if model_settings.is_default or settings.default_model == model.name else Qt.CheckState.Unchecked)
            values[2].setData(Qt.ItemDataRole.UserRole, model.name)
            for col, item in enumerate(values):
                table.setItem(row, col, item)
            if model_settings.enabled:
                combo.addItem(model.display_name or model.name, model.name)
        combo.setCurrentIndex(max(0, combo.findData(settings.default_model or (models[0].name if models else ""))))
        table.resizeColumnsToContents()

    def save_settings(self) -> None:
        if self.default_image_combo:
            self.store.global_settings.default_image_engine = self.default_image_combo.currentData() or "realesrgan"
        if self.default_animated_combo:
            self.store.global_settings.default_animated_engine = self.default_animated_combo.currentData() or self.store.global_settings.default_image_engine
        if self.default_video_combo:
            self.store.global_settings.default_video_engine = self.default_video_combo.currentData() or self.store.global_settings.default_image_engine
        if self.default_interpolation_combo:
            self.store.global_settings.default_video_interpolation_engine = self.default_interpolation_combo.currentData() or "rife"
        if self.image_threads_spin:
            self.store.global_settings.image_threads = self.image_threads_spin.value()
        if self.animated_threads_spin:
            self.store.global_settings.animated_threads = self.animated_threads_spin.value()
        if self.video_threads_spin:
            self.store.global_settings.video_threads = self.video_threads_spin.value()
        if self.gpu_id_edit:
            self.store.global_settings.gpu_id = self.gpu_id_edit.text().strip() or "auto"
        if self.multi_gpu_checkbox:
            self.store.global_settings.multi_gpu_enabled = self.multi_gpu_checkbox.isChecked()
        if self.multi_gpu_id_edit:
            self.store.global_settings.multi_gpu_id = self.multi_gpu_id_edit.text().strip() or "0"
        if self.multi_gpu_tile_spin:
            self.store.global_settings.multi_gpu_tile = self.multi_gpu_tile_spin.value()
        for engine in DEFAULT_ENGINE_MANAGER.list_engines():
            if engine.engine_id not in self.widgets:
                continue
            widgets = self.widgets[engine.engine_id]
            settings = self.store.get_engine(engine.engine_id)
            settings.enabled = widgets["enabled"].isChecked()
            settings.executable_path = widgets["exe"].text().strip()
            configured_model_dir = Path(widgets["model_dir"].text().strip() or str(get_engine_models_dir(engine.engine_id)))
            if configured_model_dir.resolve().is_relative_to(get_models_root().resolve()):
                settings.model_dir = str(configured_model_dir)
            else:
                settings.extra_params["legacy_model_dir"] = str(configured_model_dir)
                settings.extra_params["needs_model_migration"] = True
                settings.model_dir = str(get_engine_models_dir(engine.engine_id))
                widgets["model_dir"].setText(settings.model_dir)
            settings.default_model = widgets["model_combo"].currentData() or ""
            settings.default_scale = widgets["scale_combo"].currentData() or 0
            settings.default_tile = widgets["tile"].value()
            settings.low_memory_default = widgets["low_memory"].isChecked()
            settings.default_output_format = widgets["format"].currentData() or "original"
            settings.default_noise_level = widgets["noise"].currentData() if widgets["noise"].currentData() is not None else 0
            settings.syncgap_mode = widgets["syncgap"].currentData() if widgets["syncgap"].currentData() is not None else 2
            settings.extra_params["use_tta"] = widgets["tta"].isChecked()
            settings.extra_params["gpu_id"] = widgets["gpu"].text().strip() or self.store.global_settings.gpu_id
            table: QTableWidget = widgets["table"]
            first_enabled = ""
            checked_default = ""
            for row in range(table.rowCount()):
                name_item = table.item(row, 2)
                if not name_item:
                    continue
                model_id = name_item.data(Qt.ItemDataRole.UserRole)
                enabled = table.item(row, 0).checkState() == Qt.CheckState.Checked
                is_default = table.item(row, 1).checkState() == Qt.CheckState.Checked
                if enabled and not first_enabled:
                    first_enabled = model_id
                if enabled and is_default:
                    checked_default = model_id
                settings.models[model_id] = ModelSettings(
                    model_id=model_id,
                    display_name=name_item.text(),
                    path=table.item(row, 3).text() if table.item(row, 3) else "",
                    enabled=enabled,
                    is_default=enabled and is_default,
                    note=table.item(row, 4).text() if table.item(row, 4) else "",
                    quality_score=self._score(table.item(row, 5)),
                    speed_score=self._score(table.item(row, 6)),
                    memory_score=self._score(table.item(row, 7)),
                )
            settings.default_model = checked_default or settings.default_model or first_enabled
            self.store.update_engine(settings)
            if hasattr(engine, "_health_cache"):
                engine._health_cache = None
        tool_manager = get_tool_manager()
        for engine_id, widgets in self.video_widgets.items():
            settings = self.store.get_engine(engine_id)
            settings.enabled = widgets["enabled"].isChecked()
            settings.executable_path = widgets["exe"].text().strip()
            settings.model_dir = widgets["model_dir"].text().strip() or str(get_video_interpolation_models_dir(engine_id))
            settings.default_model = widgets["model_combo"].currentData() or ""
            settings.default_scale = widgets["scale_combo"].currentData() or 2
            settings.default_tile = 0
            settings.low_memory_default = False
            settings.default_output_format = "png"
            settings.extra_params["gpu_id"] = widgets["gpu"].text().strip() or self.store.global_settings.gpu_id
            settings.extra_params["use_tta"] = widgets["tta"].isChecked()
            self.store.update_engine(settings)
            exe_path = Path(settings.executable_path) if settings.executable_path else None
            if exe_path and exe_path.exists():
                tool_manager.set_configured_path(engine_id, exe_path)
        self.store.save()
        if self.status_label:
            self.status_label.setText(f"已保存：{self.store.path}")

    def _score(self, item: QTableWidgetItem | None) -> int:
        if item is None:
            return 3
        try:
            return max(1, min(5, int(item.text())))
        except ValueError:
            return 3
