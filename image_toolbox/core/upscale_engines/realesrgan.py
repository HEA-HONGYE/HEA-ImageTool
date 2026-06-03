from __future__ import annotations

import re
from pathlib import Path

from image_toolbox.core.upscale_engines.base import BaseUpscaleEngine
from image_toolbox.core.upscale_engines.types import (
    ENGINE_NOT_FOUND,
    GPU_MEMORY_ERROR,
    INVALID_CONFIG,
    MODEL_NOT_FOUND,
    PROCESS_FAILED,
    EngineCommand,
    EngineError,
    EngineInfo,
    UpscaleConfig,
    UpscaleModel,
)


REALESRGAN_ROOT = (
    Path(__file__).resolve().parents[3]
    / "ai超分参考文件"
    / "realesrga图片放大"
    / "realesrgan-ncnn-vulkan-20211212-windows"
)
REALESRGAN_EXE = REALESRGAN_ROOT / "realesrgan-ncnn-vulkan.exe"
REALESRGAN_MODELS = REALESRGAN_ROOT / "models"
REALESRGAN_LOW_MEMORY_TILE = 128


class RealEsrganEngine(BaseUpscaleEngine):
    engine_id = "realesrgan"
    display_name = "Real-ESRGAN"
    description = "适合通用照片、动漫插画和保守增强，支持 2x/4x 超分。"
    supported_models = [
        UpscaleModel("realesrgan-x4plus", "通用照片 x4", "适合照片和通用素材。"),
        UpscaleModel("realesrgan-x4plus-anime", "动漫插画 x4", "适合动漫、插画和线条素材。"),
        UpscaleModel("realesrnet-x4plus", "保守增强 x4", "增强更保守，适合希望减少过度锐化的图片。"),
    ]
    supported_scales = [2, 4]
    supported_formats = ["png", "jpg", "webp"]
    supports_tile = True
    supports_gpu_info = True
    supports_progress_parse = True

    @property
    def executable_path(self) -> Path:
        return REALESRGAN_EXE

    @property
    def models_path(self) -> Path:
        return REALESRGAN_MODELS

    def validate_config(self, config: UpscaleConfig) -> None:
        if not self.executable_path.exists():
            raise FileNotFoundError(f"{ENGINE_NOT_FOUND}：找不到 Real-ESRGAN 可执行文件：{self.executable_path}")
        if not self.models_path.exists():
            raise FileNotFoundError(f"{MODEL_NOT_FOUND}：找不到 Real-ESRGAN 模型目录：{self.models_path}")
        model_names = {model.name for model in self.supported_models}
        if config.model_name not in model_names:
            raise ValueError(f"{INVALID_CONFIG}：不支持的模型：{config.model_name}")
        model_bin = self.models_path / f"{config.model_name}.bin"
        model_param = self.models_path / f"{config.model_name}.param"
        if not model_bin.exists() or not model_param.exists():
            raise FileNotFoundError(f"{MODEL_NOT_FOUND}：未找到模型文件：{config.model_name}.bin / {config.model_name}.param")
        if config.scale not in self.supported_scales:
            raise ValueError(f"{INVALID_CONFIG}：Real-ESRGAN 只支持 2x 或 4x。")
        if not config.keep_original_format and config.output_format not in self.supported_formats:
            raise ValueError(f"{INVALID_CONFIG}：Real-ESRGAN 不支持输出格式：{config.output_format}")
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
            config.model_name,
            "-s",
            str(config.scale),
            "-t",
            str(config.tile_size if config.tile_mode == "manual" else self.get_default_tile(config.low_memory_mode)),
            "-g",
            config.gpu_id.strip() or "auto",
            "-j",
            config.threads.strip() or "1:2:2",
            "-f",
            engine_format,
        ]
        if config.use_tta:
            command.append("-x")
        return EngineCommand(command=command, cwd=REALESRGAN_ROOT, engine_format=engine_format)

    def parse_progress(self, line: str) -> int | None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
        if not match:
            return None
        return max(0, min(100, int(float(match.group(1)))))

    def parse_error(self, output: str, returncode: int | None) -> EngineError:
        text = output.lower()
        if "vk_error" in text or "out of memory" in text or "memory" in text:
            return EngineError(GPU_MEMORY_ERROR, "疑似显存不足，请尝试低显存模式或更小 Tile。", output)
        return EngineError(PROCESS_FAILED, f"Real-ESRGAN 执行失败，返回码：{returncode}", output)

    def get_default_tile(self, low_memory: bool = False) -> int:
        return REALESRGAN_LOW_MEMORY_TILE if low_memory else 0

    def get_model_info(self) -> list[UpscaleModel]:
        return list(self.supported_models)

    def get_info(self) -> EngineInfo:
        available = True
        reason = ""
        if not self.executable_path.exists():
            available = False
            reason = f"找不到可执行文件：{self.executable_path}"
        elif not self.models_path.exists():
            available = False
            reason = f"找不到模型目录：{self.models_path}"
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
