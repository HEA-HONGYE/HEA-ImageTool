from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from image_toolbox.core.paths import (
    ensure_project_model_dirs,
    get_engine_models_dir,
    get_models_root,
    get_video_interpolation_models_dir,
    is_project_model_path,
    looks_like_external_asset_path,
)


MODEL_FILE_SUFFIXES = {
    ".bin",
    ".param",
    ".onnx",
    ".pth",
    ".model",
    ".weights",
    ".json",
    ".txt",
    ".dat",
}

STRICT_MODEL_FILE_SUFFIXES = {
    ".bin",
    ".param",
    ".onnx",
    ".pth",
    ".model",
    ".weights",
}

KNOWN_MODEL_DIRS = {
    "realesrgan": ["realesrgan-x4plus", "realesrgan-x4plus-anime", "realesrnet-x4plus"],
    "waifu2x": ["cunet", "upconv_7", "anime_style_art_rgb", "models-cunet", "models-upconv_7", "models-upconv_7_anime_style_art_rgb"],
    "realcugan": ["models-se", "models-pro", "models-nose"],
    "realsr": ["models-DF2K", "models-DF2K_JPEG"],
    "srmd": ["srmd", "srmdnf", "models-srmd"],
    "anime4k": ["Anime4K", "anime4k"],
    "video_interpolation/rife": ["models", "models-v2", "models-v3", "models-v4", "models-v4.6", "models-rife"],
    "video_interpolation/dain": ["models", "model"],
    "video_interpolation/cain": ["models", "model"],
    "video_interpolation/ifrnet": ["models", "model"],
}

MODEL_DIR_ALIASES = {
    ("waifu2x", "models-cunet"): "cunet",
    ("waifu2x", "models-upconv_7"): "upconv_7",
    ("waifu2x", "models-upconv_7_anime_style_art_rgb"): "anime_style_art_rgb",
    ("srmd", "models-srmd"): "",
}

INTERPOLATION_ENGINE_DIRS = {
    "rife": "rife-ncnn-vulkan",
    "dain": "dain-ncnn-vulkan",
    "cain": "cain-ncnn-vulkan",
    "ifrnet": "ifrnet-ncnn-vulkan",
}


@dataclass
class CopyStats:
    copied: int = 0
    skipped: int = 0
    failed: int = 0
    logs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InterpolationModelInfo:
    name: str
    path: Path
    file_count: int
    size_bytes: int
    available: bool


def project_model_dir_for(engine_id: str, model_id: str = "") -> Path:
    if engine_id.startswith("video_interpolation/"):
        interpolation_id = engine_id.split("/", 1)[1]
        root = get_video_interpolation_models_dir(interpolation_id)
        return root / model_id if model_id else root
    root = get_engine_models_dir(engine_id)
    return root / model_id if model_id else root


def normalize_model_dir_name(engine_id: str, name: str) -> str:
    return MODEL_DIR_ALIASES.get((engine_id, name), name)


def _contains_model_files(path: Path) -> bool:
    if path.is_file():
        return path.suffix.lower() in MODEL_FILE_SUFFIXES
    if not path.is_dir():
        return False
    return any(child.is_file() and child.suffix.lower() in MODEL_FILE_SUFFIXES for child in path.rglob("*"))


def _contains_strict_model_files(path: Path) -> bool:
    if path.is_file():
        return path.suffix.lower() in STRICT_MODEL_FILE_SUFFIXES
    if not path.is_dir():
        return False
    return any(child.is_file() and child.suffix.lower() in STRICT_MODEL_FILE_SUFFIXES for child in path.rglob("*"))


