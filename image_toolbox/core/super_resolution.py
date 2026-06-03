from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Callable, Literal

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from image_toolbox.core.upscale_engines import DEFAULT_ENGINE_MANAGER
from image_toolbox.core.upscale_engines.types import (
    CANCELLED,
    ENGINE_NOT_FOUND,
    GPU_MEMORY_ERROR,
    INPUT_NOT_FOUND,
    INVALID_CONFIG,
    MODEL_NOT_FOUND,
    OUTPUT_ERROR,
    PROCESS_FAILED,
    UNKNOWN_ERROR,
    UpscaleConfig,
)


FailureReason = Literal[
    "输入文件不存在",
    "图片读取失败",
    "输出目录无权限",
    "引擎执行失败",
    "显存不足或疑似显存不足",
    "用户取消",
    "未知错误",
]


class SuperResolutionError(RuntimeError):
    def __init__(self, reason: FailureReason, detail: str, error_type: str = UNKNOWN_ERROR):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail
        self.error_type = error_type


@dataclass(frozen=True)
class SuperResolutionSettings:
    engine_id: str
    output_dir: Path
    model_name: str
    scale: int
    output_format: str
    keep_original_format: bool
    quality: int
    tile_mode: str
    tile_size: int
    gpu_id: str
    threads: str
    use_tta: bool
    low_memory_mode: bool
    conflict_strategy: str

    @property
    def effective_tile_size(self) -> int:
        engine = DEFAULT_ENGINE_MANAGER.get_engine(self.engine_id)
        if self.tile_mode == "manual":
            return min(self.tile_size, engine.get_default_tile(True)) if self.low_memory_mode else self.tile_size
        return engine.get_default_tile(self.low_memory_mode)

    def to_upscale_config(self) -> UpscaleConfig:
        return UpscaleConfig(
            engine_id=self.engine_id,
            model_name=self.model_name,
            scale=self.scale,
            output_format=self.output_format,
            keep_original_format=self.keep_original_format,
            quality=self.quality,
            tile_mode=self.tile_mode,
            tile_size=self.effective_tile_size if self.tile_mode == "manual" else 0,
            low_memory_mode=self.low_memory_mode,
            conflict_strategy=self.conflict_strategy,
            output_dir=self.output_dir,
            gpu_id=self.gpu_id,
            threads=self.threads,
            use_tta=self.use_tta,
        )


@dataclass
class SuperResolutionResult:
    source: Path
    output: Path | None = None
    status: str = "failed"
    reason: str = ""
    attempts: int = 1
    skipped: bool = False


@dataclass
class SuperResolutionSummary:
    total: int
    success_count: int
    failed_count: int
    skipped_count: int
    elapsed_seconds: float
    output_dir: Path
    failed_items: list[SuperResolutionResult] = field(default_factory=list)


class SuperResolutionSignals(QObject):
    log = Signal(str)
    debug = Signal(str)
    progress = Signal(int)
    current_progress = Signal(str)
    file_status = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)


def _windows_creation_flags() -> int:
    flags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags |= subprocess.CREATE_NO_WINDOW
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP
    return flags


def read_image_info(source: Path) -> tuple[int, int, str]:
    with Image.open(source) as image:
        return image.width, image.height, (image.format or source.suffix.lstrip(".") or "PNG").upper()


def normalize_output_format(source: Path, selected_format: str, engine_id: str = "realesrgan") -> str:
    normalized = selected_format.lower()
    if normalized == "original":
        suffix = source.suffix.lower().lstrip(".")
        if suffix == "jpeg":
            suffix = "jpg"
        engine = DEFAULT_ENGINE_MANAGER.get_engine(engine_id)
        return suffix if suffix in engine.supported_formats else "png"
    if normalized == "jpeg":
        return "jpg"
    return normalized


