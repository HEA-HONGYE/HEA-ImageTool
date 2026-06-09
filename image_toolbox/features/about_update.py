from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QProgressBar, QTextEdit, QVBoxLayout, QWidget

from image_toolbox import APP_NAME, APP_VERSION
from image_toolbox.core.config import AppConfig
from image_toolbox.core.updater import DEFAULT_RELEASE_URL, DEFAULT_UPDATE_MANIFEST_URLS, UpdateCheckTask, UpdateDownloadTask, UpdateInfo, parse_url_list


class AboutUpdatePanel(QWidget):
    update_checked = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.config = AppConfig("updates")
        self.thread_pool = QThreadPool.globalInstance()
        self.latest_info: UpdateInfo | None = None
        self.check_button: QPushButton | None = None
        self.download_button: QPushButton | None = None
        self.open_release_button: QPushButton | None = None
        self.auto_check_checkbox: QCheckBox | None = None
        self.manifest_edit: QTextEdit | None = None
        self.status_label: QLabel | None = None
        self.notes_box: QTextEdit | None = None
        self.progress_bar: QProgressBar | None = None
        self.update_check_task: UpdateCheckTask | None = None
        self.update_download_task: UpdateDownloadTask | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("关于与更新")
        title.setObjectName("PanelTitle")
        hint = QLabel("查看当前版本，并从线上更新清单检查新安装包。")
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)

        info_group = QGroupBox("版本信息")
        info_layout = QFormLayout(info_group)
        info_layout.addRow("应用", QLabel(APP_NAME))
        info_layout.addRow("当前版本", QLabel(f"v{APP_VERSION}"))
        layout.addWidget(info_group)

        update_group = QGroupBox("线上更新")
        update_layout = QVBoxLayout(update_group)
        update_layout.setSpacing(10)

        self.status_label = QLabel("尚未检查更新")
        self.status_label.setObjectName("MutedText")
        self.status_label.setWordWrap(True)
        update_layout.addWidget(self.status_label)

        self.notes_box = QTextEdit()
        self.notes_box.setReadOnly(True)
        self.notes_box.setMinimumHeight(110)
        self.notes_box.setPlainText("检查到新版本后会显示更新说明。")
        update_layout.addWidget(self.notes_box)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()
        update_layout.addWidget(self.progress_bar)

        actions = QHBoxLayout()
        self.check_button = QPushButton("检查更新")
        self.check_button.clicked.connect(lambda: self.check_for_updates(silent=False))
        self.download_button = QPushButton("下载更新包")
        self.download_button.setObjectName("GhostButton")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.download_update)
        self.open_release_button = QPushButton("打开发布页")
        self.open_release_button.setObjectName("GhostButton")
        self.open_release_button.clicked.connect(self.open_release_page)
        actions.addStretch()
        actions.addWidget(self.check_button)
        actions.addWidget(self.download_button)
        actions.addWidget(self.open_release_button)
        update_layout.addLayout(actions)
        layout.addWidget(update_group)

        settings_group = QGroupBox("更新设置")
        settings_layout = QFormLayout(settings_group)
        self.auto_check_checkbox = QCheckBox("启动时自动检查更新")
        self.auto_check_checkbox.setChecked(self.config.get("auto_check", True, bool))
        self.manifest_edit = QTextEdit()
        self.manifest_edit.setMaximumHeight(86)
        self.manifest_edit.setPlainText(self.config.get("manifest_urls", "\n".join(DEFAULT_UPDATE_MANIFEST_URLS)))
        settings_layout.addRow("", self.auto_check_checkbox)
        settings_layout.addRow("更新清单地址", self.manifest_edit)
        layout.addWidget(settings_group)
        layout.addStretch()

    def manifest_urls(self) -> list[str]:
        if not self.manifest_edit:
            return list(DEFAULT_UPDATE_MANIFEST_URLS)
        urls = parse_url_list(self.manifest_edit.toPlainText())
        return urls or list(DEFAULT_UPDATE_MANIFEST_URLS)

    def check_for_updates(self, silent: bool = False) -> None:
        self.save_settings()
        if self.check_button:
            self.check_button.setEnabled(False)
            self.check_button.setText("检查中...")
        if self.status_label and not silent:
            self.status_label.setText("正在连接更新服务器...")

        self.update_check_task = UpdateCheckTask(self.manifest_urls())
        self.update_check_task.signals.finished.connect(lambda info: self._update_check_finished(info, silent))
        self.update_check_task.signals.failed.connect(lambda message: self._update_check_failed(message, silent))
        self.thread_pool.start(self.update_check_task)

    def _update_check_finished(self, info: UpdateInfo, silent: bool = False) -> None:
        self.latest_info = info
        self.update_check_task = None
        self.update_checked.emit(info)
        if self.check_button:
            self.check_button.setEnabled(True)
            self.check_button.setText("检查更新")
        if self.download_button:
            self.download_button.setEnabled(info.has_update and bool(info.download_url))
        if self.notes_box:
            notes = info.notes or "此版本没有提供更新说明。"
            self.notes_box.setPlainText(notes)
        if self.status_label:
            if info.has_update:
                self.status_label.setText(f"发现新版本 v{info.latest_version}，当前版本 v{info.current_version}。")
            else:
                self.status_label.setText(f"当前已是最新版本：v{info.current_version}。")
        if info.has_update and not silent:
            QMessageBox.information(self, "发现新版本", f"发现 {APP_NAME} v{info.latest_version}，可点击下载更新包或打开发布页。")

    def _update_check_failed(self, message: str, silent: bool = False) -> None:
        self.update_check_task = None
        if self.check_button:
            self.check_button.setEnabled(True)
            self.check_button.setText("检查更新")
        if self.status_label and not silent:
            self.status_label.setText(message)
        if not silent:
            QMessageBox.warning(self, "检查更新失败", message)

    def download_update(self) -> None:
        if not self.latest_info:
            return
        if self.download_button:
            self.download_button.setEnabled(False)
            self.download_button.setText("下载中...")
        if self.progress_bar:
            self.progress_bar.show()
            self.progress_bar.setValue(0)
        self.update_download_task = UpdateDownloadTask(self.latest_info)
        self.update_download_task.signals.progress.connect(self._set_download_progress)
        self.update_download_task.signals.finished.connect(self._download_finished)
        self.update_download_task.signals.failed.connect(self._download_failed)
        self.thread_pool.start(self.update_download_task)

    def _set_download_progress(self, value: int) -> None:
        if self.progress_bar:
            self.progress_bar.setValue(value)

    def _download_finished(self, path: Path) -> None:
        self.update_download_task = None
        if self.download_button:
            self.download_button.setEnabled(True)
            self.download_button.setText("下载更新包")
        if self.status_label:
            self.status_label.setText(f"更新包已下载：{path}")
        choice = QMessageBox.question(
            self,
            "更新包已下载",
            "更新包已下载完成。是否现在运行安装程序？运行前请先保存当前任务。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if choice == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _download_failed(self, message: str) -> None:
        self.update_download_task = None
        if self.download_button:
            self.download_button.setEnabled(True)
            self.download_button.setText("下载更新包")
        if self.status_label:
            self.status_label.setText(message)
        QMessageBox.warning(self, "下载更新失败", message)

    def open_release_page(self) -> None:
        url = DEFAULT_RELEASE_URL
        if self.latest_info and self.latest_info.release_url:
            url = self.latest_info.release_url
        QDesktopServices.openUrl(QUrl(url))

    def save_settings(self) -> None:
        if self.auto_check_checkbox:
            self.config.set("auto_check", self.auto_check_checkbox.isChecked())
        if self.manifest_edit:
            self.config.set("manifest_urls", "\n".join(self.manifest_urls()))
