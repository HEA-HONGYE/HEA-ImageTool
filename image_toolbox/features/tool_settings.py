from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from image_toolbox.core.tool_manager import (
    TOOL_DEFINITIONS,
    ToolHealthStatus,
    get_tool_manager,
    import_tools_from_source,
)
from image_toolbox.ui.widgets import NoWheelComboBox as QComboBox


class ToolSettingsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.manager = get_tool_manager()
        self.table: QTableWidget | None = None
        self.path_edits: dict[str, QLineEdit] = {}
        self.import_strategy_combo: QComboBox | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("工具管理")
        title.setObjectName("PanelTitle")
        hint = QLabel("管理视频处理运行依赖：FFmpeg、FFprobe、RIFE、IFRNet、CAIN、DAIN。模型仍在项目模型库中管理，工具目录只放可执行程序和 DLL。")
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)

        layout.addWidget(self._build_table_group())
        layout.addWidget(self._build_path_group())
        layout.addWidget(self._build_import_group())
        layout.addStretch()

    def _build_table_group(self) -> QWidget:
        group = QGroupBox("运行环境检测")
        box = QVBoxLayout(group)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["工具", "状态", "路径", "版本", "原因"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(150)
        box.addWidget(self.table)
        row = QHBoxLayout()
        refresh_button = QPushButton("重新检查")
        refresh_button.clicked.connect(self.refresh)
        open_tools_button = QPushButton("打开 tools 目录")
        open_tools_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.manager.tools_root.resolve()))))
        row.addStretch()
        row.addWidget(refresh_button)
        row.addWidget(open_tools_button)
        box.addLayout(row)
        return group

    def _build_path_group(self) -> QWidget:
        group = QGroupBox("手动配置路径")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)
        layout.setColumnStretch(1, 1)
        for row_index, tool_id in enumerate(["ffmpeg", "ffprobe", "rife", "ifrnet", "cain", "dain"]):
            definition = TOOL_DEFINITIONS[tool_id]
            label = QLabel(definition.display_name)
            label.setMinimumWidth(72)
            label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            edit = QLineEdit()
            edit.setMinimumWidth(120)
            edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.path_edits[tool_id] = edit
            browse_button = QPushButton("浏览")
            browse_button.setFixedWidth(72)
            browse_button.clicked.connect(lambda _checked=False, item=tool_id: self._browse_tool(item))
            save_button = QPushButton("保存并检测")
            save_button.setFixedWidth(104)
            save_button.clicked.connect(lambda _checked=False, item=tool_id: self._save_tool_path(item))
            open_button = QPushButton("打开目录")
            open_button.setFixedWidth(88)
            open_button.clicked.connect(lambda _checked=False, item=tool_id: self._open_tool_dir(item))
            layout.addWidget(label, row_index, 0)
            layout.addWidget(edit, row_index, 1)
            layout.addWidget(browse_button, row_index, 2)
            layout.addWidget(save_button, row_index, 3)
            layout.addWidget(open_button, row_index, 4)
        return group

    def _build_import_group(self) -> QWidget:
        group = QGroupBox("从素材库导入工具")
        row = QHBoxLayout(group)
        self.import_strategy_combo = QComboBox()
        self.import_strategy_combo.addItem("跳过已存在", "skip")
        self.import_strategy_combo.addItem("覆盖", "overwrite")
        import_button = QPushButton("选择素材库并导入")
        import_button.clicked.connect(self._import_from_source)
        row.addWidget(QLabel("已存在文件"))
        row.addWidget(self.import_strategy_combo)
        row.addStretch()
        row.addWidget(import_button)
        return group

    def refresh(self) -> None:
        health_map = self.manager.refresh()
        if self.table:
            self.table.setRowCount(0)
            for row, tool_id in enumerate(["ffmpeg", "ffprobe", "rife", "ifrnet", "cain", "dain"]):
                health = health_map[tool_id]
                self.table.insertRow(row)
                values = [
                    health.display_name,
                    self._status_text(health.status),
                    str(health.path or ""),
                    health.version,
                    health.reason,
                ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        for tool_id, edit in self.path_edits.items():
            configured = self.manager.configured_path(tool_id)
            health = health_map.get(tool_id)
            edit.setText(str(configured or (health.path if health and health.path else "")))

    def _status_text(self, status: ToolHealthStatus) -> str:
        return {
            ToolHealthStatus.AVAILABLE: "可用",
            ToolHealthStatus.MISSING: "缺失",
            ToolHealthStatus.INVALID: "无效",
            ToolHealthStatus.VERSION_UNKNOWN: "可用，版本未知",
        }.get(status, str(status))

    def _browse_tool(self, tool_id: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择工具可执行文件", str(Path.cwd()), "Executable (*.exe);;All Files (*)")
        if path:
            self.path_edits[tool_id].setText(path)

    def _save_tool_path(self, tool_id: str) -> None:
        text = self.path_edits[tool_id].text().strip()
        if not text:
            return
        self.manager.set_configured_path(tool_id, Path(text))
        self.refresh()

    def _open_tool_dir(self, tool_id: str) -> None:
        directory = self.manager.project_tool_dir(tool_id)
        directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory.resolve())))

    def _import_from_source(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择素材库根目录", str(Path.cwd()))
        if not directory:
            return
        strategy = self.import_strategy_combo.currentData() if self.import_strategy_combo else "skip"
        logs = import_tools_from_source(Path(directory), strategy)
        self.refresh()
        QMessageBox.information(self, "导入工具完成", "\n".join(logs) or "没有发现可导入工具")
