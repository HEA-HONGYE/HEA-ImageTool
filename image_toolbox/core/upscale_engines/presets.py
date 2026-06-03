from __future__ import annotations

from image_toolbox.core.upscale_engines.types import UpscalePreset


UPSCALE_PRESETS = [
    UpscalePreset("photo_hd", "照片高清", "通用照片 4x 高清放大。", "realesrgan", "realesrgan-x4plus", 4),
    UpscalePreset("anime_art", "动漫插画", "动漫、插画和线条素材 4x 放大。", "realesrgan", "realesrgan-x4plus-anime", 4),
    UpscalePreset("conservative", "保守增强", "较保守的 4x 增强，减少过度锐化。", "realesrgan", "realesrnet-x4plus", 4),
    UpscalePreset("quick_preview", "快速预览", "使用 2x 快速查看效果。", "realesrgan", "realesrgan-x4plus", 2),
    UpscalePreset(
        "low_memory",
        "低显存稳定",
        "更保守的 Tile 设置，适合大图或显存较小的电脑。",
        "realesrgan",
        "realesrgan-x4plus",
        2,
        low_memory_mode=True,
        tile_mode="manual",
        tile_size=128,
    ),
    UpscalePreset(
        "waifu2x_line_art",
        "动漫线稿",
        "Waifu2x 线稿和干净插画 4x 增强。",
        "waifu2x",
        "anime_style_art",
        4,
        noise_level=1,
    ),
    UpscalePreset(
        "waifu2x_illustration",
        "动漫插画",
        "Waifu2x CUNet 插画 4x 增强，中等降噪。",
        "waifu2x",
        "cunet",
        4,
        noise_level=2,
    ),
    UpscalePreset(
        "waifu2x_restore",
        "动漫修复",
        "Waifu2x CUNet 插画 4x 修复，较强降噪。",
        "waifu2x",
        "cunet",
        4,
        noise_level=3,
    ),
]
