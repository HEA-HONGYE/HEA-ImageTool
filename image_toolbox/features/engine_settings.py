from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
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
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from image_toolbox.core.engine_settings import EngineSettings, ModelSettings, get_engine_settings_store
from image_toolbox.core.upscale_engines import DEFAULT_ENGINE_MANAGER


class EngineSettingsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.store = get_engine_settings_store()
        self.tabs: QTabWidget | None = None
        self.widgets: dict[str, dict[str, Any]] = {}
        self.status_label: QLabel | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("引擎设置")
        title.setObjectName("PanelTitle")
        hint = QLabel("统一管理图片超分/增强引擎、模型启用状态、默认参数和路径配置。")
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)

        self.tabs = QTabWidget()
        for engine in DEFAULT_ENGINE_MANAGER.list_engines():
            tab = self._build_engine_tab(engine)
            self.tabs.addTab(tab, engine.display_name)
        layout.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        self.status_label = QLabel(f"配置文件：{self.store.path}")
        self.status_label.setObjectName("MutedText")
        save_button = QPushButton("保存设置")
        save_button.clicked.connect(self.save_settings)
        footer.addWidget(self.status_label)
        footer.addStretch()
        footer.addWidget(save_button)
        layout.addLayout(footer)

    def _build_engine_tab(self, engine) -> QWidget:
        settings = self.store.get_engine(engine.engine_id)
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(14)

        status_group = QGroupBox("引擎状态")
        status_layout = QFormLayout(status_group)
        enabled = QCheckBox("启用该引擎")
        enabled.setChecked(settings.enabled)
        status = QLabel(self._engine_status_text(engine, settings))
        status.setObjectName("MutedText")
        status.setWordWrap(True)
        test_button = QPushButton("测试引擎")
        test_button.clicked.connect(lambda _checked=False, e=engine, label=status: self._test_engine(e, label))
        status_layout.addRow("状态", status)
        status_layout.addRow("启用", enabled)
        status_layout.addRow("说明", QLabel(engine.recommendation()))
        status_layout.addRow("", test_button)
        layout.addWidget(status_group)

        path_group = QGroupBox("路径")
        path_layout = QFormLayout(path_group)
        exe_edit = QLineEdit(settings.executable_path or str(engine.executable_path))
        model_root = self._engine_model_root(engine)
        model_edit = QLineEdit(settings.model_dir or (str(model_root) if model_root else ""))
        path_layout.addRow("引擎程序", self._path_row(exe_edit, "file"))
        path_layout.addRow("模型目录", self._path_row(model_edit, "dir"))
        layout.addWidget(path_group)

        defaults_group = QGroupBox("默认参数")
        defaults_layout = QFormLayout(defaults_group)
        model_combo = QComboBox()
        scale_combo = QComboBox()
        tile_spin = QSpinBox()
        tile_spin.setRange(0, 2048)
        tile_spin.setSingleStep(128)
        tile_spin.setValue(settings.default_tile)
        low_memory = QCheckBox("默认开启低显存模式")
        low_memory.setChecked(settings.low_memory_default)
        format_combo = QComboBox()
        for label, value in [("保留原格式", "original"), ("PNG", "png"), ("JPG", "jpg"), ("WEBP", "webp")]:
            format_combo.addItem(label, value)
        format_combo.setCurrentIndex(max(0, format_combo.findData(settings.default_output_format or "original")))
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
        for scale in engine.supported_scales:
            scale_combo.addItem(f"{scale}x", scale)
        scale_combo.setCurrentIndex(max(0, scale_combo.findData(settings.default_scale or (engine.supported_scales[0] if engine.supported_scales else 0))))
        tile_spin.setEnabled(engine.supports_tile)
        low_memory.setEnabled(engine.supports_tile)
        defaults_layout.addRow("默认模型", model_combo)
        defaults_layout.addRow("默认倍率", scale_combo)
        defaults_layout.addRow("默认 Tile（0=自动）", tile_spin)
        defaults_layout.addRow("低显存", low_memory)
        defaults_layout.addRow("默认降噪", noise_combo)
        defaults_layout.addRow("默认 SyncGap", syncgap_combo)
        defaults_layout.addRow("默认输出格式", format_combo)
        layout.addWidget(defaults_group)

        models_group = QGroupBox("模型管理")
        models_layout = QVBoxLayout(models_group)
        scan_button = QPushButton("扫描模型")
        table = QTableWidget(0, 8)
        table.setHorizontalHeaderLabels(["启用", "默认", "模型名称", "模型路径", "备注", "质量", "速度", "显存"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        models_layout.addWidget(scan_button)
        models_layout.addWidget(table)
        layout.addWidget(models_group, 1)

        self.widgets[engine.engine_id] = {
            "enabled": enabled,
            "exe": exe_edit,
            "model_dir": model_edit,
            "model_combo": model_combo,
            "scale_combo": scale_combo,
            "tile": tile_spin,
            "low_memory": low_memory,
            "format": format_combo,
            "noise": noise_combo,
            "syncgap": syncgap_combo,
            "table": table,
            "status": status,
        }
        scan_button.clicked.connect(lambda _checked=False, e=engine: self.scan_models(e.engine_id))
        self.scan_models(engine.engine_id)
        layout.addStretch()
        return tab

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

    def _browse_path(self, edit: QLineEdit, mode: str) -> None:
        if mode == "file":
            selected, _ = QFileDialog.getOpenFileName(self, "选择引擎程序", edit.text() or str(Path.cwd()), "Executable (*.exe)")
        else:
            selected = QFileDialog.getExistingDirectory(self, "选择模型目录", edit.text() or str(Path.cwd()))
        if selected:
            edit.setText(selected)

    def _engine_model_root(self, engine) -> Path | None:
        for attr in ("models_path", "models_path", "models_path"):
            if hasattr(engine, attr):
                return getattr(engine, attr)
        return None

    def _engine_status_text(self, engine, settings: EngineSettings) -> str:
        if not settings.enabled:
            return "已禁用"
        available, reason = engine.health_check()
        return f"可用：{engine.executable_path}" if available else f"不可用：{reason}"

    def _test_engine(self, engine, label: QLabel) -> None:
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
            enabled_item = QTableWidgetItem()
            enabled_item.setCheckState(Qt.CheckState.Checked if model_settings.enabled else Qt.CheckState.Unchecked)
            default_item = QTableWidgetItem()
            default_item.setCheckState(Qt.CheckState.Checked if model_settings.is_default or settings.default_model == model.name else Qt.CheckState.Unchecked)
            name_item = QTableWidgetItem(model.display_name or model.name)
            name_item.setData(Qt.ItemDataRole.UserRole, model.name)
            path_item = QTableWidgetItem(model_settings.path or str(engine.get_model_path(model.name) or ""))
            note_item = QTableWidgetItem(model_settings.note)
            quality_item = QTableWidgetItem(str(model_settings.quality_score))
            speed_item = QTableWidgetItem(str(model_settings.speed_score))
            memory_item = QTableWidgetItem(str(model_settings.memory_score))
            for col, item in enumerate([enabled_item, default_item, name_item, path_item, note_item, quality_item, speed_item, memory_item]):
                table.setItem(row, col, item)
            if model_settings.enabled:
                combo.addItem(model.display_name or model.name, model.name)
        default_model = settings.default_model or (models[0].name if models else "")
        combo.setCurrentIndex(max(0, combo.findData(default_model)))
        table.resizeColumnsToContents()

    def save_settings(self) -> None:
        for engine in DEFAULT_ENGINE_MANAGER.list_engines():
            engine_id = engine.engine_id
            widgets = self.widgets[engine_id]
            settings = self.store.get_engine(engine_id)
            settings.enabled = widgets["enabled"].isChecked()
            settings.executable_path = widgets["exe"].text().strip()
            settings.model_dir = widgets["model_dir"].text().strip()
            settings.default_model = widgets["model_combo"].currentData() or ""
            settings.default_scale = widgets["scale_combo"].currentData() or 0
            settings.default_tile = widgets["tile"].value()
            settings.low_memory_default = widgets["low_memory"].isChecked()
            settings.default_output_format = widgets["format"].currentData() or "original"
            settings.default_noise_level = widgets["noise"].currentData() if widgets["noise"].currentData() is not None else 0
            settings.syncgap_mode = widgets["syncgap"].currentData() if widgets["syncgap"].currentData() is not None else 2
            table: QTableWidget = widgets["table"]
            first_enabled_model = ""
            default_model = ""
            for row in range(table.rowCount()):
                name_item = table.item(row, 2)
                if not name_item:
                    continue
                model_id = name_item.data(Qt.ItemDataRole.UserRole)
                enabled = table.item(row, 0).checkState() == Qt.CheckState.Checked
                is_default = table.item(row, 1).checkState() == Qt.CheckState.Checked
                if enabled and not first_enabled_model:
                    first_enabled_model = model_id
                if enabled and is_default:
                    default_model = model_id
                settings.models[model_id] = ModelSettings(
                    model_id=model_id,
                    display_name=name_item.text(),
                    path=table.item(row, 3).text() if table.item(row, 3) else "",
                    enabled=enabled,
                    is_default=enabled and is_default,
                    note=table.item(row, 4).text() if table.item(row, 4) else "",
                    quality_score=self._score_value(table.item(row, 5)),
                    speed_score=self._score_value(table.item(row, 6)),
                    memory_score=self._score_value(table.item(row, 7)),
                )
            if default_model:
                settings.default_model = default_model
            elif settings.default_model and settings.models.get(settings.default_model, ModelSettings(settings.default_model)).enabled:
                pass
            else:
                settings.default_model = first_enabled_model
            self.store.update_engine(settings)
            if hasattr(engine, "_health_cache"):
                engine._health_cache = None
        self.store.save()
        if self.status_label:
            self.status_label.setText(f"已保存：{self.store.path}")

    def _score_value(self, item: QTableWidgetItem | None) -> int:
        if item is None:
            return 3
        try:
            return max(1, min(5, int(item.text())))
        except ValueError:
            return 3
