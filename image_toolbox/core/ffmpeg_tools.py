from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from image_toolbox.core.tool_manager import get_tool_manager


@dataclass(frozen=True)
class FFmpegPaths:
    ffmpeg: Path
    ffprobe: Path


def _configured_tool(name: str) -> Path | None:
    return get_tool_manager().configured_path(name)


def _project_tool(name: str) -> Path | None:
    path = get_tool_manager().resolve_tool_path(name)
    return path if path and get_tool_manager().project_tool_dir(name) in path.parents else None


def find_tool(name: str) -> Path | None:
    return get_tool_manager().resolve_tool_path(name)


def require_ffmpeg_tools() -> FFmpegPaths:
    ffmpeg, ffprobe = get_tool_manager().require_ffmpeg_pair()
    return FFmpegPaths(ffmpeg=ffmpeg, ffprobe=ffprobe)


def probe_media(source: Path, ffprobe: Path | None = None) -> dict:
    ffprobe_path = ffprobe or find_tool("ffprobe")
    if ffprobe_path is None:
        raise FileNotFoundError("Missing media tool: ffprobe")
    command = [
        str(ffprobe_path),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(source),
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffprobe failed")
    return json.loads(completed.stdout or "{}")


def media_fps(probe_data: dict) -> float:
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") != "video":
            continue
        rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/1"
        if "/" in rate:
            numerator, denominator = rate.split("/", 1)
            try:
                denominator_value = float(denominator)
                if denominator_value:
                    return float(numerator) / denominator_value
            except ValueError:
                return 0.0
        try:
            return float(rate)
        except ValueError:
            return 0.0
    return 0.0


def has_audio_stream(probe_data: dict) -> bool:
    return any(stream.get("codec_type") == "audio" for stream in probe_data.get("streams", []))
