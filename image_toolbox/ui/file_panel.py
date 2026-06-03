from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout

from image_toolbox.core.image_ops import is_supported_image


class FilePanel(QFrame):
    files_changed = Signal()
    selection_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("RightPanel")
        self.setAcceptDrops(True)
        self.files: list[Path] = []
        self.statuses: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("任务队列")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        buttons = QHBoxLayout()
        add_button = QPushButton("添加图片")
        clear_button = QPushButton("清空")
        clear_button.setObjectName("GhostButton")
        add_button.clicked.connect(self.choose_files)
        clear_button.clicked.connect(self.clear_files)
        buttons.addWidget(add_button)
        buttons.addWidget(clear_button)
        layout.addLayout(buttons)

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_current_row_changed)
        layout.addWidget(self.list_widget, 1)

        self.info_label = QLabel("拖入图片或点击添加。")
        self.info_label.setObjectName("MutedText")
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignTop)
        layout.addWidget(self.info_label)

    def choose_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图片",
            str(Path.cwd()),
            "Images (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)",
        )
        self.add_files([Path(item) for item in selected])

    def add_files(self, paths: list[Path]) -> None:
        existing = {path.resolve() for path in self.files}
        for path in paths:
            if path.exists() and is_supported_image(path) and path.resolve() not in existing:
                self.files.append(path)
                self.statuses.append("待处理")
                existing.add(path.resolve())
                self.list_widget.addItem(self._item_text(path.name, "待处理"))
        if self.files and self.list_widget.currentRow() < 0:
            self.list_widget.setCurrentRow(0)
        self._update_info(self.list_widget.currentRow())
        self.files_changed.emit()

    def clear_files(self) -> None:
        self.files.clear()
        self.statuses.clear()
        self.list_widget.clear()
        self.info_label.setText("拖入图片或点击添加。")
        self.files_changed.emit()

    def reset_statuses(self) -> None:
        for index in range(len(self.statuses)):
            self.set_file_status(index, "待处理")

    def set_file_status(self, index: int, status: str) -> None:
        if index < 0 or index >= len(self.files):
            return
        self.statuses[index] = status
        item = self.list_widget.item(index)
        if item is None:
            item = QListWidgetItem()
            self.list_widget.insertItem(index, item)
        item.setText(self._item_text(self.files[index].name, status))
        if self.list_widget.currentRow() == index:
            self._update_info(index)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
        self.add_files(paths)

    def _item_text(self, name: str, status: str) -> str:
        return f"[{status}] {name}"

    def selected_file(self) -> Path | None:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.files):
            return self.files[0] if self.files else None
        return self.files[row]

    def _on_current_row_changed(self, row: int) -> None:
        self._update_info(row)
        self.selection_changed.emit()

    def _update_info(self, row: int) -> None:
        if row < 0 or row >= len(self.files):
            self.info_label.setText("拖入图片或点击添加。")
            return

        path = self.files[row]
        status = self.statuses[row] if row < len(self.statuses) else "待处理"
        size_kb = path.stat().st_size / 1024
        try:
            with Image.open(path) as image:
                width, height = image.size
                mode = image.mode
                fmt = image.format or path.suffix.upper().strip(".")
            self.info_label.setText(
                f"状态：{status}\n名称：{path.name}\n格式：{fmt}\n尺寸：{width} x {height}\n色彩：{mode}\n大小：{size_kb:.1f} KB\n路径：{path}"
            )
        except Exception as exc:
            self.info_label.setText(f"无法读取图片信息：{exc}")
