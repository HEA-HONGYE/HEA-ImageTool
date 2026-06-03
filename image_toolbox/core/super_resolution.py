from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from image_toolbox.core.image_ops import unique_output_path


REALESRGAN_ROOT = (
    Path(__file__).resolve().parents[2]
    / "ai超分参考文件"
    / "realesrga图片放大"
    / "realesrgan-ncnn-vulkan-20211212-windows"
)
REALESRGAN_EXE = REALESRGAN_ROOT / "realesrgan-ncnn-vulkan.exe"
REALESRGAN_MODELS = REALESRGAN_ROOT / "models"

REALESRGAN_MODELS_BY_NAME = {
    "realesrgan-x4plus": "通用照片 x4",
    "realesrgan-x4plus-anime": "动漫插画 x4",
    "realesrnet-x4plus": "保守增强 x4",
}


def ensure_realesrgan_available() -> None:
    if not REALESRGAN_EXE.exists():
        raise FileNotFoundError(f"未找到 Real-ESRGAN 引擎：{REALESRGAN_EXE}")
    if not REALESRGAN_MODELS.exists():
        raise FileNotFoundError(f"未找到 Real-ESRGAN 模型目录：{REALESRGAN_MODELS}")


def upscale_with_realesrgan(
    source: Path,
    output_dir: Path,
    model_name: str,
    scale: int,
    output_format: str,
    tile_size: int,
    gpu_id: str,
    threads: str,
    use_tta: bool,
    progress: Callable[[str], None],
) -> Path:
    ensure_realesrgan_available()

    suffix = f".{output_format.lower()}"
    output_path = unique_output_path(output_dir, f"{source.stem}_ai{scale}x", suffix)
    command = [
        str(REALESRGAN_EXE),
        "-i",
        str(source.resolve()),
        "-o",
        str(output_path.resolve()),
        "-n",
        model_name,
        "-s",
        str(scale),
        "-t",
        str(tile_size),
        "-g",
        gpu_id.strip() or "auto",
        "-j",
        threads.strip() or "1:2:2",
        "-f",
        output_format.lower(),
    ]
    if use_tta:
        command.append("-x")

    progress(f"AI 超分：{source.name} -> {output_path.name}")
    progress(f"模型：{model_name}，倍率：{scale}x，格式：{output_format.lower()}")

    process = subprocess.Popen(
        command,
        cwd=REALESRGAN_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )

    assert process.stdout is not None
    last_percent = ""
    for line in process.stdout:
        message = line.strip()
        if not message:
            continue
        if message.endswith("%"):
            last_percent = message
            continue
        progress(message)

    return_code = process.wait()
    if last_percent:
        progress(f"引擎进度：{last_percent}")
    if return_code != 0:
        raise RuntimeError(f"Real-ESRGAN 处理失败，退出码：{return_code}")
    if not output_path.exists():
        raise RuntimeError("Real-ESRGAN 已结束，但没有生成输出文件。")

    return output_path
