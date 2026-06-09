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


SRMD_ROOT = get_project_root() / "engines" / "srmd-ncnn-vulkan"
SRMD_EXE = SRMD_ROOT / "srmd-ncnn-vulkan_waifu2xEX.exe"
SRMD_FALLBACK_EXE = SRMD_ROOT / "srmd-ncnn-vulkan.exe"
SRMD_MODELS = get_engine_models_dir("srmd")
SRMD_LOW_MEMORY_TILE = 128


class SrmdEngine(BaseUpscaleEngine):
    engine_id = "srmd"
    display_name = "SRMD"
    description = "适合照片去噪、模糊图修复和传统超分增强。"
    supported_models = [
        UpscaleModel("srmd", "SRMD 去噪模型", "支持 2x/3x/4x，并可设置降噪等级。"),
        UpscaleModel("srmdnf", "SRMD 无降噪模型", "适合只放大、不希望额外降噪的图片。"),
    ]
    supported_scales = [2, 3, 4]
    supported_formats = ["png", "jpg", "webp"]
    supports_tile = True
    supports_gpu_info = True
    supports_progress_parse = True
    supports_noise = True

    def __init__(self) -> None:
        self._health_cache: tuple[bool, str] | None = None

    @property
    def executable_path(self) -> Path:
        default = SRMD_EXE if SRMD_EXE.exists() else SRMD_FALLBACK_EXE
        return resolve_executable_path(self.engine_id, default)

    @property
    def models_path(self) -> Path:
        return resolve_model_root(self.engine_id, SRMD_MODELS)

    def _model_root(self, model_name: str) -> Path:
        nested = self.models_path / model_name
        prefix = "srmdnf" if model_name == "srmdnf" else "srmd"
        if nested.exists() and any((nested / f"{prefix}_x{scale}.param").exists() for scale in self.supported_scales):
            return nested
        return self.models_path

    def _runtime_model_root(self, model_name: str) -> Path:
        model_root = self._model_root(model_name)
        native_root = self.models_path / "models-srmd"
        if native_root.exists():
            return native_root
        return ensure_named_model_dir(model_root, "models-srmd", self.engine_id)

    def validate_config(self, config: UpscaleConfig) -> None:
        if not self.executable_path.exists():
            raise FileNotFoundError(f"{ENGINE_NOT_FOUND}：找不到 SRMD 可执行文件：{SRMD_EXE}")
        if not self.models_path.exists():
            raise FileNotFoundError(f"{MODEL_NOT_FOUND}：找不到 SRMD 模型目录：{self.models_path}")
        if config.model_name not in {model.name for model in self.supported_models}:
            raise ValueError(f"{INVALID_CONFIG}：不支持的 SRMD 模型：{config.model_name}")
        if config.scale not in self.supported_scales:
            raise ValueError(f"{INVALID_CONFIG}：SRMD 当前支持 2x、3x、4x。")
        prefix = "srmdnf" if config.model_name == "srmdnf" else "srmd"
        model_root = self._model_root(config.model_name)
        if not (model_root / f"{prefix}_x{config.scale}.param").exists() or not (model_root / f"{prefix}_x{config.scale}.bin").exists():
            raise FileNotFoundError(f"{MODEL_NOT_FOUND}：未找到 SRMD {config.scale}x 模型文件。")
        if config.model_name == "srmdnf" and config.noise_level != -1:
            raise ValueError(f"{INVALID_CONFIG}：SRMD 无降噪模型只允许降噪为 -1。")
        if config.model_name == "srmd" and config.noise_level not in {0, 1, 2, 3}:
            raise ValueError(f"{INVALID_CONFIG}：SRMD 去噪模型当前开放降噪 0、1、2、3。")
        if not 0 <= config.tile_size <= 2048:
            raise ValueError(f"{INVALID_CONFIG}：Tile 参数必须在 0 到 2048 之间。")
        if not config.keep_original_format and config.output_format not in self.supported_formats:
            raise ValueError(f"{INVALID_CONFIG}：SRMD 不支持输出格式：{config.output_format}")

    def build_command(self, input_path: Path, output_path: Path, config: UpscaleConfig, engine_format: str) -> EngineCommand:
        noise = -1 if config.model_name == "srmdnf" else config.noise_level
        command = [
            str(self.executable_path),
            "-i",
            str(input_path.resolve()),
            "-o",
            str(output_path.resolve()),
            "-n",
            str(noise),
            "-s",
            str(config.scale),
            "-t",
            str(config.tile_size if config.tile_mode == "manual" else self.get_default_tile(config.low_memory_mode)),
            "-m",
            str(self._runtime_model_root(config.model_name).resolve()),
            "-g",
            config.gpu_id.strip() or "auto",
            "-j",
            config.threads.strip() or "1:2:2",
            "-f",
            engine_format,
        ]
        if config.use_tta:
            command.append("-x")
        return EngineCommand(command=command, cwd=SRMD_ROOT, engine_format=engine_format)

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
            return EngineError(MODEL_NOT_FOUND, "SRMD 模型不存在或加载失败。", output)
        if "output" in text and ("failed" in text or "write" in text):
            return EngineError(OUTPUT_ERROR, "输出失败，请检查输出目录权限。", output)
        return EngineError(PROCESS_FAILED, f"SRMD 执行失败，返回码：{returncode}", output)

    def get_default_tile(self, low_memory: bool = False) -> int:
        return SRMD_LOW_MEMORY_TILE if low_memory else 0

    def get_model_info(self) -> list[UpscaleModel]:
        if not self.models_path.exists():
            return []
        available = []
        for model in self.supported_models:
            prefix = "srmdnf" if model.name == "srmdnf" else "srmd"
            model_root = self._model_root(model.name)
            if any((model_root / f"{prefix}_x{scale}.param").exists() for scale in self.supported_scales):
                available.append(model)
        return available

    def get_model_path(self, model_id: str) -> Path | None:
        return self.models_path

    def get_noise_options(self) -> list[EngineOption]:
        return [
            EngineOption("不降噪", -1, "使用无降噪模型时选择。"),
            EngineOption("默认", 0, "默认降噪。"),
            EngineOption("弱", 1, "轻度降噪。"),
            EngineOption("中", 2, "中等降噪。"),
            EngineOption("强", 3, "强降噪。"),
        ]

    def health_check(self) -> tuple[bool, str]:
        if self._health_cache is not None:
            return self._health_cache
        if not self.executable_path.exists():
            self._health_cache = False, f"找不到可执行文件：{SRMD_EXE}"
            return self._health_cache
        if not self.models_path.exists():
            self._health_cache = False, f"找不到模型目录：{self.models_path}"
            return self._health_cache
        try:
            completed = subprocess.run(
                [str(self.executable_path), "-h"],
                cwd=SRMD_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
            )
        except OSError as exc:
            self._health_cache = False, f"SRMD 无法启动：{exc}"
            return self._health_cache
        if "srmd-ncnn-vulkan" not in (completed.stdout or "").lower():
            self._health_cache = False, "SRMD 启动检查失败。"
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
