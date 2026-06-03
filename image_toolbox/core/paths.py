from __future__ import annotations

import sys
from pathlib import Path


def get_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_assets_dir() -> Path:
    return get_project_root() / "assets"


def get_models_root() -> Path:
    return get_assets_dir() / "models"


def get_engine_models_dir(engine_id: str) -> Path:
    return get_models_root() / engine_id


def ensure_project_model_dirs() -> None:
    layout = {
        "realesrgan": ["realesrgan-x4plus", "realesrgan-x4plus-anime", "realesrnet-x4plus", "custom"],
        "waifu2x": ["cunet", "upconv_7", "anime_style_art_rgb", "custom"],
        "realcugan": ["models-se", "models-pro", "models-nose", "custom"],
        "realsr": ["models-DF2K", "models-DF2K_JPEG", "custom"],
        "srmd": ["srmd", "srmdnf", "custom"],
        "anime4k": ["custom"],
    }
    root = get_models_root()
    root.mkdir(parents=True, exist_ok=True)
    for engine_id, model_dirs in layout.items():
        engine_root = root / engine_id
        engine_root.mkdir(parents=True, exist_ok=True)
        for model_dir in model_dirs:
            (engine_root / model_dir).mkdir(parents=True, exist_ok=True)


def is_inside_path(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def is_project_model_path(path: Path) -> bool:
    return is_inside_path(path, get_models_root())


def looks_like_external_asset_path(path: str | Path) -> bool:
    text = str(path).replace("\\", "/").lower()
    markers = [
        "ai超分参考",
        "ai瓒呭垎",
        "waifu2x-extension-gui",
        "realesrga",
        "realesrgan-ncnn-vulkan",
        "waifu2x-ncnn-vulkan",
        "realcugan-ncnn-vulkan",
        "realsr-ncnn-vulkan",
        "srmd-ncnn-vulkan",
    ]
    return any(marker.lower() in text for marker in markers)