def discover_model_sources(source_root: Path) -> list[tuple[str, str, Path]]:
    source_root = source_root.resolve()
    discovered: dict[tuple[str, str, Path], tuple[str, str, Path]] = {}
    if not source_root.exists():
        return []
    candidates = [source_root]
    candidates.extend(path for path in source_root.rglob("*") if path.is_dir())
    for path in candidates:
        name = path.name
        for interpolation_id, engine_dir in INTERPOLATION_ENGINE_DIRS.items():
            normalized_parts = {part.lower() for part in path.parts}
            if engine_dir not in normalized_parts:
                continue
            if path.name.lower() == engine_dir:
                continue
            if not _contains_strict_model_files(path):
                continue
            engine_id = f"video_interpolation/{interpolation_id}"
            discovered[(engine_id, path.name, path)] = (engine_id, path.name, path)

        for engine_id, known_names in KNOWN_MODEL_DIRS.items():
            if engine_id.startswith("video_interpolation/"):
                continue
            if name not in known_names:
                continue
            if not _contains_model_files(path):
                continue
            model_id = normalize_model_dir_name(engine_id, name)
            if engine_id == "anime4k":
                model_id = ""
            discovered[(engine_id, model_id, path)] = (engine_id, model_id, path)

        if "realesrgan" in path.as_posix().lower() and _contains_model_files(path):
            for model_id in KNOWN_MODEL_DIRS["realesrgan"]:
                if any(path.glob(f"{model_id}.*")):
                    discovered[("realesrgan", model_id, path)] = ("realesrgan", model_id, path)
    return sorted(discovered.values(), key=lambda item: (item[0], item[1], str(item[2])))


def _copy_path(source: Path, target: Path, strategy: str, stats: CopyStats) -> None:
    if source.is_dir():
        files = [path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in MODEL_FILE_SUFFIXES]
        for file_path in files:
            relative = file_path.relative_to(source)
            _copy_file(file_path, target / relative, strategy, stats)
        return
    _copy_file(source, target / source.name, strategy, stats)


def _copy_file(source: Path, target: Path, strategy: str, stats: CopyStats) -> None:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        final_target = target
        if target.exists():
            if strategy == "skip":
                stats.skipped += 1
                stats.logs.append(f"跳过已存在：{target}")
                return
            if strategy == "rename":
                index = 1
                while final_target.exists():
                    final_target = target.with_name(f"{target.stem}_{index}{target.suffix}")
                    index += 1
        shutil.copy2(source, final_target)
        stats.copied += 1
        stats.logs.append(f"复制：{source} -> {final_target}")
    except OSError as exc:
        stats.failed += 1
        stats.logs.append(f"失败：{source}，原因：{exc}")


def migrate_model_library(source_root: Path, strategy: str = "skip") -> CopyStats:
    ensure_project_model_dirs()
    stats = CopyStats()
    sources = discover_model_sources(source_root)
    if not sources:
        stats.logs.append(f"未识别模型目录：{source_root}")
        return stats
    for engine_id, model_id, source in sources:
        target = project_model_dir_for(engine_id)
        if model_id:
            target = target / model_id
        _copy_path(source, target, strategy, stats)
    return stats


def get_video_upscale_model_root(engine_id: str) -> Path:
    return get_engine_models_dir(engine_id)


def get_interpolation_model_root(engine_id: str) -> Path:
    return get_video_interpolation_models_dir(engine_id)


def list_interpolation_models(engine_id: str) -> list[str]:
    model_root = get_interpolation_model_root(engine_id)
    if not model_root.exists():
        return []
    models = [
        child.name
        for child in model_root.iterdir()
        if child.is_dir() and _contains_strict_model_files(child)
    ]
    if not models and _contains_strict_model_files(model_root):
        models.append("")
    return sorted(models)


def list_interpolation_model_info(engine_id: str) -> list[InterpolationModelInfo]:
    model_root = get_interpolation_model_root(engine_id)
    if not model_root.exists():
        return []
    candidates = [child for child in model_root.iterdir() if child.is_dir()]
    if not candidates and _contains_strict_model_files(model_root):
        candidates = [model_root]
    results: list[InterpolationModelInfo] = []
    for model_dir in sorted(candidates, key=lambda item: item.name):
        files = [path for path in model_dir.rglob("*") if path.is_file()]
        strict_files = [path for path in files if path.suffix.lower() in STRICT_MODEL_FILE_SUFFIXES]
        results.append(
            InterpolationModelInfo(
                name="" if model_dir == model_root else model_dir.name,
                path=model_dir,
                file_count=len(files),
                size_bytes=sum(path.stat().st_size for path in files),
                available=bool(strict_files),
            )
        )
    return results


