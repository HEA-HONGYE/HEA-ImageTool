from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from image_toolbox.core.paths import (
    ensure_project_model_dirs,
    get_engine_models_dir,
    get_models_root,
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

KNOWN_MODEL_DIRS = {
    "realesrgan": ["realesrgan-x4plus", "realesrgan-x4plus-anime", "realesrnet-x4plus"],
    "waifu2x": ["cunet", "upconv_7", "anime_style_art_rgb", "models-cunet", "models-upconv_7", "models-upconv_7_anime_style_art_rgb"],
    "realcugan": ["models-se", "models-pro", "models-nose"],
    "realsr": ["models-DF2K", "models-DF2K_JPEG"],
    "srmd": ["srmd", "srmdnf", "models-srmd"],
    "anime4k": ["Anime4K", "anime4k"],
}

MODEL_DIR_ALIASES = {
    ("waifu2x", "models-cunet"): "cunet",
    ("waifu2x", "models-upconv_7"): "upconv_7",
    ("waifu2x", "models-upconv_7_anime_style_art_rgb"): "anime_style_art_rgb",
    ("srmd", "models-srmd"): "",
}


@dataclass
class CopyStats:
    copied: int = 0
    skipped: int = 0
    failed: int = 0
    logs: list[str] = field(default_factory=list)


def project_model_dir_for(engine_id: str, model_id: str = "") -> Path:
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


def discover_model_sources(source_root: Path) -> list[tuple[str, str, Path]]:
    source_root = source_root.resolve()
    discovered: dict[tuple[str, str, Path], tuple[str, str, Path]] = {}
    if not source_root.exists():
        return []
    candidates = [source_root]
    candidates.extend(path for path in source_root.rglob("*") if path.is_dir())
    for path in candidates:
        name = path.name
        for engine_id, known_names in KNOWN_MODEL_DIRS.items():
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
        target = get_engine_models_dir(engine_id)
        if model_id:
            target = target / model_id
        _copy_path(source, target, strategy, stats)
    return stats


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