def resolve_output_path(source: Path, output_dir: Path, scale: int, output_format: str, conflict_strategy: str) -> Path | None:
    output_path = output_dir / f"{source.stem}_ai{scale}x.{output_format}"
    if conflict_strategy == "overwrite" or not output_path.exists():
        return output_path
    if conflict_strategy == "skip":
        return None

    index = 1
    while True:
        candidate = output_dir / f"{source.stem}_ai{scale}x_{index}.{output_format}"
        if not candidate.exists():
            return candidate
        index += 1


def parse_progress_percent(message: str, engine_id: str = "realesrgan") -> int | None:
    return DEFAULT_ENGINE_MANAGER.get_engine(engine_id).parse_progress(message)


def _map_error_type(error_type: str) -> FailureReason:
    if error_type in {ENGINE_NOT_FOUND, MODEL_NOT_FOUND, INPUT_NOT_FOUND}:
        return "输入文件不存在" if error_type == INPUT_NOT_FOUND else "引擎执行失败"
    if error_type == OUTPUT_ERROR:
        return "输出目录无权限"
    if error_type == GPU_MEMORY_ERROR:
        return "显存不足或疑似显存不足"
    if error_type == CANCELLED:
        return "用户取消"
    if error_type in {PROCESS_FAILED, INVALID_CONFIG}:
        return "引擎执行失败"
    return "未知错误"


def classify_failure(exc: Exception, output: str = "") -> FailureReason:
    text = f"{exc}\n{output}".lower()
    if isinstance(exc, FileNotFoundError):
        return "输入文件不存在"
    if isinstance(exc, PermissionError):
        return "输出目录无权限"
    if "cancel" in text or "取消" in text:
        return "用户取消"
    if "vk_error" in text or "out of memory" in text or "memory" in text or "显存" in text:
        return "显存不足或疑似显存不足"
    if "cannot identify image file" in text or "image" in text and "read" in text:
        return "图片读取失败"
    if "exit" in text or "返回码" in text or "退出码" in text:
        return "引擎执行失败"
    return "未知错误"


def validate_super_resolution_inputs(files: list[Path], settings: SuperResolutionSettings) -> None:
    if not files:
        raise ValueError("请先添加图片文件。")
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        test_file = settings.output_dir / ".hea_write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
    except OSError as exc:
        raise PermissionError(f"输出目录无权限：{settings.output_dir}") from exc

    engine = DEFAULT_ENGINE_MANAGER.get_engine(settings.engine_id)
    engine.validate_config(settings.to_upscale_config())
    if settings.output_format.lower() not in {"original", "png", "jpg", "webp"}:
        raise ValueError("输出格式只能选择保留原格式、PNG、JPG 或 WEBP。")
    if not 0 <= settings.tile_size <= 2048:
        raise ValueError("Tile 参数必须在 0 到 2048 之间。")
    if settings.tile_mode not in {"auto", "manual"}:
        raise ValueError("Tile 模式无效。")
    if not 1 <= settings.quality <= 100:
        raise ValueError("JPG/WEBP 质量必须在 1 到 100 之间。")
    if settings.conflict_strategy not in {"rename", "skip", "overwrite"}:
        raise ValueError("输出文件冲突策略无效。")


def ensure_realesrgan_available(model_name: str | None = None) -> None:
    settings = SuperResolutionSettings(
        engine_id="realesrgan",
        output_dir=Path.cwd() / "output",
        model_name=model_name or "realesrgan-x4plus",
        scale=4,
        output_format="png",
        keep_original_format=False,
        quality=95,
        tile_mode="auto",
        tile_size=0,
        gpu_id="auto",
        threads="1:2:2",
        use_tta=False,
        low_memory_mode=False,
        conflict_strategy="rename",
    )
    DEFAULT_ENGINE_MANAGER.get_engine("realesrgan").validate_config(settings.to_upscale_config())


