from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThreadPool, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar, QPushButton, QStackedWidget, QTextEdit, QVBoxLayout, QWidget

from image_toolbox import APP_NAME, APP_VERSION
from image_toolbox.core.super_resolution import SuperResolutionSummary
from image_toolbox.core.tasks import ImageBatchTask
from image_toolbox.features.compression import CompressionFeature
from image_toolbox.features.conversion import ConversionFeature
from image_toolbox.features.home import HomePanel
from image_toolbox.features.rename import RenameFeature
from image_toolbox.features.resize import ResizeFeature
from image_toolbox.features.super_resolution import SuperResolutionFeature
from image_toolbox.features.watermark import WatermarkFeature
from image_toolbox.ui.file_panel import FilePanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1240, 800)
        self.thread_pool = QThreadPool.globalInstance()
        self.features = {
            "compress": CompressionFeature(),
            "convert": ConversionFeature(),
            "resize": ResizeFeature(),
            "super_resolution": SuperResolutionFeature(),
            "watermark": WatermarkFeature(),
            "rename": RenameFeature(),
        }
        self.nav_buttons: dict[str, QPushButton] = {}
        self.is_running = False
        self.is_paused = False
        self.run_button: QPushButton | None = None
        self.pause_button: QPushButton | None = None
        self.cancel_button: QPushButton | None = None
        self.retry_failed_button: QPushButton | None = None
        self.current_progress_label: QLabel | None = None
        self.current_task: ImageBatchTask | None = None
        self.last_failed_files: list[Path] = []
        self.last_failed_feature_key: str | None = None

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        root_layout.addLayout(content, 1)

        content.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.page_keys: list[str] = []
        self._add_page("home", self._build_home())
        for key, feature in self.features.items():
            self._add_page(key, feature.build_panel())
        content.addWidget(self.stack, 1)

        self.file_panel = FilePanel()
        self.file_panel.setFixedWidth(350)
        self.file_panel.files_changed.connect(self._notify_file_context_changed)
        self.file_panel.selection_changed.connect(self._notify_file_context_changed)
        content.addWidget(self.file_panel)

        root_layout.addWidget(self._build_bottom_panel())
        self.switch_page("home")
        self._set_running(False)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(10)

        brand = QLabel(APP_NAME)
        brand.setObjectName("CardTitle")
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("MutedText")
        layout.addWidget(brand)
        layout.addWidget(version)
        layout.addSpacing(14)

        self._add_nav_button(layout, "home", "首页")
        self._add_nav_button(layout, "compress", "图片压缩")
        self._add_nav_button(layout, "convert", "格式转换")
        self._add_nav_button(layout, "resize", "批量改尺寸")
        self._add_nav_button(layout, "super_resolution", "AI 超分")
        self._add_nav_button(layout, "watermark", "批量加水印")
        self._add_nav_button(layout, "rename", "批量重命名")
        layout.addStretch()

        self.run_button = QPushButton("开始处理")
        self.run_button.clicked.connect(self.run_current_feature)
        self.pause_button = QPushButton("暂停")
        self.pause_button.setObjectName("GhostButton")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.cancel_button = QPushButton("停止")
        self.cancel_button.setObjectName("GhostButton")
        self.cancel_button.clicked.connect(self.cancel_task)
        layout.addWidget(self.run_button)
        layout.addWidget(self.pause_button)
        layout.addWidget(self.cancel_button)
        return sidebar

    def _add_nav_button(self, layout: QVBoxLayout, key: str, text: str) -> None:
        button = QPushButton(text)
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.clicked.connect(lambda _checked=False, page_key=key: self.switch_page(page_key))
        self.nav_buttons[key] = button
        layout.addWidget(button)

    def _build_home(self) -> HomePanel:
        home = HomePanel()
        home.feature_requested.connect(self.switch_page)
        return home

    def _build_bottom_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("BottomPanel")
        panel.setFixedHeight(170)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("日志输出")
        title.setObjectName("CardTitle")
        open_output_button = QPushButton("打开输出目录")
        open_output_button.setObjectName("GhostButton")
        open_output_button.clicked.connect(self.open_output_dir)
        self.retry_failed_button = QPushButton("重试失败项")
        self.retry_failed_button.setObjectName("GhostButton")
        self.retry_failed_button.clicked.connect(self.retry_failed_items)
        clear_button = QPushButton("清空日志")
        clear_button.setObjectName("GhostButton")
        clear_button.clicked.connect(lambda: self.log_box.clear())
        header.addWidget(title)
        header.addStretch()
        header.addWidget(open_output_button)
        header.addWidget(self.retry_failed_button)
        header.addWidget(clear_button)
        layout.addLayout(header)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.current_progress_label = QLabel("当前：未开始")
        self.current_progress_label.setObjectName("MutedText")
        layout.addWidget(self.current_progress_label)
        return panel

    def _add_page(self, key: str, widget: QWidget) -> None:
        self.page_keys.append(key)
        self.stack.addWidget(widget)

    def switch_page(self, key: str) -> None:
        if key not in self.page_keys:
            return
        self.stack.setCurrentIndex(self.page_keys.index(key))
        for button_key, button in self.nav_buttons.items():
            button.setChecked(button_key == key)
        self._notify_file_context_changed()

    def run_current_feature(self) -> None:
        if self.is_running:
            self._log("已有任务正在处理，请等待完成。")
            return

        key = self.page_keys[self.stack.currentIndex()]
        if key == "home":
            self._log("请先选择左侧的功能模块。")
            return

        files = list(self.file_panel.files)
        if not files:
            self._log("请先添加图片文件。")
            return

        feature = self.features[key]
        self.progress_bar.setValue(0)
        self.file_panel.reset_statuses()
        try:
            task = feature.create_task(files)
            if task is None:
                processor = feature.create_processor(files)
                task = ImageBatchTask(files, processor)
        except Exception as exc:
            self._log(f"参数错误：{exc}")
            return

        self._start_task(key, feature.title, files, task)

    def _start_task(self, key: str, title: str, files: list[Path], task) -> None:
        task.signals.log.connect(self._log)
        if hasattr(task.signals, "debug"):
            task.signals.debug.connect(self._log_debug)
        task.signals.progress.connect(self.progress_bar.setValue)
        if hasattr(task.signals, "current_progress"):
            task.signals.current_progress.connect(self._set_current_progress)
        task.signals.file_status.connect(self.file_panel.set_file_status)
        task.signals.failed.connect(self._task_failed)
        if key == "super_resolution":
            task.signals.finished.connect(self._super_resolution_finished)
        else:
            task.signals.finished.connect(self._task_finished)
        self.current_task = task
        self._set_running(True)
        if self.current_progress_label:
            self.current_progress_label.setText("当前：准备开始")
        self._log(f"开始：{title}，共 {len(files)} 个文件。")
        self.thread_pool.start(task)

    def toggle_pause(self) -> None:
        if not self.current_task:
            return
        if self.is_paused:
            self.current_task.resume()
            self.is_paused = False
            self._log("任务已继续。")
        else:
            self.current_task.pause()
            self.is_paused = True
            self._log("任务已暂停，当前文件完成后会停在下一个文件前。")
        if self.pause_button:
            self.pause_button.setText("继续" if self.is_paused else "暂停")

    def cancel_task(self) -> None:
        if not self.current_task:
            return
        self.current_task.cancel()
        self._log("正在停止任务...")

    def retry_failed_items(self) -> None:
        if self.is_running:
            self._log("已有任务正在处理，请等待完成。")
            return
        if not self.last_failed_files or not self.last_failed_feature_key:
            self._log("当前没有可重试的失败项。")
            return
        feature = self.features[self.last_failed_feature_key]
        try:
            task = feature.create_task(self.last_failed_files)
        except Exception as exc:
            self._log(f"参数错误：{exc}")
            return
        self.file_panel.clear_files()
        self.file_panel.add_files(self.last_failed_files)
        self.progress_bar.setValue(0)
        self._start_task(self.last_failed_feature_key, f"{feature.title}（重试失败项）", self.last_failed_files, task)

    def open_output_dir(self) -> None:
        key = self.page_keys[self.stack.currentIndex()]
        output_dir: Path | None = None
        if key in self.features:
            output_dir = self.features[key].get_output_dir()
        if output_dir is None:
            output_dir = Path.cwd() / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_dir.resolve())))

    def _task_failed(self, message: str) -> None:
        self._log(f"失败：{message}")
        self.current_task = None
        self._set_running(False)

    def _task_finished(self, success_count: int, failed_count: int) -> None:
        self._log(f"全部任务完成。成功 {success_count} 个，失败 {failed_count} 个。")
        self.current_task = None
        self._set_running(False)

    def _super_resolution_finished(self, summary: SuperResolutionSummary) -> None:
        elapsed = self._format_elapsed(summary.elapsed_seconds)
        self.last_failed_files = [item.source for item in summary.failed_items]
        self.last_failed_feature_key = "super_resolution" if self.last_failed_files else None
        self._log(
            f"AI 超分完成。总数量 {summary.total}，成功 {summary.success_count}，失败 {summary.failed_count}，跳过 {summary.skipped_count}，耗时 {elapsed}。"
        )
        self._log(f"输出目录：{summary.output_dir}")
        if summary.failed_items:
            self._log("失败项/失败日志：")
            for item in summary.failed_items:
                self._log(f"- {item.source.name}：{item.reason}")
        if self.current_progress_label:
            self.current_progress_label.setText("当前：已完成")
        self.current_task = None
        self._set_running(False)

    def _set_running(self, is_running: bool) -> None:
        self.is_running = is_running
        if not is_running:
            self.is_paused = False
        if self.run_button:
            self.run_button.setEnabled(not is_running)
            self.run_button.setText("处理中..." if is_running else "开始处理")
        if self.pause_button:
            self.pause_button.setEnabled(is_running)
            self.pause_button.setText("暂停")
        if self.cancel_button:
            self.cancel_button.setEnabled(is_running)
            self.cancel_button.setText("停止")
        if self.retry_failed_button:
            self.retry_failed_button.setEnabled((not is_running) and bool(self.last_failed_files))

    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{timestamp}] {message}")

    def _log_debug(self, message: str) -> None:
        self._log(message)

    def _set_current_progress(self, message: str) -> None:
        if self.current_progress_label:
            self.current_progress_label.setText(message)

    def _notify_file_context_changed(self) -> None:
        key = self.page_keys[self.stack.currentIndex()] if hasattr(self, "stack") and self.page_keys else ""
        if key in self.features:
            selected_file = self.file_panel.selected_file() if hasattr(self, "file_panel") else None
            self.features[key].update_file_context(list(self.file_panel.files), selected_file, self._log)

    def _format_elapsed(self, seconds: float) -> str:
        minutes, sec = divmod(int(seconds), 60)
        if minutes:
            return f"{minutes} 分 {sec} 秒"
        return f"{sec} 秒"

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.is_running and self.current_task:
            choice = QMessageBox.question(
                self,
                "确认退出",
                "当前还有图片任务正在处理。要取消剩余任务并退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if choice != QMessageBox.Yes:
                event.ignore()
                return

            self.current_task.cancel()
            self.thread_pool.waitForDone(3000)

        event.accept()
