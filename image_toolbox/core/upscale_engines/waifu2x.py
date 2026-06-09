from __future__ import annotations

import re
import subprocess
from pathlib import Path

from image_toolbox.core.engine_settings import resolve_executable_path, resolve_model_root
from image_toolbox.core.paths import get_engine_models_dir, get_project_root
from image_toolbox.core.upscale_engines.base import BaseUpscaleEngine
from image_toolbox.core.upscale_engines.model_paths import ensure_named_model_dir
from image_toolbox.core.upscale_engines.types import (
    ENGINE_NOT_FOUND,
    GPU_MEMORY_ERROR,
    GPU_UNSUPPORTED,
    INVALID_CONFIG,
    MODEL_NOT_FOUND,
    OUTPUT_ERROR,
    PROCESS_FAILED,
    VULKAN_ERROR,
    EngineCommand,
    EngineError,
    EngineInfo,
    EngineOption,
    UpscaleConfig,
    UpscaleModel,
)


WAIFU2X_ROOT = get_project_root() / "engines" / "waifu2x-ncnn-vulkan"
WAIFU2X_EXE = WAIFU2X_ROOT / "waifu2x-ncnn-vulkan_waifu2xEX.exe"
WAIFU2X_FP16_EXE = WAIFU2X_ROOT / "waifu2x-ncnn-vulkan-fp16p_waifu2xEX.exe"
WAIFU2X_LOW_MEMORY_TILE = 128

MODEL_ALIASES = {
    "cunet": "cunet",
    "upconv_7": "upconv_7",
    "anime_style_art_rgb": "anime_style_art_rgb",
    "anime_style_art": "anime_style_art_rgb",
}

MODEL_RUNTIME_DIRS = {
    "cunet": "models-cunet",
    "upconv_7": "models-upconv_7_photo",
    "anime_style_art_rgb": "models-upconv_7_anime_style_art_rgb",
    "anime_style_art": "models-upconv_7_anime_style_art_rgb",
}


