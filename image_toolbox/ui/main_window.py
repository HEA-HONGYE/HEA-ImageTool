from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, QThreadPool, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QPainter, QPixmap, QResizeEvent
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QFormLayout, QGraphicsOpacityEffect, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSlider, QStackedWidget, QTextEdit, QVBoxLayout, QWidget

from image_toolbox import APP_NAME, APP_VERSION
from image_toolbox.core.config import AppConfig
from image_toolbox.core.super_resolution import SuperResolutionSummary
from image_toolbox.core.tasks import ImageBatchTask
from image_toolbox.core.tool_manager import get_tool_manager
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
        self.background_edit.editingFinished.connect(self._save_and_apply)
        browse_button = QPushButton("插入图片")
        browse_button.clicked.connect(self._choose_background)
        background_row = QHBoxLayout()
        background_row.addWidget(self.background_edit, 1)
        background_row.addWidget(browse_button)
        bg_form.addRow("背景图片", background_row)

        self.fit_combo = QComboBox()
        self.fit_combo.addItem("自动裁剪填充", "center")
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

        for widget in [self.opacity_slider, self.component_opacity_slider, self.motion_slider, self.bg_opacity_slider, self.blur_slider, self.fit_combo, self.overlay_checkbox, self.show_icon_checkbox]:
            if isinstance(widget, QSlider):
                widget.valueChanged.connect(lambda _value: self._save_and_apply())
            elif widget is not None:
                widget.currentIndexChanged.connect(lambda _index: self._save_and_apply()) if isinstance(widget, QComboBox) else widget.toggled.connect(lambda _checked: self._save_and_apply())

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

    def _choose_background(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "选择背景图片", str(self.backgrounds_dir), "Images (*.jpg *.jpeg *.png *.webp *.bmp)")
        if selected and self.background_edit:
            self.background_edit.setText(selected)
            self._save_and_apply()

    def _open_background_folder(self) -> None:
        self.backgrounds_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.backgrounds_dir.resolve())))

    def _refresh_background(self) -> None:
        if self.background_edit and not self.background_edit.text().strip():
            images = []
            if self.backgrounds_dir.exists():
                for pattern in ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp"]:
                    images.extend(self.backgrounds_dir.glob(pattern))
            if images:
                self.background_edit.setText(str(images[0]))
        self._save_and_apply()

    def _clear_background(self) -> None:
        if self.background_edit:
            self.background_edit.clear()
        self._save_and_apply()

    def _save_and_apply(self) -> None:
        self.config.set("window_opacity", self.opacity_slider.value() if self.opacity_slider else 100)
        self.config.set("component_opacity", self.component_opacity_slider.value() if self.component_opacity_slider else 100)
        self.config.set("motion_effects", self.motion_slider.value() if self.motion_slider else 0)
        self.config.set("background_path", self.background_edit.text().strip() if self.background_edit else "")
        self.config.set("background_fit", self.fit_combo.currentData() if self.fit_combo else "center")
        self.config.set("background_opacity", self.bg_opacity_slider.value() if self.bg_opacity_slider else 24)
        self.config.set("background_blur", self.blur_slider.value() if self.blur_slider else 0)
        self.config.set("overlay_enabled", self.overlay_checkbox.isChecked() if self.overlay_checkbox else True)
        self.config.set("show_launcher_icon", self.show_icon_checkbox.isChecked() if self.show_icon_checkbox else True)
        self.apply_callback()


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, personalization_callback=None) -> None:
        super().__init__(parent)
        self.personalization_callback = personalization_callback or (lambda: None)
        self.setObjectName("AppShell")
        self.setWindowTitle("设置")
        self.setWindowFlag(Qt.Window, True)
        self.setMinimumSize(920, 620)
        self.resize(1180, 760)
        self.nav_buttons: dict[str, QPushButton] = {}
        self.page_factories = {}
        self.page_widgets: dict[str, QWidget] = {}
        self._centered_once = False

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
        side_layout.addStretch()

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
            page = self.page_factories.pop(page_key)()
            self.page_widgets[page_key] = page
            self.stack.removeWidget(placeholder)
            placeholder.deleteLater()
            self.stack.insertWidget(index, page)
        self.stack.setCurrentIndex(index)
        for button_key, button in self.nav_buttons.items():
            button.setChecked(button_key == page_key)

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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
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
        self.bottom_panel: QWidget | None = None
        self.background_label: QLabel | None = None
        self.background_pixmap: QPixmap | None = None
        self.background_effect: QGraphicsOpacityEffect | None = None
        self.background_fit_mode = "center"
        self.current_task: ImageBatchTask | None = None
        self.last_failed_files: list[Path] = []
        self.last_failed_feature_key: str | None = None
        self.log_messages: list[str] = []

        self.shell = AppShell()
        self.setCentralWidget(self.shell)
        self.background_label = QLabel(self.shell)
        self.background_label.setObjectName("PersonalizationBackground")
        self.background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.background_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.background_effect = QGraphicsOpacityEffect(self.background_label)
        self.background_label.setGraphicsEffect(self.background_effect)
        self.background_label.hide()
        self.background_label.lower()
        self._build_toolbar(self.shell.toolbar)
        self.shell.toolbar.hide()

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(16)
        self.shell.workspace_layout.addLayout(content, 1)

        content.addWidget(self._build_sidebar())

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
        self.switch_page("home")
        self._set_running(False)
        self._log_tool_health()
        self._apply_personalization()

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
        health_map = get_tool_manager().refresh()
        for tool_id in ["ffmpeg", "ffprobe", "rife"]:
            health = health_map[tool_id]
            if health.available and health.path:
                self._log(f"检测到 {health.display_name}：{health.path}")
            else:
                self._log(f"未检测到 {health.display_name}：请到工具管理中配置或导入。")

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
        dialog = SettingsDialog(self, self._apply_personalization)
        self.settings_dialog = dialog

        def reset_settings_dialog(_result: int) -> None:
            self.settings_dialog = None
            feature = self.features.get("super_resolution")
            if hasattr(feature, "refresh_from_engine_settings"):
                feature.refresh_from_engine_settings()

        dialog.finished.connect(reset_settings_dialog)
        dialog.show()

    def _apply_personalization(self) -> None:
        config = AppConfig("personalization")
        opacity = config.get("window_opacity", 100, int)
        self.setWindowOpacity(max(70, min(100, opacity)) / 100)

        background_path = config.get("background_path", "")
        fit_mode = config.get("background_fit", "center")
        background_opacity = max(0, min(100, config.get("background_opacity", 24, int)))
        component_opacity = max(35, min(100, config.get("component_opacity", 100, int)))
        component_alpha = int(255 * component_opacity / 100)
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

        if background_path and Path(background_path).exists():
            pixmap = QPixmap(str(Path(background_path)))
            self.background_pixmap = pixmap if not pixmap.isNull() else None
        else:
            self.background_pixmap = None
        self.background_fit_mode = fit_mode
        if self.background_effect:
            self.background_effect.setOpacity(background_opacity / 100)
        self._update_background_layer()

        self.shell.setStyleSheet(component_style if component_opacity < 100 else "")

    def _update_background_layer(self) -> None:
        if not self.background_label:
            return
        self.background_label.setGeometry(self.shell.rect())
        self.background_label.lower()
        if not self.background_pixmap or self.background_pixmap.isNull():
            self.background_label.clear()
            self.background_label.hide()
            return

        target_size = self.background_label.size()
        if target_size.isEmpty():
            return
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
        self.background_label.setPixmap(pixmap)
        self.background_label.show()
        self.background_label.lower()

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

        event.accept()
