from __future__ import annotations

import ctypes
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSize, QSizeF, Qt, QThreadPool, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QMouseEvent, QPainter, QPixmap, QResizeEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QFormLayout, QGraphicsOpacityEffect, QGraphicsScene, QGraphicsView, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSlider, QStackedWidget, QTextEdit, QVBoxLayout, QWidget

from image_toolbox import APP_NAME, APP_VERSION
from image_toolbox.core.config import AppConfig
from image_toolbox.core.super_resolution import SuperResolutionSummary
from image_toolbox.core.tasks import ImageBatchTask
from image_toolbox.core.tool_manager import get_tool_manager
from image_toolbox.core.updater import DEFAULT_UPDATE_MANIFEST_URLS, UpdateCheckTask, UpdateInfo, parse_url_list
from image_toolbox.features.about_update import AboutUpdatePanel
from image_toolbox.features.compression import CompressionFeature
from image_toolbox.features.conversion import ConversionFeature
from image_toolbox.features.engine_settings import EngineSettingsPanel
from image_toolbox.features.home import HomePanel
from image_toolbox.features.rename import RenameFeature
from image_toolbox.features.resize import ResizeFeature
from image_toolbox.features.super_resolution import SuperResolutionFeature
from image_toolbox.features.tool_settings import ToolSettingsPanel
from image_toolbox.features.watermark import WatermarkFeature
from image_toolbox.ui.file_panel import FilePanel
from image_toolbox.ui.widgets import AppShell, GlassSidebar, GlassStatusBar


BACKGROUND_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
BACKGROUND_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
WM_NCHITTEST = 0x0084
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17
RESIZE_BORDER_WIDTH = 8


class WindowsMessage(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint32),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


class StableStackedWidget(QStackedWidget):
    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, 0)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, 0)


class CompactScrollArea(QScrollArea):
    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, 0)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, 0)


class TaskCompletionToast(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("TaskCompletionToast")
        self.setFixedWidth(360)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._slide_out)
        self.slide_animation: QPropertyAnimation | None = None
        self.opacity_animation: QPropertyAnimation | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        icon = QLabel("✓")
        icon.setObjectName("TaskCompletionToastIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(34, 34)
        layout.addWidget(icon)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)
        self.title_label = QLabel("任务完成")
        self.title_label.setObjectName("TaskCompletionToastTitle")
        self.message_label = QLabel("")
        self.message_label.setObjectName("TaskCompletionToastMessage")
        self.message_label.setWordWrap(True)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.message_label)
        layout.addLayout(text_layout, 1)

    def show_message(self, title: str, message: str, duration_ms: int = 3600) -> None:
        self.title_label.setText(title)
        self.message_label.setText(message)
        self.adjustSize()
        self.raise_()
        self.show()

        end_pos = self._visible_position()
        start_pos = QPoint(self.parentWidget().width() + 18, end_pos.y()) if self.parentWidget() else end_pos
        self.move(start_pos)
        self.opacity_effect.setOpacity(0.0)
        self._animate(start_pos, end_pos, 0.0, 1.0, 360, QEasingCurve.Type.OutCubic)
        self.hide_timer.start(duration_ms)

    def reposition(self) -> None:
        if self.isVisible():
            self.move(self._visible_position())

    def _visible_position(self) -> QPoint:
        parent = self.parentWidget()
        if parent is None:
            return QPoint(0, 0)
        margin = 24
        return QPoint(parent.width() - self.width() - margin, parent.height() - self.height() - margin)

    def _slide_out(self) -> None:
        current = self.pos()
        end = QPoint(self.parentWidget().width() + 18, current.y()) if self.parentWidget() else current
        self._animate(current, end, self.opacity_effect.opacity(), 0.0, 260, QEasingCurve.Type.InCubic, self.hide)

    def _animate(
        self,
        start_pos: QPoint,
        end_pos: QPoint,
        start_opacity: float,
        end_opacity: float,
        duration_ms: int,
        easing: QEasingCurve.Type,
        finished_callback=None,
    ) -> None:
        if self.slide_animation:
            self.slide_animation.stop()
        if self.opacity_animation:
            self.opacity_animation.stop()

        self.slide_animation = QPropertyAnimation(self, b"pos", self)
        self.slide_animation.setStartValue(start_pos)
        self.slide_animation.setEndValue(end_pos)
        self.slide_animation.setDuration(duration_ms)
        self.slide_animation.setEasingCurve(easing)

        self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        self.opacity_animation.setStartValue(start_opacity)
        self.opacity_animation.setEndValue(end_opacity)
        self.opacity_animation.setDuration(duration_ms)
        self.opacity_animation.setEasingCurve(easing)
        if finished_callback:
            self.opacity_animation.finished.connect(finished_callback)

        self.slide_animation.start()
        self.opacity_animation.start()


class SettingsSaveToast(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsSaveToast")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFixedWidth(210)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._fade_out)
        self.opacity_animation: QPropertyAnimation | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 16, 11)
        layout.setSpacing(10)

        icon = QLabel("✓")
        icon.setObjectName("SettingsSaveToastIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(24, 24)
        layout.addWidget(icon)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)
        title = QLabel("保存成功")
        title.setObjectName("SettingsSaveToastTitle")
        message = QLabel("设置已更新")
        message.setObjectName("SettingsSaveToastMessage")
        text_layout.addWidget(title)
        text_layout.addWidget(message)
        layout.addLayout(text_layout, 1)

    def show_message(self) -> None:
        self.adjustSize()
        self.move(self._visible_position())
        self.raise_()
        self.show()
        self._animate(self.opacity_effect.opacity(), 1.0, 180, QEasingCurve.Type.OutCubic)
        self.hide_timer.start(1700)

    def reposition(self) -> None:
        if self.isVisible():
            self.move(self._visible_position())

    def _visible_position(self) -> QPoint:
        parent = self.parentWidget()
        if parent is None:
            return QPoint(0, 0)
        margin = 26
        return QPoint(parent.width() - self.width() - margin, margin)

    def _fade_out(self) -> None:
        self._animate(self.opacity_effect.opacity(), 0.0, 260, QEasingCurve.Type.InCubic, self.hide)

    def _animate(
        self,
        start_opacity: float,
        end_opacity: float,
        duration_ms: int,
        easing: QEasingCurve.Type,
        finished_callback=None,
    ) -> None:
        if self.opacity_animation:
            self.opacity_animation.stop()
        self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        self.opacity_animation.setStartValue(start_opacity)
        self.opacity_animation.setEndValue(end_opacity)
        self.opacity_animation.setDuration(duration_ms)
        self.opacity_animation.setEasingCurve(easing)
        if finished_callback:
            self.opacity_animation.finished.connect(finished_callback)
        self.opacity_animation.start()


