from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from PySide6.QtCore import QRunnable, Slot

from image_toolbox.core.ffmpeg_tools import has_audio_stream, media_fps, probe_media, require_ffmpeg_tools
from image_toolbox.core.model_library import build_rife_command, list_interpolation_models
from image_toolbox.core.paths import get_project_root
from image_toolbox.core.super_resolution import (
    SuperResolutionResult,
    SuperResolutionSettings,
    SuperResolutionSignals,
    SuperResolutionSummary,
    UpscaleProcessRunner,
    _windows_creation_flags,
    validate_super_resolution_inputs,
)
from image_toolbox.core.tool_manager import get_tool_manager


FRAME_PATTERN = "%06d.png"
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}
VIDEO_CODECS = {"libx264", "libx265"}


@dataclass(frozen=True)
class VideoProcessSettings:
    output_dir: Path
    output_format: str = "mp4"
    keep_audio: bool = True
    keep_temp: bool = False
    upscale_enabled: bool = True
    interpolation_enabled: bool = False
    interpolation_engine: str = "rife"
    interpolation_scale: int = 2
    interpolation_model: str = ""
    interpolation_gpu_id: str = "auto"
    interpolation_tta: bool = False
    output_fps: float = 0.0
    video_codec: str = "libx264"
    crf: int = 18
    bitrate: str = ""
    conflict_strategy: str = "rename"
    upscale_settings: SuperResolutionSettings | None = None


def list_rife_models() -> list[str]:
    return list_interpolation_models("rife")


def resolve_rife_executable() -> Path:
    return get_tool_manager().require_tool("rife")


def _resolve_video_output_path(source: Path, settings: VideoProcessSettings) -> Path | None:
    suffix = settings.output_format.lower().lstrip(".") or "mp4"
    output_path = settings.output_dir / f"{source.stem}_media_ai.{suffix}"
    if settings.conflict_strategy == "overwrite" or not output_path.exists():
        return output_path
    if settings.conflict_strategy == "skip":
        return None
    index = 1
    while True:
        candidate = settings.output_dir / f"{source.stem}_media_ai_{index}.{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _frame_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.png") if path.is_file())


def _parse_ffmpeg_frame(message: str) -> int | None:
    match = re.search(r"frame=\s*(\d+)", message)
    return int(match.group(1)) if match else None


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes}:{sec:02d}"


def _probe_frame_count(probe_data: dict) -> int:
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") != "video":
            continue
        for key in ("nb_frames", "nb_read_frames"):
            value = stream.get(key)
            if value and str(value).isdigit():
                return int(value)
    duration = float(probe_data.get("format", {}).get("duration") or 0)
    fps = media_fps(probe_data)
    return int(duration * fps) if duration and fps else 0


class MediaCommandRunner:
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

    def run(self, command: list[str], cancel_event: Event, debug_line, frame_progress=None) -> str:
        output_lines: list[str] = []
        debug_line("完整命令：" + " ".join(command))
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_windows_creation_flags(),
        )
        assert self._process.stdout is not None
        try:
            for line in self._process.stdout:
                if cancel_event.is_set():
                    self.cancel()
                    raise RuntimeError("用户取消")
                message = line.strip()
                if not message:
                    continue
                output_lines.append(message)
                parsed_frame = _parse_ffmpeg_frame(message)
                if parsed_frame is not None and frame_progress is not None:
                    frame_progress(parsed_frame)
                else:
                    debug_line(message)
            return_code = self._process.wait()
            debug_line(f"返回码：{return_code}")
            if cancel_event.is_set():
                raise RuntimeError("用户取消")
            if return_code != 0:
                raise RuntimeError("\n".join(output_lines[-20:]) or f"process exited with {return_code}")
            return "\n".join(output_lines)
        finally:
            self._process = None