class UpscaleProcessRunner:
    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None

    def cancel(self) -> None:
        if self._process and self._process.poll() is None:
            pid = self._process.pid
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
            else:
                self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def run(
        self,
        source: Path,
        output_path: Path,
        settings: SuperResolutionSettings,
        cancel_event: Event,
        log: Callable[[str], None],
        debug: Callable[[str], None],
        progress: Callable[[int], None],
    ) -> Path:
        if cancel_event.is_set():
            raise SuperResolutionError("用户取消", "任务已取消", CANCELLED)
        if not source.exists():
            raise SuperResolutionError("输入文件不存在", f"输入文件不存在：{source}", INPUT_NOT_FOUND)

        try:
            read_image_info(source)
        except Exception as exc:
            raise SuperResolutionError("图片读取失败", f"图片读取失败：{source.name}，{exc}", INPUT_NOT_FOUND) from exc

        engine = DEFAULT_ENGINE_MANAGER.get_engine(settings.engine_id)
        output_format = output_path.suffix.lower().lstrip(".")
        engine_output = output_path
        engine_format = output_format
        needs_quality_convert = output_format in {"jpg", "webp"}
        if needs_quality_convert:
            engine_output = output_path.with_name(f"{output_path.stem}__hea_tmp.png")
            engine_format = "png"
        engine_output_existed = engine_output.exists()

        command_info = engine.build_command(source, engine_output, settings.to_upscale_config(), engine_format)
        log(f"开始处理：{source.name}")
        log(f"使用引擎：{engine.display_name}")
        log(f"使用模型：{settings.model_name}")
        log(f"输出倍率：{settings.scale}x")
        log(f"输出格式：{output_format.upper()}，Tile：{settings.effective_tile_size}")
        debug(f"工作目录：{command_info.cwd}")
        debug(f"完整命令：{' '.join(command_info.command)}")

        output_lines: list[str] = []
        try:
            self._process = subprocess.Popen(
                command_info.command,
                cwd=command_info.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_windows_creation_flags(),
            )
            assert self._process.stdout is not None
            for line in self._process.stdout:
                if cancel_event.is_set():
                    self.cancel()
                    raise SuperResolutionError("用户取消", "任务已取消", CANCELLED)
                message = line.strip()
                if not message:
                    continue
                output_lines.append(message)
                percent = engine.parse_progress(message)
                if percent is not None:
                    progress(percent)
                    if percent % 10 == 0:
                        log(f"当前进度：{percent}%")
                    continue
                debug(message)

            return_code = self._process.wait()
            debug(f"返回码：{return_code}")
            if cancel_event.is_set():
                raise SuperResolutionError("用户取消", "任务已取消", CANCELLED)
            if return_code != 0:
                engine_error = engine.parse_error("\n".join(output_lines), return_code)
                raise SuperResolutionError(_map_error_type(engine_error.error_type), engine_error.user_message, engine_error.error_type)
        except SuperResolutionError:
            raise
        except Exception as exc:
            reason = classify_failure(exc, "\n".join(output_lines))
            raise SuperResolutionError(reason, str(exc), UNKNOWN_ERROR) from exc
        finally:
            if cancel_event.is_set() and (needs_quality_convert or not engine_output_existed):
                engine_output.unlink(missing_ok=True)
            self._process = None

        if not engine_output.exists():
            raise SuperResolutionError("引擎执行失败", "引擎已结束，但没有生成输出文件。", PROCESS_FAILED)

        if needs_quality_convert:
            try:
                with Image.open(engine_output) as image:
                    save_image = image.convert("RGB") if output_format == "jpg" else image
                    save_kwargs: dict[str, object] = {"quality": settings.quality}
                    if output_format == "webp":
                        save_kwargs["method"] = 6
                    save_image.save(output_path, **save_kwargs)
                engine_output.unlink(missing_ok=True)
            except Exception as exc:
                raise SuperResolutionError("输出目录无权限", f"保存 {output_format.upper()} 输出失败：{exc}", OUTPUT_ERROR) from exc

        progress(100)
        log(f"处理成功：{output_path.name}")
        return output_path


