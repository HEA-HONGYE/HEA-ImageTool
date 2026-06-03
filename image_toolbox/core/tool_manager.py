from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from image_toolbox.core.config import AppConfig
from image_toolbox.core.paths import get_project_root, looks_like_external_asset_path


class ToolHealthStatus(str, Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    INVALID = "invalid"
    VERSION_UNKNOWN = "version_unknown"


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    display_name: str
    executable_names: tuple[str, ...]
    config_key: str
    project_subdir: str
    allow_path_lookup: bool = False
    version_args: tuple[str, ...] = ("-version",)


@dataclass
class ToolHealth:
    tool_id: str
    display_name: str
    status: ToolHealthStatus
    path: Path | None = None
    version: str = ""
    reason: str = ""

    @property
    def available(self) -> bool:
        return self.status in {ToolHealthStatus.AVAILABLE, ToolHealthStatus.VERSION_UNKNOWN}


TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    "ffmpeg": ToolDefinition("ffmpeg", "FFmpeg", ("ffmpeg.exe", "ffmpeg"), "ffmpeg_path", "ffmpeg", True),
    "ffprobe": ToolDefinition("ffprobe", "FFprobe", ("ffprobe.exe", "ffprobe"), "ffprobe_path", "ffmpeg", True),
    "rife": ToolDefinition(
        "rife",
        "RIFE",
        ("rife-ncnn-vulkan.exe", "rife-ncnn-vulkan_waifu2xEX.exe", "rife-ncnn-vulkan"),
        "rife_path",
        "rife",
        False,
        ("-h",),
    ),
    "dain": ToolDefinition("dain", "DAIN", ("dain-ncnn-vulkan.exe",), "dain_path", "dain", False, ("-h",)),
    "cain": ToolDefinition("cain", "CAIN", ("cain-ncnn-vulkan.exe",), "cain_path", "cain", False, ("-h",)),
    "ifrnet": ToolDefinition("ifrnet", "IFRNet", ("ifrnet-ncnn-vulkan.exe",), "ifrnet_path", "ifrnet", False, ("-h",)),
}