def resolve_interpolation_model_dir(engine_id: str, model_name: str = "") -> Path:
    model_root = get_interpolation_model_root(engine_id)
    model_dir = model_root / model_name if model_name else model_root
    if not model_dir.exists() or not _contains_strict_model_files(model_dir):
        label = f"{engine_id.upper()} {model_name}".strip()
        raise FileNotFoundError(f"Please import {label} models into the project model library first: {model_dir}")
    if not is_project_model_path(model_dir):
        raise ValueError(f"{engine_id.upper()} model path must be inside the project model library: {model_dir}")
    return model_dir


def validate_interpolation_model_root(engine_id: str) -> Path:
    model_root = get_interpolation_model_root(engine_id)
    if not model_root.exists() or not _contains_model_files(model_root):
        raise FileNotFoundError(f"请先从素材库导入 {engine_id.upper()} 模型到项目模型库：{model_root}")
    if not is_project_model_path(model_root):
        raise ValueError(f"{engine_id.upper()} 模型路径必须位于项目模型库：{model_root}")
    return model_root


def build_rife_command(
    executable_path: Path,
    input_frames: Path,
    output_frames: Path,
    scale: int = 2,
    model_name: str = "",
    gpu_id: str = "auto",
    use_tta: bool = False,
    target_frame_count: int | None = None,
    output_pattern: str = "%06d.png",
) -> list[str]:
    model_root = resolve_interpolation_model_dir("rife", model_name)
    target_count = target_frame_count or scale
    command = [
        str(executable_path),
        "-i",
        str(input_frames.resolve()),
        "-o",
        str(output_frames.resolve()),
        "-m",
        str(model_root.resolve()),
        "-n",
        str(target_count),
        "-f",
        output_pattern,
    ]
    if gpu_id and gpu_id != "auto":
        command.extend(["-g", gpu_id])
    if use_tta:
        command.append("-x")
    return command


def build_ifrnet_command(
    executable_path: Path,
    input_frames: Path,
    output_frames: Path,
    scale: int = 2,
    model_name: str = "",
    gpu_id: str = "auto",
    use_tta: bool = False,
    target_frame_count: int | None = None,
    output_pattern: str = "%06d.png",
) -> list[str]:
    if scale not in {2, 4}:
        raise ValueError(f"IFRNet 仅支持 2x / 4x，当前：{scale}x")
    model_root = resolve_interpolation_model_dir("ifrnet", model_name)
    target_count = target_frame_count or scale
    command = [
        str(executable_path),
        "-i",
        str(input_frames.resolve()),
        "-o",
        str(output_frames.resolve()),
        "-m",
        str(model_root.resolve()),
        "-n",
        str(target_count),
        "-f",
        output_pattern,
    ]
    if gpu_id and gpu_id != "auto":
        command.extend(["-g", gpu_id])
    if use_tta:
        command.append("-x")
    return command


def import_custom_model(engine_id: str, source: Path, model_name: str | None = None, strategy: str = "rename") -> tuple[str, CopyStats]:
    ensure_project_model_dirs()
    clean_name = model_name or source.stem if source.is_file() else source.name
    clean_name = "".join(char if char.isalnum() or char in "-_." else "_" for char in clean_name).strip("._") or "custom"
    target = get_engine_models_dir(engine_id) / "custom" / clean_name
    stats = CopyStats()
    _copy_path(source, target, strategy, stats)
    return f"custom/{clean_name}", stats


def detect_external_dependencies(settings_data: dict) -> list[str]:
    findings: list[str] = []
    def walk(value: object, key_path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{key_path}.{key}" if key_path else str(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{key_path}[{index}]")
        elif isinstance(value, str) and value and looks_like_external_asset_path(value):
            findings.append(f"{key_path}: {value}")
    walk(settings_data, "")
    return findings


def is_valid_runtime_model_dir(path: Path) -> bool:
    return path.exists() and is_project_model_path(path)