class VideoMediaTask(QRunnable):
    def __init__(self, files: list[Path], settings: VideoProcessSettings):
        super().__init__()
        self.files = files
        self.settings = settings
        self.signals = SuperResolutionSignals()
        self._cancel_event = Event()
        self._command_runner: MediaCommandRunner | None = None
        self._upscale_runner: UpscaleProcessRunner | None = None
        self._started_at = time.monotonic()

    def cancel(self) -> None:
        self._cancel_event.set()
        if self._command_runner:
            self._command_runner.cancel()
        if self._upscale_runner:
            self._upscale_runner.cancel()

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass

    def _debug(self, message: str) -> None:
        self.signals.debug.emit(f"[调试] {message}")

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
            f"\n预计剩余：{_format_duration(remaining) if remaining else '未知'}"
        )
        self.signals.current_progress.emit(detail)
        self.signals.progress.emit(percent)

    def _run_command(
        self,
        command: list[str],
        stage: str,
        file_index: int,
        total_files: int,
        base_percent: int,
        span: int,
        total_frames: int = 0,
    ) -> str:
        self._command_runner = MediaCommandRunner()

        def on_frame(frame: int) -> None:
            if total_frames:
                stage_percent = min(100, int(frame / total_frames * 100))
                total_percent = base_percent + int(span * stage_percent / 100)
                self._emit_stage(stage, file_index, total_files, total_percent, f"已处理帧数：{min(frame, total_frames)} / {total_frames}")

        try:
            return self._command_runner.run(command, self._cancel_event, self._debug, on_frame)
        finally:
            self._command_runner = None

    def _extract_frames(self, ffmpeg: Path, source: Path, frame_dir: Path, file_index: int, total_files: int, total_frames: int) -> None:
        started = time.monotonic()
        frame_dir.mkdir(parents=True, exist_ok=True)
        command = [str(ffmpeg), "-y", "-i", str(source), "-vsync", "0", str(frame_dir / FRAME_PATTERN)]
        self.signals.log.emit(f"拆帧：{source.name}")
        self._run_command(command, "拆帧", file_index, total_files, 10, 20, total_frames)
        frames = _frame_files(frame_dir)
        if not frames:
            raise RuntimeError("拆帧失败：没有生成帧图片")
        self.signals.log.emit(f"拆帧完成：{len(frames)} 帧，耗时 {_format_duration(time.monotonic() - started)}")

    def _extract_audio(self, ffmpeg: Path, source: Path, audio_dir: Path, file_index: int, total_files: int, source_has_audio: bool) -> Path | None:
        if not self.settings.keep_audio or not source_has_audio:
            self.signals.log.emit("音频：输入视频没有音频或未启用保留音频，跳过。")
            return None
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = audio_dir / "audio.m4a"
        command = [str(ffmpeg), "-y", "-i", str(source), "-vn", "-acodec", "copy", str(audio_path)]
        try:
            self.signals.log.emit("提取音频：保留原音频")
            self._run_command(command, "提取音频", file_index, total_files, 28, 2)
            return audio_path if audio_path.exists() else None
        except RuntimeError as exc:
            if "用户取消" in str(exc):
                raise
            self.signals.log.emit(f"音频提取失败，将继续输出无音频视频：{exc}")
            return None

    def _upscale_frames(self, frames_in: Path, frames_out: Path, file_index: int, total_files: int) -> Path:
        if not self.settings.upscale_settings:
            raise RuntimeError("超分参数缺失")
        frames = _frame_files(frames_in)
        if not frames:
            raise RuntimeError("超分失败：输入帧为空")
        frames_out.mkdir(parents=True, exist_ok=True)
        frame_settings = self.settings.upscale_settings
        validate_super_resolution_inputs(frames[:1], frame_settings)
        self.signals.log.emit(f"超分帧处理：{len(frames)} 帧，模型：{frame_settings.model_name}，倍率：{frame_settings.scale}x")
        for index, frame in enumerate(frames, start=1):
            if self._cancel_event.is_set():
                raise RuntimeError("用户取消")
            output_path = frames_out / frame.name
            self._upscale_runner = UpscaleProcessRunner()

            def on_frame_progress(percent: int, frame_index: int = index) -> None:
                done = ((frame_index - 1) + percent / 100) / len(frames)
                self._emit_stage("超分帧处理", file_index, total_files, 30 + int(done * 30), f"已处理帧数：{frame_index} / {len(frames)}")

            try:
                self._upscale_runner.run(frame, output_path, frame_settings, self._cancel_event, self.signals.log.emit, self._debug, on_frame_progress)
            finally:
                self._upscale_runner = None
        return frames_out

    def _interpolate_frames(self, frames_in: Path, frames_out: Path, file_index: int, total_files: int) -> Path:
        if self.settings.interpolation_engine != "rife":
            raise RuntimeError("当前版本只支持 RIFE 插帧执行")
        input_frames = _frame_files(frames_in)
        if len(input_frames) < 2:
            raise RuntimeError("插帧失败：至少需要 2 帧")
        rife_exe = resolve_rife_executable()
        self.signals.log.emit(f"使用 RIFE：{rife_exe}")
        frames_out.mkdir(parents=True, exist_ok=True)
        command = build_rife_command(
            rife_exe,
            frames_in,
            frames_out,
            self.settings.interpolation_scale,
            self.settings.interpolation_model,
            self.settings.interpolation_gpu_id,
            self.settings.interpolation_tta,
            len(input_frames) * self.settings.interpolation_scale,
            FRAME_PATTERN,
        )
        if any("ai超分参考文件" in part or "waifu2x-extension-gui" in part for part in command):
            raise RuntimeError("RIFE 命令包含素材库路径，已阻止启动")
        self.signals.log.emit(f"RIFE 插帧：{self.settings.interpolation_scale}x，模型：{self.settings.interpolation_model or '默认'}")
        self._run_command(command, "插帧处理", file_index, total_files, 60, 20, len(input_frames) * self.settings.interpolation_scale)
        if not _frame_files(frames_out):
            raise RuntimeError("插帧失败：没有生成插帧结果")
        return frames_out

    def _encode_video(
        self,
        ffmpeg: Path,
        frames_dir: Path,
        output_path: Path,
        fps: float,
        audio_path: Path | None,
        file_index: int,
        total_files: int,
        total_frames: int,
    ) -> None:
        if self.settings.video_codec not in VIDEO_CODECS:
            raise ValueError(f"不支持的视频编码器：{self.settings.video_codec}")
        fps_text = f"{fps:.6f}".rstrip("0").rstrip(".") if fps else "30"
        video_input = str(frames_dir / FRAME_PATTERN)
        quality_args = ["-b:v", self.settings.bitrate] if self.settings.bitrate.strip() else ["-crf", str(self.settings.crf)]
        base_command = [str(ffmpeg), "-y", "-framerate", fps_text, "-i", video_input]
        video_args = ["-map", "0:v:0", "-c:v", self.settings.video_codec, *quality_args, "-pix_fmt", "yuv420p"]
        if audio_path and audio_path.exists():
            command = base_command + ["-i", str(audio_path)] + video_args + ["-map", "1:a:0", "-c:a", "copy", str(output_path)]
            try:
                self.signals.log.emit("合成视频：保留音频")
                self._run_command(command, "合成视频", file_index, total_files, 80, 18, total_frames)
                return
            except RuntimeError as exc:
                if "用户取消" in str(exc):
                    raise
                self.signals.log.emit(f"音频合并失败，改为无音频输出：{exc}")
        command = base_command + video_args + [str(output_path)]
        self.signals.log.emit("合成视频：无音频")
        self._run_command(command, "合成视频", file_index, total_files, 80, 18, total_frames)

    def _process_video(self, source: Path, output_path: Path, task_dir: Path, file_index: int, total_files: int) -> None:
        tools = require_ffmpeg_tools()
        self.signals.log.emit(f"使用 FFmpeg：{tools.ffmpeg}")
        self.signals.log.emit(f"使用 FFprobe：{tools.ffprobe}")
        self.signals.log.emit(f"输出目录：{self.settings.output_dir}")
        self.signals.debug.emit(f"[调试] 临时目录：{task_dir}")
        self._emit_stage("读取视频", file_index, total_files, 5)
        probe_data = probe_media(source, tools.ffprobe)
        input_fps = media_fps(probe_data) or 30.0
        total_frames = _probe_frame_count(probe_data)
        output_fps = self.settings.output_fps or input_fps * (self.settings.interpolation_scale if self.settings.interpolation_enabled else 1)
        source_has_audio = has_audio_stream(probe_data)
        self.signals.log.emit(f"视频信息：FPS {input_fps:.3f}，预估帧数 {total_frames or '未知'}，输出 FPS {output_fps:.3f}")

        frames_raw = task_dir / "frames_raw"
        frames_upscaled = task_dir / "frames_upscaled"
        frames_interpolated = task_dir / "frames_interpolated"
        audio_dir = task_dir / "audio"

        self._extract_frames(tools.ffmpeg, source, frames_raw, file_index, total_files, total_frames)
        actual_frame_count = len(_frame_files(frames_raw))
        audio_path = self._extract_audio(tools.ffmpeg, source, audio_dir, file_index, total_files, source_has_audio)

        frames_for_encode = frames_raw
        if self.settings.upscale_enabled:
            frames_for_encode = self._upscale_frames(frames_raw, frames_upscaled, file_index, total_files)
        if self.settings.interpolation_enabled:
            frames_for_encode = self._interpolate_frames(frames_for_encode, frames_interpolated, file_index, total_files)

        encode_frame_count = len(_frame_files(frames_for_encode)) or actual_frame_count
        self._encode_video(tools.ffmpeg, frames_for_encode, output_path, output_fps, audio_path, file_index, total_files, encode_frame_count)
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
        temp_root = get_project_root() / "temp" / "video_tasks"
        temp_root.mkdir(parents=True, exist_ok=True)

        for index, source in enumerate(self.files, start=1):
            result = SuperResolutionResult(source=source)
            zero_index = index - 1
            try:
                if self._cancel_event.is_set():
                    raise RuntimeError("用户取消")
                if not source.exists():
                    raise FileNotFoundError(f"输入文件不存在：{source}")
                if source.suffix.lower() not in VIDEO_EXTENSIONS:
                    raise ValueError(f"输入格式不支持：{source.suffix}")
                output_path = _resolve_video_output_path(source, self.settings)
                if output_path is None:
                    skipped_count += 1
                    self.signals.file_status.emit(zero_index, "已跳过")
                    self.signals.log.emit(f"跳过：{source.name}，原因：输出文件已存在")
                    continue
                self.signals.file_status.emit(zero_index, "处理中")
                task_dir = temp_root / f"{int(time.time())}_{index}_{source.stem}"
                task_dir.mkdir(parents=True, exist_ok=True)
                self._process_video(source, output_path, task_dir, index, total)
                result.output = output_path
                result.status = "success"
                success_count += 1
                self.signals.file_status.emit(zero_index, "成功")
                self.signals.log.emit(f"处理成功：{output_path.name}，耗时 {_format_duration(time.monotonic() - started_at)}")
                if not self.settings.keep_temp:
                    shutil.rmtree(task_dir, ignore_errors=True)
            except Exception as exc:
                if self._cancel_event.is_set() or "用户取消" in str(exc):
                    result.reason = "用户取消：任务已取消"
                    self.signals.file_status.emit(zero_index, "已取消")
                    self.signals.log.emit("任务已取消")
                    failed_items.append(result)
                    break
                result.reason = str(exc)
                self.signals.file_status.emit(zero_index, f"失败：{exc}")
                self.signals.log.emit(f"处理失败：{source.name}，原因：{exc}")
                failed_items.append(result)

        elapsed = time.monotonic() - started_at
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
