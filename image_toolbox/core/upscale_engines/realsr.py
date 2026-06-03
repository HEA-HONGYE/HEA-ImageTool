from __future__ import annotations

import re
import subprocess
from pathlib import Path

from image_toolbox.core.engine_settings import resolve_executable_path, resolve_model_root
from image_toolbox.core.upscale_engines.base import BaseUpscaleEngine
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
    UpscaleConfig,
    UpscaleModel,
)


REALSR_ROOT = Path(__file__).resolve().parents[3] / "ai超分参考文件" / "waifu2x-extension-gui" / "realsr-ncnn-vulkan"
REALSR_EXE = REALSR_ROOT / "realsr-ncnn-vulkan_waifu2xEX.exe"
REALSR_FALLBACK_EXE = REALSR_ROOT / "realsr-ncnn-vulkan.exe"
REALSR_LOW_MEMORY_TILE = 128


class RealSrEngine(BaseUpscaleEngine):
    engine_id = "realsr"
    display_name = "RealSR"
    description = "适合真实照片、自然图像增强和超分。"
    supported_models = [
        UpscaleModel("models-DF2K", "照片高清 DF2K", "适合真实照片和自然图像 4x 增强。"),
        UpscaleModel("models-DF2K_JPEG", "JPEG 照片修复 DF2K_JPEG", "适合压缩痕迹较明显的照片 4x 修复。"),
    ]
    supported_scales = [4]
    supported_formats = ["png", "jpg", "webp"]
    supports_tile = True
    supports_gpu_info = True
    supports_progress_parse = True

    def __init__(self) -> None:
        self._health_cache: tuple[bool, str] | None = None

    @property
    def executable_path(self) -> Path:
        default = REALSR_EXE if REALSR_EXE.exists() else REALSR_FALLBACK_EXE
        return resolve_executable_path(self.engine_id, default)

    @property
    def models_path(self) -> Path:
        return resolve_model_root(self.engine_id, REALSR_ROOT)

    def _model_dir(self, model_name: str) -> Path:
        return self.models_path / model_name

    def validate_config(self, config: UpscaleConfig) -> None:
        if not self.executable_path.exists():
            raise FileNotFoundError(f"{ENGINE_NOT_FOUND}：找不到 RealSR 可执行文件：{REALSR_EXE}")
        if config.model_name not in {model.name for model in self.supported_models}:
            raise ValueError(f"{INVALID_CONFIG}：不支持的 RealSR 模型：{config.model_name}")
        model_dir = self._model_dir(config.model_name)
        if not model_dir.exists():
            raise FileNotFoundError(f"{MODEL_NOT_FOUND}：未找到 RealSR 模型目录：{model_dir}")
        if not (model_dir / "x4.param").exists() or not (model_dir / "x4.bin").exists():
            raise FileNotFoundError(f"{MODEL_NOT_FOUND}：RealSR 模型文件不完整：{model_dir}")
        if config.scale != 4:
            raise ValueError(f"{INVALID_CONFIG}：RealSR 当前只支持 4x。")
        if not 0 <= config.tile_size <= 2048:
            raise ValueError(f"{INVALID_CONFIG}：Tile 参数必须在 0 到 2048 之间。")
        if not config.keep_original_format and config.output_format not in self.supported_formats:
            raise ValueError(f"{INVALID_CONFIG}：RealSR 不支持输出格式：{config.output_format}")

    def build_command(self, input_path: Path, output_path: Path, config: UpscaleConfig, engine_format: str) -> EngineCommand:
        command = [
            str(self.executable_path),
            "-i",
            str(input_path.resolve()),
            "-o",
            str(output_path.resolve()),
            "-s",
            "4",
            "-t",
            str(config.tile_size if config.tile_mode == "manual" else self.get_default_tile(config.low_memory_mode)),
            "-m",
            str(self._model_dir(config.model_name).resolve()),
            "-g",
            config.gpu_id.strip() or "auto",
            "-j",
            config.threads.strip() or "1:2:2",
            "-f",
            engine_format,
        ]
        if config.use_tta:
            command.append("-x")
        return EngineCommand(command=command, cwd=REALSR_ROOT, engine_format=engine_format)

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
            return EngineError(MODEL_NOT_FOUND, "RealSR 模型不存在或加载失败。", output)
        if "output" in text and ("failed" in text or "write" in text):
            return EngineError(OUTPUT_ERROR, "输出失败，请检查输出目录权限。", output)
        return EngineError(PROCESS_FAILED, f"RealSR 执行失败，返回码：{returncode}", output)

    def get_default_tile(self, low_memory: bool = False) -> int:
        return REALSR_LOW_MEMORY_TILE if low_memory else 0

    def get_model_info(self) -> list[UpscaleModel]:
        available = [model for model in self.supported_models if self._model_dir(model.name).exists()]
        return available or list(self.supported_models)

    def get_model_path(self, model_id: str) -> Path | None:
        return self._model_dir(model_id)

    def health_check(self) -> tuple[bool, str]:
        if self._health_cache is not None:
            return self._health_cache
        if not self.executable_path.exists():
            self._health_cache = False, f"找不到可执行文件：{REALSR_EXE}"
            return self._health_cache
        if not self.get_model_info():
            self._health_cache = False, "未找到可用 RealSR 模型目录。"
            return self._health_cache
        try:
            completed = subprocess.run(
                [str(self.executable_path), "-h"],
                cwd=REALSR_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
            )
        except OSError as exc:
            self._health_cache = False, f"RealSR 无法启动：{exc}"
            return self._health_cache
        if "realsr-ncnn-vulkan" not in (completed.stdout or "").lower():
            self._health_cache = False, "RealSR 启动检查失败。"
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
