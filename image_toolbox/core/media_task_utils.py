from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from image_toolbox.core.paths import get_project_root


MEDIA_TASK_STATES = {
    "waiting",
    "probing",
    "extracting",
    "processing",
    "interpolating",
    "encoding",
    "completed",
    "failed",
    "cancelled",
}


@dataclass
class MediaTaskRecord:
    task_id: str
    media_type: str
    input_path: str
    output_path: str = ""
    status: str = "waiting"
    stage: str = "waiting"
    failed_stage: str = ""
    failure_reason: str = ""
    output_format: str = ""
    frame_count: int = 0
    estimated_output_frames: int = 0
    estimated_temp_bytes: int = 0
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    commands: list[list[str]] = field(default_factory=list)
    tool_paths: dict[str, str] = field(default_factory=dict)
    model_paths: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


class TaskLogWriter:
    def __init__(self, task_dir: Path) -> None:
        self.task_dir = task_dir
        self.log_dir = task_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.user_log = self.log_dir / "user_log.txt"
        self.debug_log = self.log_dir / "debug_log.txt"

    def user(self, message: str) -> None:
        self._append(self.user_log, message)

    def debug(self, message: str) -> None:
        self._append(self.debug_log, message)

    def _append(self, path: Path, message: str) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")


def write_task_record(task_dir: Path, record: MediaTaskRecord) -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.json").write_text(json.dumps(asdict(record), ensure_ascii=False, indent=2), encoding="utf-8")


def update_task_state(task_dir: Path, record: MediaTaskRecord, status: str, stage: str | None = None, failure_reason: str = "") -> None:
    if status not in MEDIA_TASK_STATES:
        raise ValueError(f"未知媒体任务状态：{status}")
    record.status = status
    record.stage = stage or status
    if failure_reason:
        record.failed_stage = record.stage
        record.failure_reason = failure_reason
    if status in {"completed", "failed", "cancelled"}:
        record.completed_at = time.time()
    write_task_record(task_dir, record)


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return total


def format_bytes(size: int) -> str:
    value = float(max(0, size))
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


def free_space_for(path: Path) -> int:
    target = path if path.exists() else path.parent
    while not target.exists() and target.parent != target:
        target = target.parent
    usage = shutil.disk_usage(target)
    return int(usage.free)


def ensure_space(path: Path, required_bytes: int) -> None:
    free_bytes = free_space_for(path)
    if required_bytes > 0 and free_bytes < required_bytes:
        raise RuntimeError(f"磁盘空间不足：预计需要 {format_bytes(required_bytes)}，可用 {format_bytes(free_bytes)}")


def estimate_frame_bytes(width: int, height: int, frames: int, scale: int = 1, multiplier: float = 1.2) -> int:
    pixels = max(1, width) * max(1, height) * max(1, scale) * max(1, scale)
    return int(pixels * 4 * max(1, frames) * multiplier)


def media_cache_roots() -> list[Path]:
    root = get_project_root() / "temp"
    return [root / "video_tasks", root / "animated_tasks"]


def clear_media_task_cache() -> tuple[int, int]:
    total_size = 0
    removed = 0
    for root in media_cache_roots():
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)
            continue
        for task_dir in root.iterdir():
            if not task_dir.is_dir():
                continue
            total_size += directory_size(task_dir)
            shutil.rmtree(task_dir, ignore_errors=True)
            removed += 1
        root.mkdir(parents=True, exist_ok=True)
    return removed, total_size


def load_failed_media_task_records() -> list[MediaTaskRecord]:
    records: list[MediaTaskRecord] = []
    for root in media_cache_roots():
        if not root.exists():
            continue
        for task_json in root.glob("*/task.json"):
            try:
                data = json.loads(task_json.read_text(encoding="utf-8"))
                if data.get("status") not in {"failed", "cancelled"}:
                    continue
                records.append(MediaTaskRecord(**data))
            except Exception:
                continue
    return records


def write_report(record: MediaTaskRecord, task_dir: Path) -> Path:
    reports_dir = get_project_root() / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{record.task_id}_report.txt"
    elapsed = max(0.0, (record.completed_at or time.time()) - record.started_at)
    lines = [
        f"任务 ID: {record.task_id}",
        f"媒体类型: {record.media_type}",
        f"输入文件: {record.input_path}",
        f"输出文件: {record.output_path}",
        f"状态: {record.status}",
        f"阶段: {record.stage}",
        f"失败阶段: {record.failed_stage}",
        f"失败原因: {record.failure_reason}",
        f"输出格式: {record.output_format}",
        f"帧数: {record.frame_count}",
        f"预计输出帧数: {record.estimated_output_frames}",
        f"预计临时空间: {format_bytes(record.estimated_temp_bytes)}",
        f"耗时: {elapsed:.1f}s",
        f"临时目录: {task_dir}",
        "",
        "工具路径:",
        *[f"- {key}: {value}" for key, value in record.tool_paths.items()],
        "",
        "模型路径:",
        *[f"- {key}: {value}" for key, value in record.model_paths.items()],
        "",
        "命令列表:",
        *[" ".join(command) for command in record.commands],
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