class SuperResolutionBatchTask(QRunnable):
    def __init__(self, files: list[Path], settings: SuperResolutionSettings):
        super().__init__()
        self.files = files
        self.settings = settings
        self.signals = SuperResolutionSignals()
        self._cancel_event = Event()
        self._runner: UpscaleProcessRunner | None = None

    def cancel(self) -> None:
        self._cancel_event.set()
        if self._runner:
            self._runner.cancel()

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass

    @Slot()
    def run(self) -> None:
        started_at = time.monotonic()
        total = len(self.files)
        success_count = 0
        skipped_count = 0
        cancelled = False
        failed_items: list[SuperResolutionResult] = []

        if not self.files:
            self.signals.failed.emit("请先添加图片文件。")
            return

        index = 0
        for index, source in enumerate(self.files, start=1):
            zero_index = index - 1
            if self._cancel_event.is_set():
                self.signals.file_status.emit(zero_index, "已取消")
                self.signals.log.emit("任务已取消")
                cancelled = True
                break

            self.signals.file_status.emit(zero_index, "处理中")
            self.signals.current_progress.emit(f"当前：第 {index} / {total} 张\n当前文件进度：0%\n总进度：{int((index - 1) / total * 100)}%")
            output_format = normalize_output_format(source, self.settings.output_format, self.settings.engine_id)
            output_path = resolve_output_path(source, self.settings.output_dir, self.settings.scale, output_format, self.settings.conflict_strategy)
            if output_path is None:
                skipped_count += 1
                self.signals.file_status.emit(zero_index, "已跳过")
                self.signals.log.emit(f"跳过：{source.name}，原因：输出文件已存在")
                self.signals.progress.emit(int(index / total * 100))
                continue

            result = SuperResolutionResult(source=source, output=output_path)
            max_attempts = 2
            for attempt in range(1, max_attempts + 1):
                result.attempts = attempt
                self._runner = UpscaleProcessRunner()

                def current_file_progress(percent: int, file_index: int = index) -> None:
                    total_progress = int(((file_index - 1) + percent / 100) / total * 100)
                    self.signals.current_progress.emit(
                        f"当前：第 {file_index} / {total} 张\n当前文件进度：{percent}%\n总进度：{total_progress}%"
                    )
                    self.signals.progress.emit(total_progress)

                try:
                    if attempt > 1:
                        self.signals.log.emit(f"自动重试：{source.name}（第 {attempt} 次）")
                    self._runner.run(
                        source,
                        output_path,
                        self.settings,
                        self._cancel_event,
                        self.signals.log.emit,
                        lambda message: self.signals.debug.emit(f"[调试] {message}"),
                        current_file_progress,
                    )
                    result.status = "success"
                    success_count += 1
                    self.signals.file_status.emit(zero_index, "成功")
                    break
                except SuperResolutionError as exc:
                    result.reason = f"{exc.reason}：{exc.detail}"
                    if exc.reason == "用户取消" or self._cancel_event.is_set():
                        result.reason = "用户取消：任务已取消"
                        self.signals.file_status.emit(zero_index, "已取消")
                        self.signals.log.emit("任务已取消")
                        cancelled = True
                        break
                    if attempt >= max_attempts:
                        self.signals.file_status.emit(zero_index, f"失败：{exc.reason}")
                        self.signals.log.emit(f"处理失败：{source.name}，原因：{exc.reason}")
                        failed_items.append(result)
                    else:
                        self.signals.log.emit(f"处理失败：{source.name}，原因：{exc.reason}，准备自动重试")
                finally:
                    self._runner = None

            self.signals.progress.emit(int(index / total * 100))
            if self._cancel_event.is_set():
                cancelled = True
                break

        elapsed = time.monotonic() - started_at
        if cancelled:
            for remaining_index in range(index, total):
                self.signals.file_status.emit(remaining_index, "已取消")
            self.signals.current_progress.emit("当前：任务已取消")
        summary = SuperResolutionSummary(
            total=total,
            success_count=success_count,
            failed_count=len(failed_items),
            skipped_count=skipped_count,
            elapsed_seconds=elapsed,
            output_dir=self.settings.output_dir,
            failed_items=failed_items,
        )
        self.signals.finished.emit(summary)
