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
from image_toolbox.core.model_library import build_cain_command, build_dain_command, build_ifrnet_command, build_rife_command, list_interpolation_models
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


def list_ifrnet_models() -> list[str]:
    return list_interpolation_models("ifrnet")


def list_interpolation_engine_models(engine_id: str) -> list[str]:
    return list_interpolation_models(engine_id)


def resolve_rife_executable() -> Path:
    return get_tool_manager().require_tool("rife")


def resolve_ifrnet_executable() -> Path:
    return get_tool_manager().require_tool("ifrnet")


def resolve_cain_executable() -> Path:
    return get_tool_manager().require_tool("cain")


def resolve_dain_executable() -> Path:
    return get_tool_manager().require_tool("dain")


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
        self._active_record: MediaTaskRecord | None = None
        self._active_task_dir: Path | None = None
        self._log_writer: TaskLogWriter | None = None

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
        if self._active_record:
            self._active_record.commands.append(command)
            if self._active_task_dir:
                write_task_record(self._active_task_dir, self._active_record)

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
        self._set_state("extracting", "extracting")
        started = time.monotonic()
        frame_dir.mkdir(parents=True, exist_ok=True)
        command = [str(ffmpeg), "-y", "-i", str(source), "-vsync", "0", str(frame_dir / FRAME_PATTERN)]
        self._log(f"拆帧：{source.name}")
        self._run_command(command, "拆帧", file_index, total_files, 10, 20, total_frames)
        frames = _frame_files(frame_dir)
        if not frames:
            raise RuntimeError("拆帧失败：没有生成帧图片")
        self._log(f"拆帧完成：{len(frames)} 帧，耗时 {_format_duration(time.monotonic() - started)}")

    def _extract_audio(self, ffmpeg: Path, source: Path, audio_dir: Path, file_index: int, total_files: int, source_has_audio: bool) -> Path | None:
        if not self.settings.keep_audio or not source_has_audio:
            self._log("音频：输入视频没有音频或未启用保留音频，跳过。")
            return None
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = audio_dir / "audio.m4a"
        command = [str(ffmpeg), "-y", "-i", str(source), "-vn", "-acodec", "copy", str(audio_path)]
        try:
            self._log("提取音频：保留原音频")
            self._run_command(command, "提取音频", file_index, total_files, 28, 2)
            return audio_path if audio_path.exists() else None
        except RuntimeError as exc:
            if "用户取消" in str(exc):
                raise
            self._log(f"音频提取失败，将继续输出无音频视频：{exc}")
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
        self._set_state("processing", "processing")
        self._log(f"超分帧处理：{len(frames)} 帧，模型：{frame_settings.model_name}，倍率：{frame_settings.scale}x")
        for index, frame in enumerate(frames, start=1):
            if self._cancel_event.is_set():
                raise RuntimeError("用户取消")
            output_path = frames_out / frame.name
            self._upscale_runner = UpscaleProcessRunner()
            if self._active_record:
                self._active_record.extra["current_frame"] = index
                self._active_record.extra["current_frame_path"] = str(frame)
                if self._active_task_dir:
                    write_task_record(self._active_task_dir, self._active_record)

            def on_frame_progress(percent: int, frame_index: int = index) -> None:
                done = ((frame_index - 1) + percent / 100) / len(frames)
                self._emit_stage("超分帧处理", file_index, total_files, 30 + int(done * 30), f"已处理帧数：{frame_index} / {len(frames)}")

            try:
                self._upscale_runner.run(frame, output_path, frame_settings, self._cancel_event, self._log, self._debug, on_frame_progress)
            finally:
                self._upscale_runner = None
        return frames_out

    def _interpolate_frames(self, frames_in: Path, frames_out: Path, file_index: int, total_files: int) -> Path:
        input_frames = _frame_files(frames_in)
        if len(input_frames) < 2:
            raise RuntimeError("插帧失败：至少需要 2 帧")
        if self.settings.interpolation_engine == "cain":
            return self._interpolate_frames_with_cain(input_frames, frames_in, frames_out, file_index, total_files)
        if self.settings.interpolation_engine == "rife":
            executable = resolve_rife_executable()
            command = build_rife_command(
                executable,
                frames_in,
                frames_out,
                self.settings.interpolation_scale,
                self.settings.interpolation_model,
                self.settings.interpolation_gpu_id,
                self.settings.interpolation_tta,
                len(input_frames) * self.settings.interpolation_scale,
                FRAME_PATTERN,
            )
            display_name = "RIFE"
        elif self.settings.interpolation_engine == "ifrnet":
            executable = resolve_ifrnet_executable()
            command = build_ifrnet_command(
                executable,
                frames_in,
                frames_out,
                self.settings.interpolation_scale,
                self.settings.interpolation_model,
                self.settings.interpolation_gpu_id,
                self.settings.interpolation_tta,
                len(input_frames) * self.settings.interpolation_scale,
                FRAME_PATTERN,
            )
            display_name = "IFRNet"
        elif self.settings.interpolation_engine == "dain":
            executable = resolve_dain_executable()
            command = build_dain_command(
                executable,
                frames_in,
                frames_out,
                self.settings.interpolation_scale,
                self.settings.interpolation_model or "best",
                self.settings.interpolation_gpu_id,
                len(input_frames) * self.settings.interpolation_scale,
                FRAME_PATTERN,
            )
            if self.settings.interpolation_tta:
                self._log("DAIN 当前命令行不支持 TTA 参数，已忽略 TTA。")
            display_name = "DAIN"
        else:
            raise RuntimeError(f"当前版本不支持插帧引擎：{self.settings.interpolation_engine}")
        self._set_state("interpolating", "interpolating")
        self._log(f"使用 {display_name}：{executable}")
        frames_out.mkdir(parents=True, exist_ok=True)
        if any("ai超分参考文件" in part or "waifu2x-extension-gui" in part for part in command):
            raise RuntimeError(f"{display_name} 命令包含素材库路径，已阻止启动")
        self._log(f"{display_name} 插帧：{self.settings.interpolation_scale}x，模型：{self.settings.interpolation_model or '默认'}")
        self._run_command(command, "插帧处理", file_index, total_files, 60, 20, len(input_frames) * self.settings.interpolation_scale)
        if not _frame_files(frames_out):
            raise RuntimeError("插帧失败：没有生成插帧结果")
        return frames_out

    def _interpolate_frames_with_cain(
        self,
        input_frames: list[Path],
        frames_in: Path,
        frames_out: Path,
        file_index: int,
        total_files: int,
    ) -> Path:
        if self.settings.interpolation_scale not in {2, 4}:
            raise RuntimeError(f"CAIN 仅支持 2x / 4x，当前：{self.settings.interpolation_scale}x")
        executable = resolve_cain_executable()
        self._set_state("interpolating", "interpolating")
        self._log(f"使用 CAIN：{executable}")
        frames_out.mkdir(parents=True, exist_ok=True)
        passes = 1 if self.settings.interpolation_scale == 2 else 2
        current_input = frames_in
        for pass_index in range(1, passes + 1):
            current_output = frames_out if pass_index == passes else frames_out.parent / "frames_cain_pass1"
            current_output.mkdir(parents=True, exist_ok=True)
            command = build_cain_command(
                executable,
                current_input,
                current_output,
                self.settings.interpolation_model or "cain",
                self.settings.interpolation_gpu_id,
                FRAME_PATTERN,
            )
            if self.settings.interpolation_tta:
                self._log("CAIN 当前命令行不支持 TTA 参数，已忽略 TTA。")
            if any("ai超分参考文件" in part or "waifu2x-extension-gui" in part for part in command):
                raise RuntimeError("CAIN 命令包含素材库路径，已阻止启动")
            target_frames = len(_frame_files(current_input)) * 2
            self._log(
                f"CAIN 插帧：第 {pass_index} / {passes} 轮，模型：{self.settings.interpolation_model or 'cain'}，预计输出 {target_frames} 帧"
            )
            base_percent = 60 + int((pass_index - 1) * 20 / passes)
            span = max(1, int(20 / passes))
            self._run_command(command, "插帧处理", file_index, total_files, base_percent, span, target_frames)
            if not _frame_files(current_output):
                raise RuntimeError(f"CAIN 插帧失败：第 {pass_index} 轮没有生成结果")
            current_input = current_output
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
                self._set_state("encoding", "encoding")
                self._log("合成视频：保留音频")
                self._run_command(command, "合成视频", file_index, total_files, 80, 18, total_frames)
                return
            except RuntimeError as exc:
                if "用户取消" in str(exc):
                    raise
                self._log(f"音频合并失败，改为无音频输出：{exc}")
        command = base_command + video_args + [str(output_path)]
        self._set_state("encoding", "encoding")
        self._log("合成视频：无音频")
        self._run_command(command, "合成视频", file_index, total_files, 80, 18, total_frames)

    def _process_video(self, source: Path, output_path: Path, task_dir: Path, file_index: int, total_files: int) -> None:
        tools = require_ffmpeg_tools()
        if self._active_record:
            self._active_record.output_path = str(output_path)
            self._active_record.tool_paths.update({"ffmpeg": str(tools.ffmpeg), "ffprobe": str(tools.ffprobe)})
            if self.settings.upscale_settings:
                self._active_record.extra["upscale_engine"] = self.settings.upscale_settings.engine_id
                self._active_record.extra["upscale_model"] = self.settings.upscale_settings.model_name
            if self.settings.interpolation_enabled:
                self._active_record.tool_paths[self.settings.interpolation_engine] = str(get_tool_manager().require_tool(self.settings.interpolation_engine))
                self._active_record.extra["interpolation_engine"] = self.settings.interpolation_engine
                self._active_record.extra["interpolation_model"] = self.settings.interpolation_model
            write_task_record(task_dir, self._active_record)
        self._log(f"使用 FFmpeg：{tools.ffmpeg}")
        self._log(f"使用 FFprobe：{tools.ffprobe}")
        self._log(f"输出目录：{self.settings.output_dir}")
        self._debug(f"临时目录：{task_dir}")
        self._set_state("probing", "probing")
        self._emit_stage("读取视频", file_index, total_files, 5)
        probe_data = probe_media(source, tools.ffprobe)
        input_fps = media_fps(probe_data) or 30.0
        total_frames = _probe_frame_count(probe_data)
        output_fps = self.settings.output_fps or input_fps * (self.settings.interpolation_scale if self.settings.interpolation_enabled else 1)
        source_has_audio = has_audio_stream(probe_data)
        duration = float(probe_data.get("format", {}).get("duration") or 0)
        width = 0
        height = 0
        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == "video":
                width = int(stream.get("width") or 0)
                height = int(stream.get("height") or 0)
                break
        scale = self.settings.upscale_settings.scale if self.settings.upscale_enabled and self.settings.upscale_settings else 1
        output_frames = max(1, total_frames or int(duration * input_fps) or 1) * (self.settings.interpolation_scale if self.settings.interpolation_enabled else 1)
        estimated_temp = estimate_frame_bytes(width, height, max(1, total_frames or output_frames), 1, 1.5)
        if self.settings.upscale_enabled:
            estimated_temp += estimate_frame_bytes(width, height, max(1, total_frames or output_frames), scale, 1.4)
        if self.settings.interpolation_enabled:
            estimated_temp += estimate_frame_bytes(width, height, output_frames, scale, 1.3)
        if self._active_record:
            self._active_record.frame_count = total_frames
            self._active_record.estimated_output_frames = output_frames
            self._active_record.estimated_temp_bytes = estimated_temp
            write_task_record(task_dir, self._active_record)
        ensure_space(task_dir, estimated_temp)
        self._log(f"视频信息：FPS {input_fps:.3f}，预估帧数 {total_frames or '未知'}，输出 FPS {output_fps:.3f}")
        self._log(f"预计临时空间：{format_bytes(estimated_temp)}，仅供参考")
        if duration > 60 or total_frames > 3000 or output_frames > 6000 or estimated_temp > 10 * 1024**3:
            self._log("长任务警告：该任务可能耗时较长并占用大量磁盘空间，建议先使用短片测试。")

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
                self._active_task_dir = task_dir
                self._log_writer = TaskLogWriter(task_dir)
                self._active_record = MediaTaskRecord(
                    task_id=task_dir.name,
                    media_type="video",
                    input_path=str(source),
                    output_path=str(output_path),
                    output_format=self.settings.output_format,
                    status="waiting",
                    stage="waiting",
                    extra={
                        "upscale_enabled": self.settings.upscale_enabled,
                        "interpolation_enabled": self.settings.interpolation_enabled,
                        "keep_audio": self.settings.keep_audio,
                    },
                )
                write_task_record(task_dir, self._active_record)
                self._process_video(source, output_path, task_dir, index, total)
                result.output = output_path
                result.status = "success"
                success_count += 1
                self._set_state("completed", "completed")
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
                self._log(f"处理失败：{source.name}，原因：{exc}")
                failed_items.append(result)
            finally:
                self._active_record = None
                self._active_task_dir = None
                self._log_writer = None

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
