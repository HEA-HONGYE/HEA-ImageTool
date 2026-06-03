from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from image_toolbox.core.config import AppConfig
from image_toolbox.core.paths import get_project_root


@dataclass(frozen=True)
class FFmpegPaths:
    ffmpeg: Path
    ffprobe: Path


def _configured_tool(name: str) -> Path | None:
    configured = AppConfig("media_tools").get(f"{name}_path", "", str)
    if configured:
        path = Path(configured)
        if path.exists():
            return path
    return None


def _project_tool(name: str) -> Path | None:
    executable = f"{name}.exe" if not name.lower().endswith(".exe") else name
    path = get_project_root() / "tools" / "ffmpeg" / executable
    return path if path.exists() else None


def find_tool(name: str) -> Path | None:
    configured = _configured_tool(name)
    if configured:
        return configured
    project_tool = _project_tool(name)
    if project_tool:
        return project_tool
    found = shutil.which(name)
    return Path(found) if found else None


def require_ffmpeg_tools() -> FFmpegPaths:
    ffmpeg = find_tool("ffmpeg")
    ffprobe = find_tool("ffprobe")
    missing: list[str] = []
    if ffmpeg is None:
        missing.append("ffmpeg")
    if ffprobe is None:
        missing.append("ffprobe")
    if missing:
        raise FileNotFoundError("Missing media tool: " + ", ".join(missing))
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
