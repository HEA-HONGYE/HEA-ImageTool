from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from PIL import Image, ImageSequence, UnidentifiedImageError
from PySide6.QtCore import QRunnable, Slot

from image_toolbox.core.paths import get_project_root
from image_toolbox.core.media_task_utils import (
    MediaTaskRecord,
    TaskLogWriter,
    ensure_space,
    estimate_frame_bytes,
    format_bytes,
    update_task_state,
    write_report,
    write_task_record,
)
from image_toolbox.core.super_resolution import (
    SuperResolutionResult,
    SuperResolutionSettings,
    SuperResolutionSignals,
    SuperResolutionSummary,
    UpscaleProcessRunner,
    validate_super_resolution_inputs,
)


ANIMATED_EXTENSIONS = {".gif", ".webp", ".png", ".apng"}
FRAME_PATTERN = "%06d.png"


@dataclass(frozen=True)
class AnimatedMediaInfo:
    input_path: Path
    input_format: str
    width: int
    height: int
    frame_count: int
    durations: list[int]
    loop_count: int
    has_alpha: bool
    file_size: int

    @property
    def duration_ms(self) -> int:
        return sum(self.durations)

    @property
    def fps(self) -> float:
        if not self.durations:
            return 0.0
        average = sum(self.durations) / len(self.durations)
        return 1000 / average if average else 0.0


@dataclass(frozen=True)
class AnimatedProcessSettings:
    output_dir: Path
    output_format: str = "gif"
    keep_temp: bool = False
    enable_upscale: bool = False
    output_fps: float = 0.0
    preserve_loop: bool = True
    conflict_strategy: str = "rename"
    upscale_settings: SuperResolutionSettings | None = None


def read_animated_info(source: Path) -> AnimatedMediaInfo:
    if not source.exists():
        raise FileNotFoundError(f"输入文件不存在：{source}")
    if source.suffix.lower() not in ANIMATED_EXTENSIONS:
        raise ValueError(f"格式不支持：{source.suffix}")
    try:
        with Image.open(source) as image:
            frame_count = getattr(image, "n_frames", 1)
            is_animated = bool(getattr(image, "is_animated", False)) and frame_count > 1
            if not is_animated:
                raise ValueError("不是动态图片")
            durations: list[int] = []
            has_alpha = False
            for frame in ImageSequence.Iterator(image):
                durations.append(max(1, int(frame.info.get("duration", image.info.get("duration", 100)) or 100)))
                has_alpha = has_alpha or _frame_has_alpha(frame)
            return AnimatedMediaInfo(
                input_path=source,
                input_format=(image.format or source.suffix.lstrip(".")).upper(),
                width=image.width,
                height=image.height,
                frame_count=frame_count,
                durations=durations,
                loop_count=int(image.info.get("loop", 0) or 0),
                has_alpha=has_alpha,
                file_size=source.stat().st_size,
            )
    except UnidentifiedImageError as exc:
        raise ValueError(f"动态图片读取失败：{source}") from exc


def is_animated_image(source: Path) -> bool:
    try:
        read_animated_info(source)
        return True
    except Exception:
        return False


def _frame_has_alpha(frame: Image.Image) -> bool:
    if frame.mode in {"RGBA", "LA"}:
        alpha = frame.getchannel("A")
        return alpha.getextrema()[0] < 255
    return "transparency" in frame.info


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    return f"{minutes}:{sec:02d}"


def _resolve_output_path(source: Path, settings: AnimatedProcessSettings) -> Path | None:
    suffix = settings.output_format.lower().lstrip(".")
    output_path = settings.output_dir / f"{source.stem}_animated_ai.{suffix}"
    if settings.conflict_strategy == "overwrite" or not output_path.exists():
        return output_path
    if settings.conflict_strategy == "skip":
        return None
    index = 1
    while True:
        candidate = settings.output_dir / f"{source.stem}_animated_ai_{index}.{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _frame_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.png"))