class ToolManager:
    def __init__(self) -> None:
        self.config = AppConfig("media_tools")
        self.health: dict[str, ToolHealth] = {}
        self.ensure_tool_dirs()
        self.refresh()

    @property
    def tools_root(self) -> Path:
        return get_project_root() / "tools"

    def ensure_tool_dirs(self) -> None:
        self.tools_root.mkdir(parents=True, exist_ok=True)
        for definition in TOOL_DEFINITIONS.values():
            (self.tools_root / definition.project_subdir).mkdir(parents=True, exist_ok=True)

    def set_configured_path(self, tool_id: str, path: Path) -> None:
        definition = TOOL_DEFINITIONS[tool_id]
        self.config.set(definition.config_key, str(path))
        self.refresh_tool(tool_id)

    def configured_path(self, tool_id: str) -> Path | None:
        definition = TOOL_DEFINITIONS[tool_id]
        configured = self.config.get(definition.config_key, "", str)
        if not configured:
            return None
        path = Path(configured)
        return path if path.exists() else None

    def project_tool_dir(self, tool_id: str) -> Path:
        return self.tools_root / TOOL_DEFINITIONS[tool_id].project_subdir

    def resolve_tool_path(self, tool_id: str) -> Path | None:
        definition = TOOL_DEFINITIONS[tool_id]
        configured = self.configured_path(tool_id)
        if configured:
            if looks_like_external_asset_path(configured):
                return None
            return configured
        project_dir = self.project_tool_dir(tool_id)
        for executable_name in definition.executable_names:
            candidate = project_dir / executable_name
            if candidate.exists():
                return candidate
        if definition.allow_path_lookup:
            for executable_name in definition.executable_names:
                found = shutil.which(executable_name)
                if found:
                    return Path(found)
        return None

    def refresh(self) -> dict[str, ToolHealth]:
        self.health = {tool_id: self.check_tool(tool_id) for tool_id in TOOL_DEFINITIONS}
        return self.health

    def refresh_tool(self, tool_id: str) -> ToolHealth:
        self.health[tool_id] = self.check_tool(tool_id)
        return self.health[tool_id]

    def check_tool(self, tool_id: str) -> ToolHealth:
        definition = TOOL_DEFINITIONS[tool_id]
        path = self.resolve_tool_path(tool_id)
        if path is None:
            return ToolHealth(tool_id, definition.display_name, ToolHealthStatus.MISSING, reason="未检测到工具")
        if looks_like_external_asset_path(path):
            return ToolHealth(tool_id, definition.display_name, ToolHealthStatus.INVALID, path=path, reason="工具路径指向素材库，不能作为运行路径")
        if not path.exists():
            return ToolHealth(tool_id, definition.display_name, ToolHealthStatus.MISSING, path=path, reason="文件不存在")
        version = self._read_version(path, definition.version_args)
        if not version:
            return ToolHealth(tool_id, definition.display_name, ToolHealthStatus.VERSION_UNKNOWN, path=path, reason="无法读取版本信息")
        return ToolHealth(tool_id, definition.display_name, ToolHealthStatus.AVAILABLE, path=path, version=version)

    def _read_version(self, path: Path, args: tuple[str, ...]) -> str:
        try:
            completed = subprocess.run(
                [str(path), *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except Exception:
            return ""
        first_line = next((line.strip() for line in completed.stdout.splitlines() if line.strip()), "")
        return first_line[:240]

    def require_tool(self, tool_id: str) -> Path:
        health = self.refresh_tool(tool_id)
        if not health.available or health.path is None:
            raise FileNotFoundError(f"未检测到 {health.display_name}，请到工具管理中配置或导入。{health.reason}")
        return health.path

    def require_ffmpeg_pair(self) -> tuple[Path, Path]:
        ffmpeg = self.require_tool("ffmpeg")
        ffprobe = self.require_tool("ffprobe")
        return ffmpeg, ffprobe


_TOOL_MANAGER: ToolManager | None = None


def get_tool_manager() -> ToolManager:
    global _TOOL_MANAGER
    if _TOOL_MANAGER is None:
        _TOOL_MANAGER = ToolManager()
    return _TOOL_MANAGER


def reload_tool_manager() -> ToolManager:
    global _TOOL_MANAGER
    _TOOL_MANAGER = ToolManager()
    return _TOOL_MANAGER


def find_tools_in_source(source_root: Path) -> dict[str, list[Path]]:
    results: dict[str, list[Path]] = {tool_id: [] for tool_id in ["ffmpeg", "ffprobe", "rife"]}
    if not source_root.exists():
        return results
    for file_path in source_root.rglob("*.exe"):
        lower_name = file_path.name.lower()
        if lower_name in {"ffmpeg.exe", "ffmpeg_waifu2xex.exe", "ffmpeg_legacyw2xex.exe"}:
            results["ffmpeg"].append(file_path)
        elif lower_name in {"ffprobe.exe", "ffprobe_waifu2xex.exe"}:
            results["ffprobe"].append(file_path)
        elif lower_name in {"rife-ncnn-vulkan.exe", "rife-ncnn-vulkan_waifu2xex.exe"}:
            results["rife"].append(file_path)
    return {tool_id: sorted(paths) for tool_id, paths in results.items()}


def import_tools_from_source(source_root: Path, strategy: str = "skip") -> list[str]:
    manager = get_tool_manager()
    discovered = find_tools_in_source(source_root)
    logs: list[str] = []
    for tool_id, paths in discovered.items():
        if not paths:
            logs.append(f"未发现 {TOOL_DEFINITIONS[tool_id].display_name}")
            continue
        source = paths[0]
        target_dir = manager.project_tool_dir(tool_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / TOOL_DEFINITIONS[tool_id].executable_names[0]
        if target.exists() and strategy == "skip":
            logs.append(f"跳过已存在：{target}")
        else:
            shutil.copy2(source, target)
            logs.append(f"复制：{source} -> {target}")
            if tool_id == "rife":
                for dll_path in sorted(source.parent.glob("*.dll")):
                    dll_target = target_dir / dll_path.name
                    if dll_target.exists() and strategy == "skip":
                        logs.append(f"跳过已存在：{dll_target}")
                        continue
                    shutil.copy2(dll_path, dll_target)
                    logs.append(f"复制依赖：{dll_path} -> {dll_target}")
        manager.set_configured_path(tool_id, target)
    manager.refresh()
    return logs
