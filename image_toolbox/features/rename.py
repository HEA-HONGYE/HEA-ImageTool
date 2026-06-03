from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QCheckBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

from image_toolbox.core.config import AppConfig
from image_toolbox.core.image_ops import rename_image
from image_toolbox.features.base import ToolFeature


class RenameFeature(ToolFeature):
    key = "rename"
    title = "批量重命名"
    description = "用前缀、后缀、自动编号和原文件名组合批量导出。"

    def __init__(self) -> None:
        self.config = AppConfig(self.key)
        self.prefix_edit: QLineEdit | None = None
        self.suffix_edit: QLineEdit | None = None
        self.keep_original_checkbox: QCheckBox | None = None
        self.auto_number_checkbox: QCheckBox | None = None
        self.start_spin: QSpinBox | None = None
        self.width_spin: QSpinBox | None = None
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

        group = QGroupBox("命名参数")
        form = QFormLayout(group)
        form.setSpacing(14)

        self.prefix_edit = QLineEdit(self.config.get("prefix", ""))
        form.addRow("前缀", self.prefix_edit)

        self.suffix_edit = QLineEdit(self.config.get("suffix", ""))
        form.addRow("后缀", self.suffix_edit)

        self.keep_original_checkbox = QCheckBox("保留原文件名")
        self.keep_original_checkbox.setChecked(self.config.get("keep_original", True, bool))
        form.addRow("原名", self.keep_original_checkbox)

        self.auto_number_checkbox = QCheckBox("添加自动编号")
        self.auto_number_checkbox.setChecked(self.config.get("auto_number", True, bool))
        form.addRow("编号", self.auto_number_checkbox)

        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 999999)
        self.start_spin.setValue(self.config.get("start", 1, int))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 8)
        self.width_spin.setValue(self.config.get("width", 3, int))
        number_row = QHBoxLayout()
        number_row.addWidget(QLabel("起始"))
        number_row.addWidget(self.start_spin)
        number_row.addWidget(QLabel("位数"))
        number_row.addWidget(self.width_spin)
        form.addRow("编号格式", number_row)

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
        prefix = self.prefix_edit.text() if self.prefix_edit else ""
        suffix = self.suffix_edit.text() if self.suffix_edit else ""
        keep_original = self.keep_original_checkbox.isChecked() if self.keep_original_checkbox else True
        auto_number = self.auto_number_checkbox.isChecked() if self.auto_number_checkbox else True
        start = self.start_spin.value() if self.start_spin else 1
        width = self.width_spin.value() if self.width_spin else 3
        order = {path.resolve(): index for index, path in enumerate(files, start=start)}

        self.config.set("output_dir", str(output_dir))
        self.config.set("prefix", prefix)
        self.config.set("suffix", suffix)
        self.config.set("keep_original", keep_original)
        self.config.set("auto_number", auto_number)
        self.config.set("start", start)
        self.config.set("width", width)

        def processor(source: Path, logger: Callable[[str], None]) -> Path:
            parts: list[str] = []
            if prefix:
                parts.append(prefix)
            if keep_original:
                parts.append(source.stem)
            if suffix:
                parts.append(suffix)
            if auto_number:
                parts.append(str(order[source.resolve()]).zfill(width))
            new_stem = "_".join(part for part in parts if part) or source.stem
            return rename_image(source, output_dir, new_stem, logger)

        return processor

    def get_output_dir(self) -> Path | None:
        return Path(self.output_edit.text()) if self.output_edit and self.output_edit.text() else None

    def _choose_output(self) -> None:
        if not self.output_edit:
            return
        directory = QFileDialog.getExistingDirectory(None, "选择输出目录", self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)