class AnimatedMediaTask(QRunnable):
    def __init__(self, files: list[Path], settings: AnimatedProcessSettings):
        super().__init__()
        self.files = files
        self.settings = settings
        self.signals = SuperResolutionSignals()
        self._cancel_event = Event()
        self._upscale_runner: UpscaleProcessRunner | None = None
        self._started_at = time.monotonic()
        self._active_record: MediaTaskRecord | None = None
        self._active_task_dir: Path | None = None
        self._log_writer: TaskLogWriter | None = None

    def cancel(self) -> None:
        self._cancel_event.set()
        if self._upscale_runner:
            self._upscale_runner.cancel()

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass

    def _debug(self, message: str) -> None:
        if self._log_writer:
            self._log_writer.debug(message)
        self.signals.debug.emit(f"[调试] {message}")

    def _log(self, message: str) -> None:
        if self._log_writer:
            self._log_writer.user(message)
        self.signals.log.emit(message)

    def _set_state(self, status: str, stage: str | None = None, failure_reason: str = "") -> None:
        if self._active_record and self._active_task_dir:
            update_task_state(self._active_task_dir, self._active_record, status, stage, failure_reason)
            if stage:
                self._log(f"任务阶段：{stage}")

    def _emit_stage(self, stage: str, file_index: int, total_files: int, percent: int, frame_text: str = "") -> None:
        percent = max(0, min(100, percent))
        elapsed = time.monotonic() - self._started_at
        remaining = elapsed * (100 - percent) / percent if percent > 0 else 0
        detail = f"当前阶段：{stage}"
        if frame_text:
            detail += f"\n{frame_text}"
        detail += (
            f"\n当前：第 {file_index} / {total_files} 个文件"
            f"\n总进度：{percent}%"
            f"\n当前耗时：{_format_duration(elapsed)}"
            f"\n预计剩余：{_format_duration(remaining) if remaining else '估算中'}"
        )
        self.signals.current_progress.emit(detail)
        self.signals.progress.emit(percent)

    def _extract_frames(self, source: Path, frame_dir: Path, info: AnimatedMediaInfo, file_index: int, total_files: int) -> None:
        self._set_state("extracting", "extracting")
        frame_dir.mkdir(parents=True, exist_ok=True)
        self._log(f"拆帧：{source.name}，共 {info.frame_count} 帧")
        with Image.open(source) as image:
            for index, frame in enumerate(ImageSequence.Iterator(image), start=1):
                if self._cancel_event.is_set():
                    raise RuntimeError("用户取消")
                frame_rgba = frame.convert("RGBA")
                frame_rgba.save(frame_dir / (FRAME_PATTERN % index))
                progress = 10 + int(index / info.frame_count * 20)
                self._emit_stage("拆帧", file_index, total_files, progress, f"已处理帧数：{index} / {info.frame_count}")
        if len(_frame_files(frame_dir)) != info.frame_count:
            raise RuntimeError("拆帧失败：帧数量不一致")

    def _process_frames(self, frames_in: Path, frames_out: Path, file_index: int, total_files: int) -> Path:
        if not self.settings.enable_upscale:
            return frames_in
        self._set_state("processing", "processing")
        if not self.settings.upscale_settings:
            raise RuntimeError("逐帧处理失败：缺少 AI 超分参数")
        frames = _frame_files(frames_in)
        if not frames:
            raise RuntimeError("逐帧处理失败：输入帧为空")
        frames_out.mkdir(parents=True, exist_ok=True)
        validate_super_resolution_inputs(frames[:1], self.settings.upscale_settings)
        self._log(
            f"逐帧 AI 超分：{len(frames)} 帧，模型：{self.settings.upscale_settings.model_name}，倍率：{self.settings.upscale_settings.scale}x"
        )
        for index, frame_path in enumerate(frames, start=1):
            if self._cancel_event.is_set():
                raise RuntimeError("用户取消")
            output_path = frames_out / frame_path.name
            self._upscale_runner = UpscaleProcessRunner()
            if self._active_record:
                self._active_record.extra["current_frame"] = index
                self._active_record.extra["current_frame_path"] = str(frame_path)
                if self._active_task_dir:
                    write_task_record(self._active_task_dir, self._active_record)

            def on_progress(percent: int, frame_index: int = index) -> None:
                done = ((frame_index - 1) + percent / 100) / len(frames)
                self._emit_stage("逐帧处理", file_index, total_files, 30 + int(done * 45), f"已处理帧数：{frame_index} / {len(frames)}")

            try:
                self._upscale_runner.run(frame_path, output_path, self.settings.upscale_settings, self._cancel_event, self._log, self._debug, on_progress)
            finally:
                self._upscale_runner = None
        return frames_out

    def _compose(self, frames_dir: Path, output_path: Path, info: AnimatedMediaInfo, file_index: int, total_files: int) -> None:
        self._set_state("encoding", "encoding")
        frames = [Image.open(path).convert("RGBA") for path in _frame_files(frames_dir)]
        if not frames:
            raise RuntimeError("合成失败：没有可用帧")
        durations = [max(1, int(1000 / self.settings.output_fps))] * len(frames) if self.settings.output_fps > 0 else info.durations
        if len(durations) != len(frames):
            durations = (durations + [durations[-1] if durations else 100] * len(frames))[: len(frames)]
        loop = info.loop_count if self.settings.preserve_loop else 0
        fmt = self.settings.output_format.lower()
        self._log(f"合成动态图片：{output_path.name}，格式：{fmt.upper()}，帧数：{len(frames)}")
        try:
            if fmt == "gif":
                paletted = [frame.convert("P", palette=Image.Palette.ADAPTIVE) for frame in frames]
                paletted[0].save(output_path, save_all=True, append_images=paletted[1:], duration=durations, loop=loop, optimize=False, disposal=2)
                if info.has_alpha:
                    self._log("透明通道警告：GIF 仅支持 1-bit 透明，可能有边缘损失。")
            elif fmt == "webp":
                frames[0].save(output_path, save_all=True, append_images=frames[1:], duration=durations, loop=loop, lossless=True, quality=95, method=6)
            elif fmt == "apng":
                frames[0].save(output_path, format="PNG", save_all=True, append_images=frames[1:], duration=durations, loop=loop, disposal=2)
            else:
                raise ValueError(f"输出格式不支持：{fmt}")
        finally:
            for frame in frames:
                frame.close()
        self._emit_stage("合成", file_index, total_files, 95, f"已处理帧数：{len(frames)} / {len(frames)}")

    def _process_one(self, source: Path, output_path: Path, task_dir: Path, file_index: int, total_files: int) -> None:
        self._emit_stage("读取动图信息", file_index, total_files, 5)
        self._set_state("probing", "probing")
        info = read_animated_info(source)
        scale = self.settings.upscale_settings.scale if self.settings.enable_upscale and self.settings.upscale_settings else 1
        estimated_temp = estimate_frame_bytes(info.width, info.height, info.frame_count, 1, 1.4)
        if self.settings.enable_upscale:
            estimated_temp += estimate_frame_bytes(info.width, info.height, info.frame_count, scale, 1.6)
        ensure_space(task_dir, estimated_temp)
        if self._active_record:
            self._active_record.frame_count = info.frame_count
            self._active_record.estimated_output_frames = info.frame_count
            self._active_record.estimated_temp_bytes = estimated_temp
            self._active_record.extra.update(
                {
                    "width": info.width,
                    "height": info.height,
                    "fps": info.fps,
                    "duration_ms": info.duration_ms,
                    "loop_count": info.loop_count,
                    "has_alpha": info.has_alpha,
                }
            )
            write_task_record(task_dir, self._active_record)
        self._log(
            f"动图信息：{info.input_format}，{info.width}x{info.height}，{info.frame_count} 帧，FPS {info.fps:.2f}，循环 {info.loop_count}，透明：{'是' if info.has_alpha else '否'}"
        )
        self._log(f"预计临时空间：{format_bytes(estimated_temp)}，仅供参考")
        if info.frame_count > 3000 or estimated_temp > 10 * 1024**3:
            self._log("长任务警告：该动图帧数较多或预计临时空间很大，建议先用短样本测试。")
        frames_raw = task_dir / "frames_raw"
        frames_processed = task_dir / "frames_processed"
        self._extract_frames(source, frames_raw, info, file_index, total_files)
        frames_for_output = self._process_frames(frames_raw, frames_processed, file_index, total_files)
        self._compose(frames_for_output, output_path, info, file_index, total_files)
        self._set_state("completed", "completed")
        self._emit_stage("完成", file_index, total_files, 100)

    @Slot()
    def run(self) -> None:
        self._started_at = time.monotonic()
        started_at = self._started_at
        total = len(self.files)
        success_count = 0
        skipped_count = 0
        failed_items: list[SuperResolutionResult] = []
        self.settings.output_dir.mkdir(parents=True, exist_ok=True)
        temp_root = get_project_root() / "temp" / "animated_tasks"
        temp_root.mkdir(parents=True, exist_ok=True)

        for index, source in enumerate(self.files, start=1):
            result = SuperResolutionResult(source=source)
            zero_index = index - 1
            task_dir = temp_root / f"{int(time.time())}_{index}_{source.stem}"
            try:
                if self._cancel_event.is_set():
                    raise RuntimeError("用户取消")
                output_path = _resolve_output_path(source, self.settings)
                if output_path is None:
                    skipped_count += 1
                    self.signals.file_status.emit(zero_index, "已跳过")
                    self.signals.log.emit(f"跳过：{source.name}，原因：输出文件已存在")
                    continue
                self.signals.file_status.emit(zero_index, "处理中")
                task_dir.mkdir(parents=True, exist_ok=True)
                (task_dir / "logs").mkdir(exist_ok=True)
                self._active_task_dir = task_dir
                self._log_writer = TaskLogWriter(task_dir)
                self._active_record = MediaTaskRecord(
                    task_id=task_dir.name,
                    media_type="animated",
                    input_path=str(source),
                    output_path=str(output_path),
                    output_format=self.settings.output_format,
                    status="waiting",
                    stage="waiting",
                    extra={
                        "enable_upscale": self.settings.enable_upscale,
                        "output_fps": self.settings.output_fps,
                        "preserve_loop": self.settings.preserve_loop,
                    },
                )
                if self.settings.upscale_settings:
                    self._active_record.extra["upscale_engine"] = self.settings.upscale_settings.engine_id
                    self._active_record.extra["upscale_model"] = self.settings.upscale_settings.model_name
                    self._active_record.extra["scale"] = self.settings.upscale_settings.scale
                write_task_record(task_dir, self._active_record)
                self._debug(f"临时目录：{task_dir}")
                self._process_one(source, output_path, task_dir, index, total)
                result.output = output_path
                result.status = "success"
                success_count += 1
                if self._active_record:
                    report_path = write_report(self._active_record, task_dir)
                    self._log(f"日志报告：{report_path}")
                self.signals.file_status.emit(zero_index, "成功")
                self._log(f"处理成功：{output_path.name}，耗时 {_format_duration(time.monotonic() - started_at)}")
                if not self.settings.keep_temp:
                    shutil.rmtree(task_dir, ignore_errors=True)
            except Exception as exc:
                if self._cancel_event.is_set() or "用户取消" in str(exc):
                    result.reason = "用户取消：任务已取消"
                    self._set_state("cancelled", self._active_record.stage if self._active_record else "cancelled", result.reason)
                    if self._active_record and self._active_task_dir:
                        report_path = write_report(self._active_record, self._active_task_dir)
                        self._log(f"日志报告：{report_path}")
                    self.signals.file_status.emit(zero_index, "已取消")
                    self._log("任务已取消，已生成文件和临时日志会保留。")
                    failed_items.append(result)
                    break
                result.reason = str(exc)
                if self._active_record:
                    current_frame = self._active_record.extra.get("current_frame")
                    if current_frame:
                        result.reason = f"第 {current_frame} 帧失败：{result.reason}"
                self._set_state("failed", self._active_record.stage if self._active_record else "failed", result.reason)
                if self._active_record and self._active_task_dir:
                    report_path = write_report(self._active_record, self._active_task_dir)
                    self._log(f"日志报告：{report_path}")
                self.signals.file_status.emit(zero_index, f"失败：{exc}")
                self._log(f"处理失败：{source.name}，原因：{result.reason}")
                failed_items.append(result)
            finally:
                self._active_record = None
                self._active_task_dir = None
                self._log_writer = None

        summary = SuperResolutionSummary(
            total=total,
            success_count=success_count,
            failed_count=len(failed_items),
            skipped_count=skipped_count,
            elapsed_seconds=time.monotonic() - started_at,
            output_dir=self.settings.output_dir,
            failed_items=failed_items,
        )
        self.signals.finished.emit(summary)
