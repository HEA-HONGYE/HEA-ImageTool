from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QProgressBar, QPushButton, QVBoxLayout, QWidget

from image_toolbox.core.image_ops import is_supported_image

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


class FilePanel(QFrame):
    files_changed = Signal()
    selection_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("RightPanel")
        self.setAcceptDrops(True)
        self.files: list[Path] = []
        self.statuses: list[str] = []
        self.dialog_title = "选择图片"
        self.dialog_filter = "Images (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)"
        self.supported_suffixes = set(IMAGE_SUFFIXES)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("任务队列")
        title.setObjectName("CardTitle")
        self.count_label = QLabel("0 个任务")
        self.count_label.setObjectName("MutedText")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.count_label)
        layout.addLayout(header)

        stats = QHBoxLayout()
        stats.setSpacing(8)
        self.running_label = self._build_stat_label("运行中 0")
        self.waiting_label = self._build_stat_label("等待中 0")
        stats.addWidget(self.running_label)
        stats.addWidget(self.waiting_label)
        layout.addLayout(stats)

        buttons = QHBoxLayout()
        add_button = QPushButton("添加文件")
        clear_button = QPushButton("清空")
        clear_button.setObjectName("GhostButton")
        add_button.clicked.connect(self.choose_files)
        clear_button.clicked.connect(self.clear_files)
        buttons.addWidget(add_button)
        buttons.addWidget(clear_button)
        layout.addLayout(buttons)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("TaskQueueList")
        self.list_widget.currentRowChanged.connect(self._on_current_row_changed)
        layout.addWidget(self.list_widget, 1)

        self.info_label = QLabel("拖入文件或点击添加。")
        self.info_label.setObjectName("MutedText")
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignTop)
        layout.addWidget(self.info_label)

    def _build_stat_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("QueueStatPill")
        label.setAlignment(Qt.AlignCenter)
        return label

    def choose_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            self.dialog_title,
            str(Path.cwd()),
            self.dialog_filter,
        )
        self.add_files([Path(item) for item in selected])

    def configure_media_mode(self, enabled: bool) -> None:
        if enabled:
            self.dialog_title = "选择媒体文件"
            self.dialog_filter = "Media Files (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.gif *.apng *.mp4 *.mov *.mkv *.avi *.webm *.m4v)"
            self.supported_suffixes = IMAGE_SUFFIXES | {".gif", ".apng", ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
            return
        self.dialog_title = "选择图片"
        self.dialog_filter = "Images (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)"
        self.supported_suffixes = set(IMAGE_SUFFIXES)

    def add_files(self, paths: list[Path]) -> None:
        existing = {path.resolve() for path in self.files}
        for path in paths:
            supported = is_supported_image(path) if self.supported_suffixes == IMAGE_SUFFIXES else path.suffix.lower() in self.supported_suffixes
            if path.exists() and supported and path.resolve() not in existing:
                self.files.append(path)
                self.statuses.append("待处理")
                existing.add(path.resolve())
                self._append_task_item(path, "待处理")
        if self.files and self.list_widget.currentRow() < 0:
            self.list_widget.setCurrentRow(0)
        self._update_info(self.list_widget.currentRow())
        self._refresh_summary()
        self.files_changed.emit()

    def set_files(self, paths: list[Path], statuses: list[str] | None = None, emit_changed: bool = False) -> None:
        self.files = list(paths)
        self.statuses = list(statuses or ["待处理"] * len(self.files))
        if len(self.statuses) < len(self.files):
            self.statuses.extend(["待处理"] * (len(self.files) - len(self.statuses)))
        self.statuses = self.statuses[: len(self.files)]
        self.list_widget.clear()
        for path, status in zip(self.files, self.statuses):
            self._append_task_item(path, status)
        if self.files:
            self.list_widget.setCurrentRow(0)
        self._update_info(self.list_widget.currentRow())
        self._refresh_summary()
        if emit_changed:
            self.files_changed.emit()

    def clear_files(self) -> None:
        self.files.clear()
        self.statuses.clear()
        self.list_widget.clear()
        self.info_label.setText("拖入文件或点击添加。")
        self._refresh_summary()
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
        item.setText("")
        item.setSizeHint(QSize(0, 68))
        self.list_widget.setItemWidget(item, self._build_task_item_widget(self.files[index], status))
        if self.list_widget.currentRow() == index:
            self._update_info(index)
        self._refresh_summary()

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
        self.add_files(paths)

    def _item_text(self, name: str, status: str) -> str:
        return f"[{status}] {name}"

    def _append_task_item(self, path: Path, status: str) -> None:
        item = QListWidgetItem()
        item.setText("")
        item.setSizeHint(QSize(0, 68))
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, self._build_task_item_widget(path, status))

    def _build_task_item_widget(self, path: Path, status: str) -> QWidget:
        row = QWidget()
        row.setObjectName("TaskQueueItem")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        thumb = QLabel(path.suffix.upper().lstrip(".")[:4] or "IMG")
        thumb.setObjectName("TaskThumb")
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setFixedSize(42, 42)
        layout.addWidget(thumb)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        name_label = QLabel(path.name)
        name_label.setObjectName("TaskName")
        status_label = QLabel(status)
        status_label.setObjectName("TaskStatus")
        progress = QProgressBar()
        progress.setObjectName("TaskMiniProgress")
        progress.setRange(0, 100)
        progress.setTextVisible(False)
        progress.setFixedHeight(6)
        progress.setValue(self._status_progress(status))
        text_col.addWidget(name_label)
        text_col.addWidget(status_label)
        text_col.addWidget(progress)
        layout.addLayout(text_col, 1)
        return row

    def _status_progress(self, status: str) -> int:
        if "待" in status or "等待" in status:
            return 0
        if "完成" in status or "成功" in status or "Done" in status:
            return 100
        if "处理中" in status or "运行中" in status:
            return 48
        if "失败" in status:
            return 100
        return 0

    def _refresh_summary(self) -> None:
        total = len(self.files)
        running = sum(1 for status in self.statuses if ("处理中" in status or "运行中" in status) and "待" not in status)
        waiting = sum(1 for status in self.statuses if "待" in status or "等待" in status)
        self.count_label.setText(f"{total} 个任务")
        self.running_label.setText(f"运行中 {running}")
        self.waiting_label.setText(f"等待中 {waiting}")

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
            self.info_label.setText("拖入文件或点击添加。")
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
            if self.supported_suffixes != IMAGE_SUFFIXES and path.suffix.lower() in self.supported_suffixes:
                self.info_label.setText(f"状态：{status}\n名称：{path.name}\n格式：{path.suffix.upper().lstrip('.') or '未知'}\n大小：{size_kb:.1f} KB\n路径：{path}")
            else:
                self.info_label.setText(f"无法读取图片信息：{exc}")