class Waifu2xEngine(BaseUpscaleEngine):
    engine_id = "waifu2x"
    display_name = "Waifu2x"
    description = "适合动漫插画、线稿、CG 图像增强。"
    supported_models = [
        UpscaleModel("cunet", "CUNet", "适合动漫插画与通用二次元素材，降噪和放大效果均衡。"),
        UpscaleModel("anime_style_art_rgb", "Anime Style Art RGB", "适合 RGB 动漫插画和 CG。"),
        UpscaleModel("anime_style_art", "Anime Style Art", "自动映射到当前 waifu2x-ncnn-vulkan 可用的动漫模型。"),
    ]
    supported_scales = [1, 2, 4, 8]
    supported_formats = ["png", "jpg", "webp"]
    supports_tile = True
    supports_gpu_info = True
    supports_progress_parse = True
    supports_noise = True

    def __init__(self) -> None:
        self._health_cache: tuple[bool, str] | None = None

    @property
    def executable_path(self) -> Path:
        default = WAIFU2X_EXE if WAIFU2X_EXE.exists() else WAIFU2X_FP16_EXE
        return resolve_executable_path(self.engine_id, default)

    @property
    def models_path(self) -> Path:
        return resolve_model_root(self.engine_id, get_engine_models_dir("waifu2x"))

    def _model_dir(self, model_name: str) -> Path:
        return self.models_path / MODEL_ALIASES.get(model_name, model_name)

    def _runtime_model_dir(self, model_name: str) -> Path:
        model_dir = self._model_dir(model_name)
        required_name = MODEL_RUNTIME_DIRS.get(model_name)
        if required_name is None or model_name.startswith("custom/"):
            return model_dir
        native_dir = self.models_path / required_name
        if native_dir.exists():
            return native_dir
        return ensure_named_model_dir(model_dir, required_name, self.engine_id)

    def validate_config(self, config: UpscaleConfig) -> None:
        if not self.executable_path.exists():
            raise FileNotFoundError(f"{ENGINE_NOT_FOUND}：找不到 Waifu2x 可执行文件：{WAIFU2X_EXE}")
        if not self.models_path.exists():
            raise FileNotFoundError(f"{MODEL_NOT_FOUND}：找不到 Waifu2x 模型根目录：{self.models_path}")
        if config.model_name not in {model.name for model in self.supported_models} and not config.model_name.startswith("custom/"):
            raise ValueError(f"{INVALID_CONFIG}：不支持的 Waifu2x 模型：{config.model_name}")
        model_dir = self._model_dir(config.model_name)
        if not model_dir.exists():
            raise FileNotFoundError(f"{MODEL_NOT_FOUND}：未找到 Waifu2x 模型目录：{model_dir}")
        if not any(model_dir.glob("*.param")) or not any(model_dir.glob("*.bin")):
            raise FileNotFoundError(f"{MODEL_NOT_FOUND}：Waifu2x 模型文件不完整：{model_dir}")
        if config.scale not in self.supported_scales:
            raise ValueError(f"{INVALID_CONFIG}：Waifu2x 当前支持 1x、2x、4x、8x。")
        if config.noise_level not in {-1, 0, 1, 2, 3}:
            raise ValueError(f"{INVALID_CONFIG}：Waifu2x 降噪等级必须是 -1、0、1、2、3。")
        if not config.keep_original_format and config.output_format not in self.supported_formats:
            raise ValueError(f"{INVALID_CONFIG}：Waifu2x 不支持输出格式：{config.output_format}")
        if not 0 <= config.tile_size <= 2048:
            raise ValueError(f"{INVALID_CONFIG}：Tile 参数必须在 0 到 2048 之间。")

    def build_command(self, input_path: Path, output_path: Path, config: UpscaleConfig, engine_format: str) -> EngineCommand:
        command = [
            str(self.executable_path),
            "-i",
            str(input_path.resolve()),
            "-o",
            str(output_path.resolve()),
            "-n",
            str(config.noise_level),
            "-s",
            str(config.scale),
            "-t",
            str(config.tile_size if config.tile_mode == "manual" else self.get_default_tile(config.low_memory_mode)),
            "-m",
            str(self._runtime_model_dir(config.model_name).resolve()),
            "-g",
            config.gpu_id.strip() or "auto",
            "-j",
            config.threads.strip() or "1:2:2",
            "-f",
            engine_format,
        ]
        if config.use_tta:
            command.append("-x")
        return EngineCommand(command=command, cwd=WAIFU2X_ROOT, engine_format=engine_format)

    def parse_progress(self, line: str) -> int | None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
        if not match:
            return None
        return max(0, min(100, int(float(match.group(1)))))

    def parse_error(self, output: str, returncode: int | None) -> EngineError:
        text = output.lower()
        if "invalid gpu device" in text or "no vulkan device" in text or "unsupported gpu" in text:
            return EngineError(GPU_UNSUPPORTED, "GPU 不支持或未找到可用 Vulkan 设备。", output)
        if "failed to create instance" in text or "vulkan" in text and "failed" in text:
            return EngineError(VULKAN_ERROR, "Vulkan 初始化失败，请检查显卡驱动和 Vulkan Runtime。", output)
        if "out of memory" in text or "vk_error" in text or "memory" in text:
            return EngineError(GPU_MEMORY_ERROR, "疑似显存不足，请尝试低显存模式或更小 Tile。", output)
        if "model" in text and ("not found" in text or "failed" in text):
            return EngineError(MODEL_NOT_FOUND, "Waifu2x 模型不存在或加载失败。", output)
        if "input" in text and ("not found" in text or "failed" in text):
            return EngineError(PROCESS_FAILED, "输入文件不存在或读取失败。", output)
        if "output" in text and ("failed" in text or "write" in text):
            return EngineError(OUTPUT_ERROR, "输出失败，请检查输出目录权限。", output)
        return EngineError(PROCESS_FAILED, f"Waifu2x 执行失败，返回码：{returncode}", output)

    def get_default_tile(self, low_memory: bool = False) -> int:
        return WAIFU2X_LOW_MEMORY_TILE if low_memory else 0

    def get_model_info(self) -> list[UpscaleModel]:
        available_models = []
        for model in self.supported_models:
            if self._model_dir(model.name).exists():
                available_models.append(model)
        custom_root = self.models_path / "custom"
        if custom_root.exists():
            for model_dir in custom_root.iterdir():
                if model_dir.is_dir() and any(model_dir.glob("*.param")) and any(model_dir.glob("*.bin")):
                    model_id = f"custom/{model_dir.name}"
                    available_models.append(UpscaleModel(model_id, model_dir.name, "导入到项目模型库的自定义模型。"))
        return available_models

    def get_model_path(self, model_id: str) -> Path | None:
        return self._model_dir(model_id)

    def get_noise_options(self) -> list[EngineOption]:
        return [
            EngineOption("关闭", -1, "关闭降噪。"),
            EngineOption("弱", 0, "轻度降噪。"),
            EngineOption("中", 1, "中等降噪。"),
            EngineOption("强", 2, "较强降噪。"),
            EngineOption("极强", 3, "最强降噪。"),
        ]

    def health_check(self) -> tuple[bool, str]:
        if self._health_cache is not None:
            return self._health_cache
        if not self.executable_path.exists():
            self._health_cache = False, f"找不到可执行文件：{WAIFU2X_EXE}"
            return self._health_cache
        if not self.models_path.exists():
            self._health_cache = False, f"找不到模型根目录：{self.models_path}"
            return self._health_cache
        missing = [model.name for model in self.supported_models if not self._model_dir(model.name).exists()]
        if missing:
            self._health_cache = False, f"缺少模型目录：{', '.join(missing)}"
            return self._health_cache
        try:
            completed = subprocess.run(
                [str(self.executable_path), "-h"],
                cwd=WAIFU2X_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
            )
        except OSError as exc:
            self._health_cache = False, f"Waifu2x 无法启动：{exc}"
            return self._health_cache
        output = completed.stdout or ""
        if "waifu2x-ncnn-vulkan" not in output.lower():
            self._health_cache = False, "Waifu2x 启动检查失败。"
            return self._health_cache

        self._health_cache = True, ""
        return self._health_cache

    def get_info(self) -> EngineInfo:
        available, reason = self.health_check()
        return EngineInfo(
            engine_id=self.engine_id,
            display_name=self.display_name,
            description=self.description,
            available=available,
            executable_path=self.executable_path,
            models=self.get_model_info(),
            supported_scales=self.supported_scales,
            supported_formats=self.supported_formats,
            unavailable_reason=reason,
        )
