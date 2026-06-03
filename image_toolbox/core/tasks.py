from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class TaskSignals(QObject):
    log = Signal(str)
    progress = Signal(int)
    file_status = Signal(int, str)
    finished = Signal(int, int)
    failed = Signal(str)


class ImageBatchTask(QRunnable):
    def __init__(self, files: list[Path], processor: Callable[[Path, Callable[[str], None]], Path]):
        super().__init__()
        self.files = files
        self.processor = processor
        self.signals = TaskSignals()
        self._cancelled = False
        self._pause_event = Event()
        self._pause_event.set()

    def cancel(self) -> None:
        self._cancelled = True
        self._pause_event.set()

    def pause(self) -> None:
        self._pause_event.clear()

    def resume(self) -> None:
        self._pause_event.set()

    @Slot()
    def run(self) -> None:
        if not self.files:
            self.signals.failed.emit("请先添加图片文件。")
            return

        total = len(self.files)
        success_count = 0
        failed_count = 0

        for index, file_path in enumerate(self.files, start=1):
            zero_index = index - 1
            if self._cancelled:
                self.signals.file_status.emit(zero_index, "已取消")
                self.signals.log.emit("任务已取消，剩余文件未处理。")
                break

            self.signals.file_status.emit(zero_index, "等待")
            self._pause_event.wait()
            if self._cancelled:
                self.signals.file_status.emit(zero_index, "已取消")
                self.signals.log.emit("任务已取消，剩余文件未处理。")
                break

            try:
                self.signals.file_status.emit(zero_index, "处理中")
                result = self.processor(file_path, self.signals.log.emit)
                self.signals.log.emit(f"完成：{result}")
                self.signals.file_status.emit(zero_index, "成功")
                success_count += 1
            except Exception as exc:
                failed_count += 1
                self.signals.log.emit(f"跳过：{file_path.name}，原因：{exc}")
                self.signals.file_status.emit(zero_index, f"失败：{exc}")
            finally:
                self.signals.progress.emit(int(index / total * 100))

        self.signals.finished.emit(success_count, failed_count)
