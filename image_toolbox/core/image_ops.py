from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

SUPPORTED_INPUTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_INPUTS


def unique_output_path(directory: Path, stem: str, suffix: str) -> Path:
    candidate = directory / f"{stem}{suffix}"
    index = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{index}{suffix}"
        index += 1
    return candidate


def compress_image(
    source: Path,
    output_dir: Path,
    quality: int,
    keep_format: bool,
    progress: Callable[[str], None],
) -> Path:
    suffix = source.suffix.lower() if keep_format else ".jpg"
    if suffix == ".jpeg":
        suffix = ".jpg"

    output_path = unique_output_path(output_dir, f"{source.stem}_compressed", suffix)
    with Image.open(source) as image:
        save_image = image
        save_kwargs: dict[str, object] = {"optimize": True}

        if suffix in {".jpg", ".jpeg"}:
            save_image = image.convert("RGB")
            save_kwargs.update({"quality": quality, "progressive": True})
        elif suffix == ".webp":
            save_kwargs.update({"quality": quality, "method": 6})
        elif suffix == ".png":
            save_kwargs.update({"compress_level": 9})

        progress(f"压缩：{source.name} -> {output_path.name}")
        save_image.save(output_path, **save_kwargs)

    return output_path


def convert_image(
    source: Path,
    output_dir: Path,
    target_format: str,
    quality: int,
    progress: Callable[[str], None],
) -> Path:
    suffix = f".{target_format.lower()}"
    output_path = unique_output_path(output_dir, f"{source.stem}_{target_format.lower()}", suffix)

    with Image.open(source) as image:
        save_kwargs: dict[str, object] = {}
        save_image = image

        if suffix in {".jpg", ".jpeg"}:
            save_image = image.convert("RGB")
            save_kwargs.update({"quality": quality, "optimize": True, "progressive": True})
        elif suffix == ".webp":
            save_kwargs.update({"quality": quality, "method": 6})
        elif suffix == ".png":
            save_kwargs.update({"optimize": True})

        progress(f"转换：{source.name} -> {output_path.name}")
        save_image.save(output_path, **save_kwargs)

    return output_path


def _prepare_for_suffix(image: Image.Image, suffix: str) -> Image.Image:
    if suffix in {".jpg", ".jpeg", ".bmp"} and image.mode in {"RGBA", "LA", "P"}:
        background = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == "P":
            image = image.convert("RGBA")
        background.paste(image, mask=image.getchannel("A") if "A" in image.getbands() else None)
        return background
    return image


def _save_processed_image(image: Image.Image, output_path: Path, quality: int = 90) -> None:
    suffix = output_path.suffix.lower()
    save_image = _prepare_for_suffix(image, suffix)
    save_kwargs: dict[str, object] = {}
    if suffix in {".jpg", ".jpeg"}:
        save_kwargs.update({"quality": quality, "optimize": True, "progressive": True})
    elif suffix == ".webp":
        save_kwargs.update({"quality": quality, "method": 6})
    elif suffix == ".png":
        save_kwargs.update({"optimize": True})
    save_image.save(output_path, **save_kwargs)


def resize_image(
    source: Path,
    output_dir: Path,
    mode: str,
    scale_percent: int,
    width: int,
    height: int,
    keep_aspect: bool,
    progress: Callable[[str], None],
) -> Path:
    output_path = unique_output_path(output_dir, f"{source.stem}_resized", source.suffix.lower())
    with Image.open(source) as image:
        original_width, original_height = image.size
        if mode == "percent":
            ratio = max(scale_percent, 1) / 100
            new_size = (max(1, int(original_width * ratio)), max(1, int(original_height * ratio)))
        else:
            target_width = max(width, 1)
            target_height = max(height, 1)
            if keep_aspect:
                ratio = min(target_width / original_width, target_height / original_height)
                new_size = (max(1, int(original_width * ratio)), max(1, int(original_height * ratio)))
            else:
                new_size = (target_width, target_height)

        progress(f"改尺寸：{source.name} -> {output_path.name} ({new_size[0]}x{new_size[1]})")
        resized = image.resize(new_size, Image.Resampling.LANCZOS)
        _save_processed_image(resized, output_path)
    return output_path


def _position_xy(canvas_size: tuple[int, int], mark_size: tuple[int, int], position: str, margin: int = 24) -> tuple[int, int]:
    canvas_width, canvas_height = canvas_size
    mark_width, mark_height = mark_size
    positions = {
        "左上": (margin, margin),
        "上中": ((canvas_width - mark_width) // 2, margin),
        "右上": (canvas_width - mark_width - margin, margin),
        "居中": ((canvas_width - mark_width) // 2, (canvas_height - mark_height) // 2),
        "左下": (margin, canvas_height - mark_height - margin),
        "下中": ((canvas_width - mark_width) // 2, canvas_height - mark_height - margin),
        "右下": (canvas_width - mark_width - margin, canvas_height - mark_height - margin),
    }
    return positions.get(position, positions["右下"])


def add_text_watermark(
    source: Path,
    output_dir: Path,
    text: str,
    position: str,
    opacity: int,
    font_size: int,
    progress: Callable[[str], None],
) -> Path:
    output_path = unique_output_path(output_dir, f"{source.stem}_watermark", source.suffix.lower())
    with Image.open(source) as image:
        base = image.convert("RGBA")
        overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        try:
            font = ImageFont.truetype("msyh.ttc", font_size)
        except OSError:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        mark_size = (bbox[2] - bbox[0], bbox[3] - bbox[1])
        xy = _position_xy(base.size, mark_size, position)
        alpha = max(0, min(opacity, 100)) * 255 // 100
        draw.text(xy, text, font=font, fill=(255, 255, 255, alpha), stroke_width=2, stroke_fill=(0, 0, 0, alpha // 2))
        result = Image.alpha_composite(base, overlay)
        progress(f"文字水印：{source.name} -> {output_path.name}")
        _save_processed_image(result, output_path)
    return output_path


def add_image_watermark(
    source: Path,
    output_dir: Path,
    watermark_path: Path,
    position: str,
    opacity: int,
    scale_percent: int,
    progress: Callable[[str], None],
) -> Path:
    output_path = unique_output_path(output_dir, f"{source.stem}_watermark", source.suffix.lower())
    with Image.open(source) as image, Image.open(watermark_path) as watermark:
        base = image.convert("RGBA")
        mark = watermark.convert("RGBA")
        scale = max(scale_percent, 1) / 100
        mark_size = (max(1, int(mark.width * scale)), max(1, int(mark.height * scale)))
        mark = mark.resize(mark_size, Image.Resampling.LANCZOS)
        alpha = mark.getchannel("A").point(lambda value: value * max(0, min(opacity, 100)) // 100)
        mark.putalpha(alpha)
        xy = _position_xy(base.size, mark.size, position)
        base.alpha_composite(mark, xy)
        progress(f"图片水印：{source.name} -> {output_path.name}")
        _save_processed_image(base, output_path)
    return output_path


def rename_image(
    source: Path,
    output_dir: Path,
    new_stem: str,
    progress: Callable[[str], None],
) -> Path:
    output_path = unique_output_path(output_dir, new_stem, source.suffix.lower())
    with Image.open(source) as image:
        progress(f"重命名：{source.name} -> {output_path.name}")
        _save_processed_image(image.copy(), output_path)
    return output_path