class WindowMenuBar(QFrame):
    def __init__(self, parent_window: "MainWindow") -> None:
        super().__init__()
        self.parent_window = parent_window
        self.setObjectName("WindowMenuBar")
        self.setFixedHeight(34)
        self._drag_start: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar_button = self._tool_button("[]", "侧栏")
        self.back_button = self._tool_button("<", "后退")
        self.forward_button = self._tool_button(">", "前进")
        self.sidebar_button.clicked.connect(parent_window.toggle_sidebar)
        self.back_button.clicked.connect(parent_window.navigate_back)
        self.forward_button.clicked.connect(parent_window.navigate_forward)
        for button in [self.sidebar_button, self.back_button, self.forward_button]:
            layout.addWidget(button)

        download_button = self._tool_button("v", "下载")
        download_button.setObjectName("WindowMenuAccentButton")
        download_button.clicked.connect(parent_window.open_output_dir)
        layout.addWidget(download_button)
        layout.addSpacing(12)

        for text in ["文件", "编辑", "查看", "窗口", "帮助"]:
            menu_button = QPushButton(text)
            menu_button.setObjectName("WindowMenuTextButton")
            menu_button.setFixedHeight(30)
            menu_button.setMenu(self._build_menu(text))
            layout.addWidget(menu_button)

        layout.addStretch()

        self.minimize_button = self._window_button("-", "最小化")
        self.maximize_button = self._window_button("□", "最大化")
        self.close_button = self._window_button("x", "关闭")
        self.close_button.setObjectName("WindowCloseButton")
        self.minimize_button.clicked.connect(parent_window.showMinimized)
        self.maximize_button.clicked.connect(parent_window.toggle_maximized)
        self.close_button.clicked.connect(parent_window.close)

        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

    def _tool_button(self, text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("WindowMenuIconButton")
        button.setToolTip(tooltip)
        button.setFixedSize(30, 30)
        return button

    def _window_button(self, text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("WindowControlButton")
        button.setToolTip(tooltip)
        button.setFixedSize(46, 34)
        return button

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_start and event.buttons() & Qt.MouseButton.LeftButton:
            if self.parent_window.isMaximized():
                self.parent_window.showNormal()
                self._drag_start = QPoint(self.parent_window.width() // 2, self.height() // 2)
            self.parent_window.move(event.globalPosition().toPoint() - self._drag_start)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_start = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent_window.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def sync_window_state(self) -> None:
        self.maximize_button.setText("▣" if self.parent_window.isMaximized() else "□")
        self.back_button.setEnabled(self.parent_window.can_navigate_back())
        self.forward_button.setEnabled(self.parent_window.can_navigate_forward())

    def _build_menu(self, name: str) -> QMenu:
        menu = QMenu(self)
        if name == "文件":
            self._add_menu_action(menu, "添加文件", self.parent_window.choose_files_from_menu)
            self._add_menu_action(menu, "打开输出目录", self.parent_window.open_output_dir)
            menu.addSeparator()
            self._add_menu_action(menu, "退出", self.parent_window.close)
        elif name == "编辑":
            self._add_menu_action(menu, "清空任务队列", self.parent_window.clear_current_files)
            self._add_menu_action(menu, "设置", self.parent_window.show_settings_dialog)
        elif name == "查看":
            self._add_menu_action(menu, "主页", lambda: self.parent_window.switch_page("home"))
            self._add_menu_action(menu, "智能媒体增强", lambda: self.parent_window.switch_page("super_resolution"))
            self._add_menu_action(menu, "显示/隐藏侧栏", self.parent_window.toggle_sidebar)
        elif name == "窗口":
            self._add_menu_action(menu, "最小化", self.parent_window.showMinimized)
            self._add_menu_action(menu, "最大化/还原", self.parent_window.toggle_maximized)
        else:
            self._add_menu_action(menu, "关于与更新", self.parent_window.open_about_update)
        return menu

    def _add_menu_action(self, menu: QMenu, text: str, callback) -> None:
        action = QAction(text, menu)
        action.triggered.connect(callback)
        menu.addAction(action)


class SettingsContentPage(QWidget):
    def __init__(self, panel: QWidget) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.panel = panel
        self.scroll_area = CompactScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidget(panel)
        layout.addWidget(self.scroll_area)

    def scroll_to_group(self, title: str | None) -> None:
        if not title:
            self.scroll_area.verticalScrollBar().setValue(0)
            return
        for group in self.panel.findChildren(QGroupBox):
            if title == group.title() or title in group.title():
                position = group.mapTo(self.panel, QPoint(0, 0)).y()
                self.scroll_area.verticalScrollBar().setValue(max(0, position - 12))
                return
        self.scroll_area.verticalScrollBar().setValue(0)

    def save_settings(self) -> None:
        if hasattr(self.panel, "save_settings"):
            self.panel.save_settings()


class PersonalizationPanel(QWidget):
    def __init__(self, apply_callback) -> None:
        super().__init__()
        self.config = AppConfig("personalization")
        self.apply_callback = apply_callback
        self.backgrounds_dir = Path.cwd() / "assets" / "backgrounds"
        self.opacity_slider: QSlider | None = None
        self.component_opacity_slider: QSlider | None = None
        self.motion_slider: QSlider | None = None
        self.bg_opacity_slider: QSlider | None = None
        self.blur_slider: QSlider | None = None
        self.fit_combo: QComboBox | None = None
        self.background_edit: QLineEdit | None = None
        self.overlay_checkbox: QCheckBox | None = None
        self.show_icon_checkbox: QCheckBox | None = None
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(80)
        self.preview_timer.timeout.connect(self._emit_preview)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("个性化")
        title.setObjectName("PanelTitle")
        hint = QLabel("调整窗口透明度、背景图片和背景叠加效果。")
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)

        basic_group = QGroupBox("基础")
        basic_form = QFormLayout(basic_group)
        basic_form.setSpacing(12)
        opacity_row = self._build_slider("window", 70, 100, self.config.get("window_opacity", 100, int))
        basic_form.addRow("窗口不透明度", opacity_row)
        component_opacity_row = self._build_slider("component", 35, 100, self.config.get("component_opacity", 100, int))
        motion_row = self._build_motion_slider(self.config.get("motion_effects", 0, int))
        basic_form.addRow("动态效果", motion_row)
        basic_form.addRow("组件透明度", component_opacity_row)
        self.show_icon_checkbox = QCheckBox("打开启动器时显示 HEA 图标")
        self.show_icon_checkbox.setChecked(self.config.get("show_launcher_icon", True, bool))
        basic_form.addRow("", self.show_icon_checkbox)
        layout.addWidget(basic_group)

        bg_group = QGroupBox("背景图片")
        bg_form = QFormLayout(bg_group)
        bg_form.setSpacing(12)
        self.background_edit = QLineEdit(self.config.get("background_path", ""))
        browse_button = QPushButton("插入图片")
        browse_button.clicked.connect(self._choose_background)
        background_row = QHBoxLayout()
        background_row.addWidget(self.background_edit, 1)
        background_row.addWidget(browse_button)
        bg_form.addRow("背景图片", background_row)

        self.fit_combo = QComboBox()
        self.fit_combo.addItem("裁剪铺满", "center")
        self.fit_combo.addItem("拉伸填充", "stretch")
        self.fit_combo.addItem("平铺", "tile")
        self.fit_combo.setCurrentIndex(max(0, self.fit_combo.findData(self.config.get("background_fit", "center"))))
        bg_form.addRow("适应方式", self.fit_combo)

        bg_opacity_row = self._build_slider("background", 0, 100, self.config.get("background_opacity", 24, int))
        bg_form.addRow("背景透明度", bg_opacity_row)
        blur_row = self._build_slider("blur", 0, 20, self.config.get("background_blur", 0, int))
        bg_form.addRow("背景模糊", blur_row)
        self.overlay_checkbox = QCheckBox("叠加彩色背景")
        self.overlay_checkbox.setChecked(self.config.get("overlay_enabled", True, bool))
        bg_form.addRow("", self.overlay_checkbox)

        actions = QHBoxLayout()
        open_folder = QPushButton("打开文件夹")
        open_folder.setObjectName("GhostButton")
        open_folder.clicked.connect(self._open_background_folder)
        refresh = QPushButton("刷新背景图片")
        refresh.setObjectName("GhostButton")
        refresh.clicked.connect(self._refresh_background)
        clear = QPushButton("清空背景图片")
        clear.setObjectName("GhostButton")
        clear.clicked.connect(self._clear_background)
        actions.addWidget(open_folder)
        actions.addWidget(refresh)
        actions.addWidget(clear)
        actions.addStretch()
        bg_form.addRow("", actions)
        layout.addWidget(bg_group)
        layout.addStretch()

        self._connect_live_preview()

    def _connect_live_preview(self) -> None:
        if self.background_edit:
            self.background_edit.textChanged.connect(lambda _text: self._preview_and_apply())
        for widget in [
            self.opacity_slider,
            self.component_opacity_slider,
            self.motion_slider,
            self.bg_opacity_slider,
            self.blur_slider,
            self.fit_combo,
            self.overlay_checkbox,
            self.show_icon_checkbox,
        ]:
            if isinstance(widget, QSlider):
                widget.valueChanged.connect(lambda _value: self._preview_and_apply())
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(lambda _index: self._preview_and_apply())
            elif widget is not None:
                widget.toggled.connect(lambda _checked: self._preview_and_apply())

    def _build_slider(self, target: str, minimum: int, maximum: int, value: int) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(max(minimum, min(maximum, value)))
        value_label = QLabel(str(slider.value()))
        value_label.setFixedWidth(42)
        slider.valueChanged.connect(lambda next_value: value_label.setText(str(next_value)))
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        if target == "window":
            self.opacity_slider = slider
        elif target == "component":
            self.component_opacity_slider = slider
        elif target == "background":
            self.bg_opacity_slider = slider
        else:
            self.blur_slider = slider
        return container

    def _build_motion_slider(self, value: int) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        low_label = QLabel("无动态效果")
        low_label.setObjectName("MutedText")
        high_label = QLabel("高动态效果")
        high_label.setObjectName("MutedText")

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 1)
        slider.setSingleStep(1)
        slider.setPageStep(1)
        slider.setTickInterval(1)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        slider.setValue(1 if value else 0)
        self.motion_slider = slider

        row.addWidget(low_label)
        row.addWidget(slider, 1)
        row.addWidget(high_label)
        return container

    def _open_background_folder(self) -> None:
        self.backgrounds_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.backgrounds_dir.resolve())))

    def _choose_background(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "选择背景媒体",
            str(self.backgrounds_dir),
            "Media (*.jpg *.jpeg *.png *.webp *.bmp *.mp4 *.mov *.mkv *.avi *.webm *.m4v);;Images (*.jpg *.jpeg *.png *.webp *.bmp);;Videos (*.mp4 *.mov *.mkv *.avi *.webm *.m4v)",
        )
        if selected and self.background_edit:
            self.background_edit.setText(selected)

    def _refresh_background(self) -> None:
        if self.background_edit and not self.background_edit.text().strip():
            media_files: list[Path] = []
            if self.backgrounds_dir.exists():
                for suffix in sorted(BACKGROUND_IMAGE_EXTENSIONS | BACKGROUND_VIDEO_EXTENSIONS):
                    media_files.extend(self.backgrounds_dir.glob(f"*{suffix}"))
                    media_files.extend(self.backgrounds_dir.glob(f"*{suffix.upper()}"))
            if media_files:
                self.background_edit.setText(str(media_files[0]))

    def _clear_background(self) -> None:
        if self.background_edit:
            self.background_edit.clear()

    def _current_values(self) -> dict[str, object]:
        return {
            "window_opacity": self.opacity_slider.value() if self.opacity_slider else 100,
            "component_opacity": self.component_opacity_slider.value() if self.component_opacity_slider else 100,
            "motion_effects": self.motion_slider.value() if self.motion_slider else 0,
            "background_path": self.background_edit.text().strip() if self.background_edit else "",
            "background_fit": self.fit_combo.currentData() if self.fit_combo else "center",
            "background_opacity": self.bg_opacity_slider.value() if self.bg_opacity_slider else 24,
            "background_blur": self.blur_slider.value() if self.blur_slider else 0,
            "overlay_enabled": self.overlay_checkbox.isChecked() if self.overlay_checkbox else True,
            "show_launcher_icon": self.show_icon_checkbox.isChecked() if self.show_icon_checkbox else True,
        }

    def _preview_and_apply(self) -> None:
        self.preview_timer.start()

    def _emit_preview(self) -> None:
        self.apply_callback(self._current_values())

    def _save_and_apply(self) -> None:
        values = self._current_values()
        for key, value in values.items():
            self.config.set(key, value)
        self.apply_callback(values)

    def save_settings(self) -> None:
        self._save_and_apply()


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, personalization_callback=None, update_callback=None) -> None:
        super().__init__(parent)
        self.personalization_callback = personalization_callback or (lambda: None)
        self.update_callback = update_callback or (lambda _info: None)
        self.setObjectName("AppShell")
        self.setWindowTitle("设置")
        self.setWindowFlag(Qt.Window, True)
        self.setMinimumSize(920, 620)
        self.resize(1180, 760)
        self.nav_buttons: dict[str, QPushButton] = {}
        self.page_factories = {}
        self.page_widgets: dict[str, QWidget] = {}
        self._centered_once = False
        self.save_toast = SettingsSaveToast(self)
        self.save_toast.hide()

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        sidebar = GlassSidebar()
        sidebar.setFixedWidth(230)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(16, 18, 16, 18)
        side_layout.setSpacing(6)

        title = QLabel("设置")
        title.setObjectName("CardTitle")
        hint = QLabel("引擎与工具")
        hint.setObjectName("MutedText")
        side_layout.addWidget(title)
        side_layout.addWidget(hint)
        side_layout.addSpacing(12)

        self.stack = StableStackedWidget()
        self.page_keys: list[str] = []
        self._add_settings_page("engine_base", lambda: EngineSettingsPanel("base"))
        self._add_settings_page("engine_image", lambda: EngineSettingsPanel("image"))
        self._add_settings_page("engine_video", lambda: EngineSettingsPanel("video"))
        self._add_settings_page("tool_settings", lambda: SettingsContentPage(ToolSettingsPanel()))
        self._add_settings_page("personalization", lambda: SettingsContentPage(PersonalizationPanel(self.personalization_callback)))
        self._add_settings_page("about_update", self._build_about_update_page)

        self._add_nav_group_label(side_layout, "引擎设置")
        self._add_settings_nav(side_layout, "engine_base", "基础配置")
        self._add_settings_nav(side_layout, "engine_image", "图片超分引擎")
        self._add_settings_nav(side_layout, "engine_video", "视频插帧引擎")
        side_layout.addSpacing(8)
        self._add_nav_group_label(side_layout, "工具管理")
        self._add_settings_nav(side_layout, "tool_settings", "工具管理")
        side_layout.addSpacing(8)
        self._add_nav_group_label(side_layout, "外观")
        self._add_settings_nav(side_layout, "personalization", "个性化")
        side_layout.addSpacing(8)
        self._add_nav_group_label(side_layout, "应用")
        self._add_settings_nav(side_layout, "about_update", "关于与更新")
        side_layout.addStretch()

        save_button = QPushButton("保存设置")
        save_button.clicked.connect(self.save_settings)
        side_layout.addWidget(save_button)

        close_button = QPushButton("关闭")
        close_button.setObjectName("GhostButton")
        close_button.clicked.connect(self.accept)
        side_layout.addWidget(close_button)

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)
        self.switch_page("engine_base")

    def _add_settings_page(self, key: str, page_factory) -> None:
        self.page_keys.append(key)
        placeholder = QWidget()
        self.page_factories[key] = page_factory
        self.page_widgets[key] = placeholder
        self.stack.addWidget(placeholder)

    def _build_about_update_page(self) -> QWidget:
        panel = AboutUpdatePanel()
        panel.update_checked.connect(self.update_callback)
        return SettingsContentPage(panel)

    def _add_nav_group_label(self, layout: QVBoxLayout, text: str) -> None:
        label = QLabel(text)
        label.setObjectName("MutedText")
        layout.addWidget(label)

    def _add_settings_nav(self, layout: QVBoxLayout, key: str, text: str) -> None:
        button = QPushButton(text)
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.setFixedHeight(34)
        button.clicked.connect(lambda _checked=False, nav_key=key: self.switch_page(nav_key))
        self.nav_buttons[key] = button
        layout.addWidget(button)

    def switch_page(self, page_key: str) -> None:
        if page_key not in self.page_keys:
            return
        index = self.page_keys.index(page_key)
        if page_key in self.page_factories:
            placeholder = self.page_widgets[page_key]
            try:
                page = self.page_factories[page_key]()
            except Exception as exc:
                page = QWidget()
                error_layout = QVBoxLayout(page)
                error_layout.setContentsMargins(24, 24, 24, 24)
                error_label = QLabel(f"设置页面加载失败：{exc}")
                error_label.setObjectName("MutedText")
                error_label.setWordWrap(True)
                error_layout.addWidget(error_label)
                error_layout.addStretch()
            else:
                self.page_factories.pop(page_key)
            self.page_widgets[page_key] = page
            self.stack.removeWidget(placeholder)
            placeholder.deleteLater()
            self.stack.insertWidget(index, page)
        self.stack.setCurrentIndex(index)
        for button_key, button in self.nav_buttons.items():
            button.setChecked(button_key == page_key)

    def save_settings(self) -> None:
        for page in self.page_widgets.values():
            if hasattr(page, "save_settings"):
                page.save_settings()
        self.save_toast.show_message()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._centered_once:
            return
        self._centered_once = True
        self._resize_for_parent()
        self._center_on_parent()

    def _resize_for_parent(self) -> None:
        parent = self.parentWidget()
        if not parent:
            return
        parent_frame = parent.frameGeometry()
        available = self.screen().availableGeometry() if self.screen() else parent_frame
        width = min(int(parent_frame.width() * 0.9), available.width() - 80)
        height = min(int(parent_frame.height() * 0.82), available.height() - 120)
        width = max(1040, min(width, 1440))
        height = max(620, min(height, 820))
        self.resize(width, height)

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        if parent:
            parent_frame = parent.frameGeometry()
            dialog_frame = self.frameGeometry()
            dialog_frame.moveCenter(parent_frame.center())
            self.move(dialog_frame.topLeft())
            return
        screen = self.screen()
        if screen:
            dialog_frame = self.frameGeometry()
            dialog_frame.moveCenter(screen.availableGeometry().center())
            self.move(dialog_frame.topLeft())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.save_toast.reposition()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.resize(1360, 860)
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
        self.open_output_button: QPushButton | None = None
        self.retry_failed_button: QPushButton | None = None
        self.current_progress_label: QLabel | None = None
        self.status_label: QLabel | None = None
        self.progress_percent_label: QLabel | None = None
        self.log_dialog: QDialog | None = None
        self.log_dialog_box: QTextEdit | None = None
        self.settings_dialog: SettingsDialog | None = None
        self.settings_button: QPushButton | None = None
        self.toolbar_title: QLabel | None = None
        self.toolbar_subtitle: QLabel | None = None
        self.toolbar_health: QLabel | None = None
        self.toolbar_compact_status: QLabel | None = None
        self.window_menu_bar: WindowMenuBar | None = None
        self.sidebar_widget: QWidget | None = None
        self.bottom_panel: QWidget | None = None
        self.background_layer: QFrame | None = None
        self.background_label: QLabel | None = None
        self.background_mask: QWidget | None = None
        self.background_video_view: QGraphicsView | None = None
        self.background_video_scene: QGraphicsScene | None = None
        self.background_video_item: QGraphicsVideoItem | None = None
        self.background_pixmap: QPixmap | None = None
        self.background_render_cache_key: tuple[int, int, str, str] | None = None
        self.background_render_cache: QPixmap | None = None
        self.background_player: QMediaPlayer | None = None
        self.background_audio_output: QAudioOutput | None = None
        self.background_media_path = ""
        self.background_media_type = ""
        self.background_fit_mode = "center"
        self.personalization_component_alpha: int | None = None
        self.personalization_background_opacity: int | None = None
        self.settings_paused_background_video = False
        self.combo_paused_background_video = False
        self.combo_popup_pause_count = 0
        self.current_task: ImageBatchTask | None = None
        self.update_check_task: UpdateCheckTask | None = None
        self.latest_update_info: UpdateInfo | None = None
        self.last_failed_files: list[Path] = []
        self.last_failed_feature_key: str | None = None
        self.log_messages: list[str] = []
        self.task_completion_toast: TaskCompletionToast | None = None
        self.sidebar_visible = True
        self.page_history: list[str] = []
        self.page_history_index = -1
        self._syncing_page_history = False

        self.shell = AppShell()
        self.setCentralWidget(self.shell)
        self.window_menu_bar = WindowMenuBar(self)
        self.shell.layout.insertWidget(0, self.window_menu_bar)
        self.background_layer = QFrame(self.shell)
        self.background_layer.setObjectName("PersonalizationBackgroundLayer")
        self.background_layer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.background_layer.hide()
        self.background_layer.lower()

        self.background_label = QLabel(self.background_layer)
        self.background_label.setObjectName("PersonalizationBackground")
        self.background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.background_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.background_label.hide()
        self.background_label.lower()
        self.background_video_scene = QGraphicsScene(self.background_layer)
        self.background_video_item = QGraphicsVideoItem()
        self.background_video_scene.addItem(self.background_video_item)
        self.background_video_view = QGraphicsView(self.background_video_scene, self.background_layer)
        self.background_video_view.setObjectName("PersonalizationBackgroundVideo")
        self.background_video_view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.background_video_view.setFrameShape(QFrame.Shape.NoFrame)
        self.background_video_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.background_video_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.background_video_view.setStyleSheet("background: transparent; border: none;")
        self.background_video_view.hide()
        self.background_video_view.lower()
        self.background_mask = QWidget(self.background_layer)
        self.background_mask.setObjectName("PersonalizationBackgroundMask")
        self.background_mask.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.background_mask.hide()
        self.background_player = QMediaPlayer(self)
        self.background_audio_output = QAudioOutput(self)
        self.background_audio_output.setVolume(0)
        self.background_player.setAudioOutput(self.background_audio_output)
        self.background_player.setVideoOutput(self.background_video_item)
        if hasattr(self.background_player, "setLoops"):
            self.background_player.setLoops(QMediaPlayer.Loops.Infinite)
        self.background_player.mediaStatusChanged.connect(self._handle_background_media_status)
        self._build_toolbar(self.shell.toolbar)
        self.shell.toolbar.hide()

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(16)
        self.shell.workspace_layout.addLayout(content, 1)

        self.sidebar_widget = self._build_sidebar()
        content.addWidget(self.sidebar_widget)

        self.stack = StableStackedWidget()
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
        if hasattr(self.features.get("super_resolution"), "bind_file_panel"):
            self.features["super_resolution"].bind_file_panel(self.file_panel)

        self.bottom_panel = self._build_bottom_panel()
        self.shell.body_layout.addWidget(self.bottom_panel)
        self.task_completion_toast = TaskCompletionToast(self.shell)
        self.task_completion_toast.hide()
        self.switch_page("home")
        self._set_running(False)
        QTimer.singleShot(0, self._finish_deferred_startup)

    def _finish_deferred_startup(self) -> None:
        self._log_tool_health()
        self._apply_personalization()
        self._start_auto_update_check()

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        if self.window_menu_bar:
            self.window_menu_bar.sync_window_state()

    def toggle_sidebar(self) -> None:
        self.sidebar_visible = not self.sidebar_visible
        if self.sidebar_widget:
            self.sidebar_widget.setVisible(self.sidebar_visible)

    def can_navigate_back(self) -> bool:
        return self.page_history_index > 0

    def can_navigate_forward(self) -> bool:
        return 0 <= self.page_history_index < len(self.page_history) - 1

    def navigate_back(self) -> None:
        if not self.can_navigate_back():
            return
        self.page_history_index -= 1
        self._syncing_page_history = True
        try:
            self.switch_page(self.page_history[self.page_history_index])
        finally:
            self._syncing_page_history = False
        if self.window_menu_bar:
            self.window_menu_bar.sync_window_state()

    def navigate_forward(self) -> None:
        if not self.can_navigate_forward():
            return
        self.page_history_index += 1
        self._syncing_page_history = True
        try:
            self.switch_page(self.page_history[self.page_history_index])
        finally:
            self._syncing_page_history = False
        if self.window_menu_bar:
            self.window_menu_bar.sync_window_state()

    def choose_files_from_menu(self) -> None:
        if hasattr(self, "file_panel") and self.file_panel.isVisible():
            self.file_panel.choose_files()

    def clear_current_files(self) -> None:
        if self.is_running:
            return
        if hasattr(self, "file_panel") and self.file_panel.isVisible():
            self.file_panel.clear_files()

    def open_about_update(self) -> None:
        self.show_settings_dialog()
        if self.settings_dialog:
            self.settings_dialog.switch_page("about_update")

    def _build_toolbar(self, toolbar: QFrame) -> None:
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(16)

        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        self.toolbar_title = QLabel(f"{APP_NAME} v{APP_VERSION}")
        self.toolbar_title.setObjectName("CardTitle")
        self.toolbar_subtitle = QLabel("High-quality Enhancement Assistant")
        self.toolbar_subtitle.setObjectName("MutedText")
        title_block.addWidget(self.toolbar_title)
        title_block.addWidget(self.toolbar_subtitle)
        layout.addLayout(title_block, 1)

        self.toolbar_compact_status = QLabel("状态：就绪")
        self.toolbar_compact_status.setObjectName("MutedText")
        self.toolbar_compact_status.hide()
        layout.addWidget(self.toolbar_compact_status, 1)

        self.toolbar_health = QLabel("Liquid Glass AppShell · Local batch workstation")
        self.toolbar_health.setObjectName("MutedText")
        layout.addWidget(self.toolbar_health)


    def _build_sidebar(self) -> QWidget:
        sidebar = GlassSidebar()
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(8)

        brand = QLabel(APP_NAME)
        brand.setObjectName("CardTitle")
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("MutedText")
        layout.addWidget(brand)
        layout.addWidget(version)
        layout.addSpacing(14)

        self._add_nav_button(layout, "home", "⌂", "首页")
        self._add_nav_button(layout, "compress", "◱", "图片压缩")
        self._add_nav_button(layout, "convert", "⇄", "格式转换")
        self._add_nav_button(layout, "resize", "#", "批量改尺寸")
        self._add_nav_button(layout, "watermark", "◇", "批量加水印")
        self._add_nav_button(layout, "rename", "Aa", "批量重命名")
        self._add_nav_button(layout, "super_resolution", "✦", "智能媒体增强")
        layout.addStretch()

        self.run_button = QPushButton("开始处理")
        self.run_button.clicked.connect(self.run_current_feature)
        self.pause_button = QPushButton("暂停")
        self.pause_button.setObjectName("GhostButton")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.cancel_button = QPushButton("停止")
        self.cancel_button.setObjectName("GhostButton")
        self.cancel_button.clicked.connect(self.cancel_task)
        self.open_output_button = QPushButton("打开输出目录")
        self.open_output_button.setObjectName("GhostButton")
        self.open_output_button.clicked.connect(self.open_output_dir)
        layout.addWidget(self.run_button)
        layout.addWidget(self.pause_button)
        layout.addWidget(self.cancel_button)
        layout.addWidget(self.open_output_button)
        self._set_action_buttons_visible(False)
        return sidebar

    def _add_nav_button(self, layout: QVBoxLayout, key: str, icon: str, text: str) -> None:
        button = QPushButton(text)
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.setFixedHeight(40)
        button.clicked.connect(lambda _checked=False, page_key=key: self.switch_page(page_key))
        self.nav_buttons[key] = button
        layout.addWidget(button)

    def _build_home(self) -> HomePanel:
        home = HomePanel()
        home.feature_requested.connect(self.switch_page)
        return home

    def _add_page(self, key: str, widget: QWidget) -> None:
        self.page_keys.append(key)
        self.stack.addWidget(widget)

    def switch_page(self, key: str) -> None:
        if key not in self.page_keys:
            return
        if not self._syncing_page_history:
            if self.page_history_index < 0 or self.page_history[self.page_history_index] != key:
                self.page_history = self.page_history[: self.page_history_index + 1]
                self.page_history.append(key)
                self.page_history_index = len(self.page_history) - 1
        window_geometry = self.geometry()
        window_state = self.windowState()
        self.setUpdatesEnabled(False)
        processing_pages = {"compress", "convert", "resize", "watermark", "rename", "super_resolution"}
        is_processing_page = key in processing_pages
        runnable_pages = set(self.features)
        try:
            self.stack.setCurrentIndex(self.page_keys.index(key))
            for button_key, button in self.nav_buttons.items():
                button.setChecked(button_key == key)
            self.shell.toolbar.hide()
            self._set_action_buttons_visible(key in runnable_pages)
            if key == "super_resolution" and hasattr(self.features.get("super_resolution"), "refresh_from_engine_settings"):
                self.features["super_resolution"].refresh_from_engine_settings()
            if hasattr(self, "file_panel"):
                self.file_panel.configure_media_mode(key == "super_resolution")
                self.file_panel.setVisible(is_processing_page)
            if self.bottom_panel:
                self.bottom_panel.setVisible(is_processing_page)
            self._notify_file_context_changed()
            self._update_background_layer()
            if self.window_menu_bar:
                self.window_menu_bar.sync_window_state()
        finally:
            self.setUpdatesEnabled(True)
            self.setWindowState(window_state)
            if not (window_state & (Qt.WindowMaximized | Qt.WindowFullScreen)):
                self.setGeometry(window_geometry)

    def run_current_feature(self) -> None:
        if self.is_running:
            self._log("已有任务正在处理，请等待完成。")
            return

        key = self.page_keys[self.stack.currentIndex()]
        if key == "home":
            self._log("请先选择左侧的功能模块。")
            return

        feature = self.features[key]
        files = list(feature.get_workbench_files()) if hasattr(feature, "get_workbench_files") else list(self.file_panel.files)
        if not files:
            self._log("请先添加要处理的文件。")
            return

        self._set_progress(0)
        if hasattr(feature, "reset_statuses"):
            feature.reset_statuses()
            if key == "super_resolution":
                self.file_panel.reset_statuses()
        else:
            self.file_panel.reset_statuses()
        try:
            task = feature.create_task(files)
            if task is None:
                processor = feature.create_processor(files)
                task = ImageBatchTask(files, processor)
        except Exception as exc:
            self._log(f"参数错误：{exc}")
            return

        self._start_task(key, feature.title, files, task, feature)

    def _start_task(self, key: str, title: str, files: list[Path], task, feature=None) -> None:
        feature = feature or self.features.get(key)
        task.signals.log.connect(self._log)
        if hasattr(task.signals, "debug"):
            task.signals.debug.connect(self._log_debug)
        task.signals.progress.connect(self._set_progress)
        if hasattr(feature, "set_page_progress"):
            task.signals.progress.connect(feature.set_page_progress)
        if hasattr(task.signals, "current_progress"):
            task.signals.current_progress.connect(self._set_current_progress)
            if hasattr(feature, "set_current_progress"):
                task.signals.current_progress.connect(feature.set_current_progress)
        if key == "super_resolution" and hasattr(feature, "set_file_status"):
            task.signals.file_status.connect(feature.set_file_status)
            task.signals.file_status.connect(self.file_panel.set_file_status)
        elif hasattr(feature, "set_file_status"):
            task.signals.file_status.connect(feature.set_file_status)
        else:
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
        if hasattr(feature, "clear_files") and hasattr(feature, "add_files"):
            feature.clear_files()
            feature.add_files(self.last_failed_files)
        else:
            self.file_panel.clear_files()
            self.file_panel.add_files(self.last_failed_files)
        self._set_progress(0)
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
        self._show_task_completion_toast(
            "任务完成",
            f"成功 {success_count} 个，失败 {failed_count} 个。",
        )
        self.current_task = None
        self._set_running(False)

    def _super_resolution_finished(self, summary: SuperResolutionSummary) -> None:
        elapsed = self._format_elapsed(summary.elapsed_seconds)
        self.last_failed_files = [item.source for item in summary.failed_items]
        self.last_failed_feature_key = "super_resolution" if self.last_failed_files else None
        self._log(
            f"智能媒体增强完成。总数量 {summary.total}，成功 {summary.success_count}，失败 {summary.failed_count}，跳过 {summary.skipped_count}，耗时 {elapsed}。"
        )
        self._log(f"输出目录：{summary.output_dir}")
        if summary.failed_items:
            self._log("失败项/失败日志：")
            for item in summary.failed_items:
                self._log(f"- {item.source.name}：{item.reason}")
        if self.current_progress_label:
            self.current_progress_label.setText("当前：已完成")
        self._show_task_completion_toast(
            "智能媒体增强完成",
            f"成功 {summary.success_count} 个，失败 {summary.failed_count} 个，跳过 {summary.skipped_count} 个。耗时 {elapsed}。",
        )
        self.current_task = None
        self._set_running(False)

    def _show_task_completion_toast(self, title: str, message: str) -> None:
        if self.task_completion_toast:
            self.task_completion_toast.show_message(title, message)

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
        if self.status_label:
            self.status_label.setText("状态：处理中" if is_running else "状态：就绪")
        if self.toolbar_compact_status:
            self.toolbar_compact_status.setText("状态：处理中" if is_running else "状态：就绪")

    def _set_action_buttons_visible(self, visible: bool) -> None:
        for button in [self.run_button, self.pause_button, self.cancel_button, self.open_output_button]:
            if button:
                button.setVisible(visible)

    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        self.log_messages.append(line)
        self.log_messages = self.log_messages[-2000:]
        if self.log_dialog_box:
            self.log_dialog_box.append(line)
        key = self.page_keys[self.stack.currentIndex()] if hasattr(self, "stack") and self.page_keys else ""
        feature = self.features.get(key)
        if feature and hasattr(feature, "append_log"):
            feature.append_log(line)

    def _log_debug(self, message: str) -> None:
        self._log(message)

    def _log_tool_health(self) -> None:
        health_map = get_tool_manager().refresh(read_versions=False)
        for tool_id in ["ffmpeg", "ffprobe", "rife"]:
            health = health_map[tool_id]
            if health.available and health.path:
                self._log(f"检测到 {health.display_name}：{health.path}")
            else:
                self._log(f"未检测到 {health.display_name}：请到工具管理中配置或导入。")

    def _start_auto_update_check(self) -> None:
        config = AppConfig("updates")
        if not config.get("auto_check", True, bool):
            return
        saved_urls = config.get("manifest_urls", "", str) or config.get("manifest_url", "", str)
        manifest_urls = parse_url_list(saved_urls) or list(DEFAULT_UPDATE_MANIFEST_URLS)
        self.update_check_task = UpdateCheckTask(manifest_urls)
        self.update_check_task.signals.finished.connect(lambda info: self._handle_update_checked(info, True))
        self.update_check_task.signals.failed.connect(self._handle_auto_update_failed)
        self.thread_pool.start(self.update_check_task)

    def _handle_auto_update_failed(self, message: str) -> None:
        self.update_check_task = None
        self._log(f"自动检查更新失败：{message}")

    def _handle_update_checked(self, info: UpdateInfo, from_auto_check: bool = False) -> None:
        self.update_check_task = None
        self.latest_update_info = info
        if info.has_update:
            self._log(f"发现新版本：v{info.latest_version}（当前 v{info.current_version}）。")
            if self.status_label:
                self.status_label.setText(f"状态：发现新版本 v{info.latest_version}")
            if from_auto_check:
                self._prompt_open_update(info)
            return
        if not from_auto_check:
            self._log(f"当前已是最新版本：v{info.current_version}。")

    def _prompt_open_update(self, info: UpdateInfo) -> None:
        choice = QMessageBox.question(
            self,
            "发现新版本",
            f"发现 {APP_NAME} v{info.latest_version}，当前版本 v{info.current_version}。是否打开发布页查看更新？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if choice == QMessageBox.StandardButton.Yes and info.release_url:
            QDesktopServices.openUrl(QUrl(info.release_url))

    def _build_bottom_panel(self) -> QWidget:
        panel = GlassStatusBar()
        panel.setFixedHeight(48)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(12)

        self.status_label = QLabel("状态：就绪")
        self.status_label.setObjectName("BottomStatusText")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedWidth(180)
        self.progress_bar.setFixedHeight(16)
        layout.addWidget(self.progress_bar)

        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setObjectName("BottomStatusText")
        self.progress_percent_label.setFixedWidth(42)
        layout.addWidget(self.progress_percent_label)

        self.current_progress_label = QLabel("当前：未开始")
        self.current_progress_label.setObjectName("BottomStatusText")
        layout.addWidget(self.current_progress_label, 1)

        self.settings_button = QPushButton("设置")
        self.settings_button.setObjectName("BottomActionButton")
        self.settings_button.setFixedSize(78, 34)
        self.settings_button.clicked.connect(self.show_settings_dialog)
        layout.addWidget(self.settings_button)

        log_button = QPushButton("查看日志")
        log_button.setObjectName("BottomActionButton")
        log_button.setFixedSize(96, 34)
        log_button.clicked.connect(self.show_log_dialog)
        layout.addWidget(log_button)

        self.log_box = QTextEdit(panel)
        self.log_box.setReadOnly(True)
        self.log_box.hide()
        return panel

    def _set_progress(self, value: int) -> None:
        clamped_value = max(0, min(100, int(value)))
        self.progress_bar.setValue(clamped_value)
        if self.progress_percent_label:
            self.progress_percent_label.setText(f"{clamped_value}%")

    def _reset_bottom_status(self) -> None:
        self._set_progress(0)
        if self.status_label:
            self.status_label.setText("状态：就绪")
        if self.current_progress_label:
            self.current_progress_label.setText("当前：未开始")

    def _clear_log(self) -> None:
        self.log_messages.clear()
        self.log_box.clear()
        if self.log_dialog_box:
            self.log_dialog_box.clear()

    def show_log_dialog(self) -> None:
        if self.log_dialog:
            self.log_dialog.raise_()
            self.log_dialog.activateWindow()
            return
        dialog = QDialog(self)
        self.log_dialog = dialog
        dialog.setWindowTitle("任务日志")
        dialog.resize(760, 460)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.log_dialog_box = QTextEdit(dialog)
        self.log_dialog_box.setReadOnly(True)
        self.log_dialog_box.setPlainText("\n".join(self.log_messages))
        layout.addWidget(self.log_dialog_box)

        buttons = QHBoxLayout()
        open_output_button = QPushButton("打开输出目录")
        open_output_button.setObjectName("GhostButton")
        open_output_button.clicked.connect(self.open_output_dir)
        self.retry_failed_button = QPushButton("重试失败项")
        self.retry_failed_button.setObjectName("GhostButton")
        self.retry_failed_button.setEnabled((not self.is_running) and bool(self.last_failed_files))
        self.retry_failed_button.clicked.connect(self.retry_failed_items)
        clear_button = QPushButton("清空日志")
        clear_button.setObjectName("GhostButton")
        clear_button.clicked.connect(self._clear_log)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.accept)
        buttons.addWidget(open_output_button)
        buttons.addWidget(self.retry_failed_button)
        buttons.addWidget(clear_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        def reset_log_dialog(_result: int) -> None:
            self.log_dialog = None
            self.log_dialog_box = None

        dialog.finished.connect(reset_log_dialog)
        dialog.show()

    def show_settings_dialog(self) -> None:
        if self.settings_dialog:
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
        self.settings_paused_background_video = self._pause_background_video_for_settings()
        dialog = SettingsDialog(self, self._apply_personalization, self._handle_update_checked)
        self.settings_dialog = dialog

        def reset_settings_dialog(_result: int) -> None:
            self.settings_dialog = None
            self._resume_background_video_after_settings()
            feature = self.features.get("super_resolution")
            if hasattr(feature, "refresh_from_engine_settings"):
                feature.refresh_from_engine_settings()

        dialog.finished.connect(reset_settings_dialog)
        dialog.show()

    def _pause_background_video_for_settings(self) -> bool:
        if not self.background_player or self.background_media_type != "video":
            return False
        if self.background_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            return False
        self.background_player.pause()
        return True

    def _resume_background_video_after_settings(self) -> None:
        if not self.settings_paused_background_video:
            return
        self.settings_paused_background_video = False
        if self.background_player and self.background_media_type == "video":
            self.background_player.play()

    def _pause_background_video_for_combo(self) -> None:
        self.combo_popup_pause_count += 1
        if self.combo_popup_pause_count > 1:
            return
        self.combo_paused_background_video = self._pause_background_video_for_settings()

    def _resume_background_video_after_combo(self) -> None:
        if self.combo_popup_pause_count <= 0:
            return
        self.combo_popup_pause_count -= 1
        if self.combo_popup_pause_count > 0 or not self.combo_paused_background_video:
            return
        self.combo_paused_background_video = False
        if self.background_player and self.background_media_type == "video":
            self.background_player.play()

    def _apply_personalization(self, preview: dict[str, object] | None = None) -> None:
        config = AppConfig("personalization")
        values = preview or {}

        def value(key: str, default, value_type=None):
            return values[key] if key in values else config.get(key, default, value_type)

        opacity = int(value("window_opacity", 100, int))
        self.setWindowOpacity(max(70, min(100, opacity)) / 100)

        background_path = str(value("background_path", ""))
        fit_mode = str(value("background_fit", "center"))
        background_opacity = max(0, min(100, int(value("background_opacity", 24, int))))
        component_opacity = max(35, min(100, int(value("component_opacity", 100, int))))
        component_alpha = int(255 * component_opacity / 100)
        component_style = ""
        if self.personalization_component_alpha != component_alpha:
            component_style = f"""
            QFrame#GlassToolbar,
            QFrame#GlassSidebar,
            QFrame#GlassPanel,
            QFrame#GlassStatusBar,
            QFrame#RightPanel,
            QFrame#BottomPanel,
            QFrame#LiquidShell,
            QFrame#LiquidHeroPanel,
            QFrame#LiquidGlassCard,
            QFrame#FeatureCard,
            QFrame#SuperGlassCard,
            QFrame#SuperModeBar,
            QFrame#SuperTaskCenter,
            QFrame#SuperWorkflowBar,
            QFrame#SuperStatusBar,
            QFrame#LiquidTaskList,
            QFrame#LiquidTaskHeaderRow,
            QFrame#LiquidTaskRow,
            QGroupBox {{
                background: rgba(255, 255, 255, {component_alpha});
            }}
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QListWidget, QTableWidget {{
                background: rgba(255, 255, 255, {component_alpha});
            }}
            QPushButton#GhostButton,
            QPushButton#NavButton,
            QPushButton#LiquidPillButton,
            QLabel#QueueStatPill,
            QWidget#TaskQueueItem,
            QLabel#TaskThumb,
            QFrame#SuperAdvancedPanel,
            QPlainTextEdit#SuperRecentLog,
            QLabel#SuperDropZone,
            QLabel#SuperTaskEmpty {{
                background: rgba(245, 247, 251, {component_alpha});
            }}
        """
            self.personalization_component_alpha = component_alpha

        background_file = Path(background_path) if background_path else None
        if background_file and background_file.exists():
            if background_file.suffix.lower() in BACKGROUND_VIDEO_EXTENSIONS:
                if self.background_media_type != "video" or self.background_media_path != str(background_file):
                    self._set_background_video(background_file)
            else:
                if self.background_media_type != "image" or self.background_media_path != str(background_file):
                    self._set_background_image(background_file)
        else:
            self._clear_background_media()
        if self.background_fit_mode != fit_mode:
            self.background_fit_mode = fit_mode
            self.background_render_cache_key = None
            self.background_render_cache = None
        if self.personalization_background_opacity != background_opacity:
            self._set_background_mask_opacity(background_opacity)
            self.personalization_background_opacity = background_opacity
        self._update_background_layer()

        if component_style or (component_opacity >= 100 and self.shell.styleSheet()):
            self.shell.setStyleSheet(component_style if component_opacity < 100 else "")

    def _set_background_image(self, path: Path) -> None:
        if self.background_player:
            self.background_player.stop()
        if self.background_video_view:
            self.background_video_view.hide()
        pixmap = QPixmap(str(path))
        self.background_pixmap = pixmap if not pixmap.isNull() else None
        self.background_media_path = str(path)
        self.background_media_type = "image" if self.background_pixmap else ""
        self.background_render_cache_key = None
        self.background_render_cache = None

    def _set_background_video(self, path: Path) -> None:
        if not self.background_player:
            return
        self.background_pixmap = None
        self.background_render_cache_key = None
        self.background_render_cache = None
        path_text = str(path)
        if self.background_media_type != "video" or self.background_media_path != path_text:
            self.background_player.setSource(QUrl.fromLocalFile(path_text))
            self.background_media_path = path_text
        self.background_media_type = "video"
        self.background_player.play()

    def _clear_background_media(self) -> None:
        self.background_pixmap = None
        self.background_media_path = ""
        self.background_media_type = ""
        if self.background_player:
            self.background_player.stop()
            self.background_player.setSource(QUrl())
        if self.background_video_view:
            self.background_video_view.hide()
        if self.background_layer:
            self.background_layer.hide()
        if self.background_label:
            self.background_label.clear()
            self.background_label.hide()

    def _set_background_mask_opacity(self, background_opacity: int) -> None:
        if not self.background_mask:
            return
        mask_alpha = int(255 * (100 - max(0, min(100, background_opacity))) / 100)
        self.background_mask.setStyleSheet(f"background: rgba(245, 247, 251, {mask_alpha});")

    def _handle_background_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self.background_player and self.background_media_type == "video":
            self.background_player.setPosition(0)
            self.background_player.play()

    def _update_background_layer(self) -> None:
        if not self.background_layer or not self.background_label:
            return
        self.background_layer.setGeometry(self.shell.rect())
        self.background_layer.lower()
        self.background_label.setGeometry(self.background_layer.rect())
        self.background_label.lower()
        if self.background_video_view:
            self.background_video_view.setGeometry(self.background_layer.rect())
            self.background_video_view.lower()
        if self.background_video_scene:
            self.background_video_scene.setSceneRect(self.background_layer.rect())
        if self.background_video_item:
            self.background_video_item.setSize(QSizeF(self.background_layer.width(), self.background_layer.height()))
        if self.background_mask:
            self.background_mask.setGeometry(self.background_layer.rect())
            self.background_mask.raise_()

        def show_background_layer() -> None:
            self.background_layer.show()
            self.background_layer.lower()
            if self.background_mask:
                self.background_mask.show()
                self.background_mask.raise_()

        def hide_background_layer() -> None:
            if self.background_mask:
                self.background_mask.hide()
            self.background_layer.hide()

        if self.background_video_view and self.background_video_item:
            if self.background_media_type == "video":
                if self.background_fit_mode == "stretch":
                    self.background_video_item.setAspectRatioMode(Qt.AspectRatioMode.IgnoreAspectRatio)
                else:
                    self.background_video_item.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)
                self.background_label.clear()
                self.background_label.hide()
                self.background_video_view.show()
                self.background_video_view.lower()
                show_background_layer()
                return

        if not self.background_pixmap or self.background_pixmap.isNull():
            self.background_label.clear()
            self.background_label.hide()
            if self.background_video_view:
                self.background_video_view.hide()
            hide_background_layer()
            return

        target_size = self.background_label.size()
        if target_size.isEmpty():
            return
        cache_key = (target_size.width(), target_size.height(), self.background_fit_mode, self.background_media_path)
        if self.background_render_cache_key == cache_key and self.background_render_cache:
            pixmap = self.background_render_cache
        else:
            if self.background_fit_mode == "stretch":
                pixmap = self.background_pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            elif self.background_fit_mode == "tile":
                pixmap = self._build_tiled_background(target_size)
            else:
                pixmap = self._build_cover_background(target_size)
            self.background_render_cache_key = cache_key
            self.background_render_cache = pixmap
        self.background_label.setPixmap(pixmap)
        self.background_label.show()
        self.background_label.lower()
        if self.background_video_view:
            self.background_video_view.hide()
        show_background_layer()

    def _build_cover_background(self, target_size: QSize) -> QPixmap:
        if not self.background_pixmap or self.background_pixmap.isNull():
            return QPixmap()
        scaled = self.background_pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        crop_x = max(0, (scaled.width() - target_size.width()) // 2)
        crop_y = max(0, (scaled.height() - target_size.height()) // 2)
        return scaled.copy(crop_x, crop_y, target_size.width(), target_size.height())

    def _build_tiled_background(self, target_size: QSize) -> QPixmap:
        if not self.background_pixmap or self.background_pixmap.isNull():
            return QPixmap()
        tile_width = max(1, self.background_pixmap.width())
        tile_height = max(1, self.background_pixmap.height())
        canvas = QPixmap(target_size)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        y = 0
        while y < target_size.height():
            x = 0
            while x < target_size.width():
                painter.drawPixmap(x, y, self.background_pixmap)
                x += tile_width
            y += tile_height
        painter.end()
        return canvas

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_background_layer()
        if self.task_completion_toast:
            self.task_completion_toast.reposition()
        if self.window_menu_bar:
            self.window_menu_bar.sync_window_state()

    def nativeEvent(self, event_type: bytes | str, message: int) -> tuple[bool, int]:  # noqa: N802
        if event_type not in (b"windows_generic_MSG", "windows_generic_MSG"):
            return super().nativeEvent(event_type, message)
        try:
            msg = WindowsMessage.from_address(int(message))
        except (TypeError, ValueError):
            return super().nativeEvent(event_type, message)
        if msg.message != WM_NCHITTEST or self.isMaximized() or self.isFullScreen():
            return super().nativeEvent(event_type, message)

        x = msg.lParam & 0xFFFF
        y = (msg.lParam >> 16) & 0xFFFF
        if x >= 0x8000:
            x -= 0x10000
        if y >= 0x8000:
            y -= 0x10000
        pos = self.mapFromGlobal(QPoint(x, y))
        left = pos.x() < RESIZE_BORDER_WIDTH
        right = pos.x() >= self.width() - RESIZE_BORDER_WIDTH
        top = pos.y() < RESIZE_BORDER_WIDTH
        bottom = pos.y() >= self.height() - RESIZE_BORDER_WIDTH

        if top and left:
            return True, HTTOPLEFT
        if top and right:
            return True, HTTOPRIGHT
        if bottom and left:
            return True, HTBOTTOMLEFT
        if bottom and right:
            return True, HTBOTTOMRIGHT
        if left:
            return True, HTLEFT
        if right:
            return True, HTRIGHT
        if top:
            return True, HTTOP
        if bottom:
            return True, HTBOTTOM
        return super().nativeEvent(event_type, message)

    def _set_toolbar_compact(self, compact: bool) -> None:
        toolbar_layout = self.shell.toolbar.layout()
        if compact:
            self.shell.toolbar.setFixedHeight(36)
            if toolbar_layout:
                toolbar_layout.setContentsMargins(12, 3, 12, 3)
                toolbar_layout.setSpacing(10)
            if self.toolbar_title:
                self.toolbar_title.hide()
            if self.toolbar_subtitle:
                self.toolbar_subtitle.hide()
            if self.toolbar_health:
                self.toolbar_health.hide()
            if self.toolbar_compact_status:
                self.toolbar_compact_status.show()
            return

        self.shell.toolbar.setFixedHeight(72)
        if toolbar_layout:
            toolbar_layout.setContentsMargins(24, 14, 24, 14)
            toolbar_layout.setSpacing(16)
        if self.toolbar_title:
            self.toolbar_title.show()
        if self.toolbar_subtitle:
            self.toolbar_subtitle.show()
        if self.toolbar_health:
            self.toolbar_health.show()
        if self.toolbar_compact_status:
            self.toolbar_compact_status.hide()

    def _set_current_progress(self, message: str) -> None:
        if self.current_progress_label:
            self.current_progress_label.setText(message)

    def _notify_file_context_changed(self) -> None:
        key = self.page_keys[self.stack.currentIndex()] if hasattr(self, "stack") and self.page_keys else ""
        if hasattr(self, "file_panel") and not self.file_panel.files and key in self.features and not self.is_running:
            self._reset_bottom_status()
        if key in self.features:
            if key == "super_resolution":
                selected_file = self.file_panel.selected_file() if hasattr(self, "file_panel") else None
                self.features[key].update_file_context(list(self.file_panel.files), selected_file, self._log)
                return
            if hasattr(self.features[key], "get_workbench_files"):
                self.features[key].update_file_context([], None, self._log)
                return
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

        if self.background_player:
            self.background_player.stop()
        event.accept()
