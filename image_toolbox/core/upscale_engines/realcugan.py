from __future__ import annotations

import re
import subprocess
from pathlib import Path

from image_toolbox.core.upscale_engines.base import BaseUpscaleEngine
from image_toolbox.core.upscale_engines.types import (
    ENGINE_NOT_FOUND,
    GPU_MEMORY_ERROR,
    GPU_UNSUPPORTED,
    INPUT_NOT_FOUND,
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


REALCUGAN_ROOT = Path(__file__).resolve().parents[3] / "ai超分参考文件" / "waifu2x-extension-gui" / "realcugan-ncnn-vulkan"
REALCUGAN_EXE = REALCUGAN_ROOT / "realcugan-ncnn-vulkan_W2xEX.exe"
REALCUGAN_FALLBACK_EXE = REALCUGAN_ROOT / "realcugan-ncnn-vulkan.exe"
REALCUGAN_LOW_MEMORY_TILE = 128


class RealCuganEngine(BaseUpscaleEngine):
    engine_id = "realcugan"
    display_name = "Real-CUGAN"
    description = "适合动漫、插画、二次元图片增强。相比通用照片模型，它更偏向强化线条和色块，但处理速度可能较慢。"
    supported_models = [
        UpscaleModel("models-se", "标准模型 SE", "适合常规动漫高清和插画增强。"),
        UpscaleModel("models-pro", "专业模型 PRO", "增强更强，适合动漫修复和线条强化。"),
        UpscaleModel("models-nose", "无降噪模型 NOSE", "保守模型，优先用于不希望额外降噪的素材。"),
    ]
    supported_scales = [2, 3, 4]
    supported_formats = ["png", "jpg", "webp"]
    supports_tile = True
    supports_gpu_info = True
    supports_progress_parse = True
    supports_noise = True
    supports_syncgap = True

    def __init__(self) -> None:
        self._health_cache: tuple[bool, str] | None = None

    @property
    def executable_path(self) -> Path:
        return REALCUGAN_EXE if REALCUGAN_EXE.exists() else REALCUGAN_FALLBACK_EXE

    @property
    def models_path(self) -> Path:
        return REALCUGAN_ROOT

    def _model_dir(self, model_name: str) -> Path:
        return self.models_path / model_name

    def validate_config(self, config: UpscaleConfig) -> None:
        if not self.executable_path.exists():
            raise FileNotFoundError(f"{ENGINE_NOT_FOUND}：找不到 Real-CUGAN 可执行文件：{REALCUGAN_EXE}")
        if not self.models_path.exists():
            raise FileNotFoundError(f"{MODEL_NOT_FOUND}：找不到 Real-CUGAN 模型根目录：{self.models_path}")
        if config.model_name not in {model.name for model in self.supported_models}:
            raise ValueError(f"{INVALID_CONFIG}：不支持的 Real-CUGAN 模型：{config.model_name}")
        model_dir = self._model_dir(config.model_name)
        if not model_dir.exists():
            raise FileNotFoundError(f"{MODEL_NOT_FOUND}：未找到 Real-CUGAN 模型目录：{model_dir}")
        if not any(model_dir.glob("*.param")) or not any(model_dir.glob("*.bin")):
            raise FileNotFoundError(f"{MODEL_NOT_FOUND}：Real-CUGAN 模型文件不完整：{model_dir}")
        if config.scale not in self.supported_scales:
            raise ValueError(f"{INVALID_CONFIG}：Real-CUGAN 当前支持 2x、3x、4x。")
        if config.model_name == "models-nose" and config.scale != 2:
            raise ValueError(f"{INVALID_CONFIG}：models-nose 当前保守只开放 2x。")
        if config.model_name == "models-nose" and config.noise_level != 0:
            raise ValueError(f"{INVALID_CONFIG}：models-nose 当前只允许默认降噪 0。")
        if config.model_name in {"models-se", "models-pro"}:
            allowed_noise = {-1, 0, 1, 2, 3} if config.scale == 2 else {-1, 0, 3}
            if config.noise_level not in allowed_noise:
                raise ValueError(
                    f"{INVALID_CONFIG}：{config.model_name} 的 {config.scale}x 当前只支持降噪 {sorted(allowed_noise)}。"
                )
        if config.syncgap_mode not in {0, 1, 2, 3}:
            raise ValueError(f"{INVALID_CONFIG}：SyncGap 只能选择 0、1、2、3。")
        if not 0 <= config.tile_size <= 2048:
            raise ValueError(f"{INVALID_CONFIG}：Tile 参数必须在 0 到 2048 之间。")
        if not config.keep_original_format and config.output_format not in self.supported_formats:
            raise ValueError(f"{INVALID_CONFIG}：Real-CUGAN 不支持输出格式：{config.output_format}")

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
            "-c",
            str(config.syncgap_mode),
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
        return EngineCommand(command=command, cwd=REALCUGAN_ROOT, engine_format=engine_format)

    def parse_progress(self, line: str) -> int | None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
        if not match:
            return None
        return max(0, min(100, int(float(match.group(1)))))

    def parse_error(self, output: str, returncode: int | None) -> EngineError:
        text = output.lower()
        if "no such file" in text or "input" in text and "not found" in text:
            return EngineError(INPUT_NOT_FOUND, "输入文件不存在或读取失败。", output)
        if "invalid gpu device" in text or "no vulkan device" in text or "unsupported gpu" in text:
            return EngineError(GPU_UNSUPPORTED, "GPU 不支持或未找到可用 Vulkan 设备。", output)
        if "failed to create instance" in text or "vulkan" in text and "failed" in text:
            return EngineError(VULKAN_ERROR, "Vulkan 初始化失败，请检查显卡驱动和 Vulkan Runtime。", output)
        if "out of memory" in text or "vk_error" in text or "memory" in text:
            return EngineError(GPU_MEMORY_ERROR, "疑似显存不足，请尝试低显存模式或更小 Tile。", output)
        if "model" in text and ("not found" in text or "failed" in text):
            return EngineError(MODEL_NOT_FOUND, "Real-CUGAN 模型不存在或加载失败。", output)
        if "output" in text and ("failed" in text or "write" in text):
            return EngineError(OUTPUT_ERROR, "输出失败，请检查输出目录权限。", output)
        return EngineError(PROCESS_FAILED, f"Real-CUGAN 执行失败，返回码：{returncode}", output)

    def get_default_tile(self, low_memory: bool = False) -> int:
        return REALCUGAN_LOW_MEMORY_TILE if low_memory else 0

    def get_model_info(self) -> list[UpscaleModel]:
        available_models = [model for model in self.supported_models if self._model_dir(model.name).exists()]
        return available_models or list(self.supported_models)

    def get_noise_options(self) -> list[EngineOption]:
        return [
            EngineOption("不降噪", -1, "关闭降噪。"),
            EngineOption("默认", 0, "使用模型默认降噪。"),
            EngineOption("弱", 1, "轻度降噪。"),
            EngineOption("中", 2, "中等降噪。"),
            EngineOption("强", 3, "强降噪，画面更干净但可能损失细节。"),
        ]

    def get_syncgap_options(self) -> list[EngineOption]:
        return [
            EngineOption("关闭", 0, "关闭 SyncGap。"),
            EngineOption("质量优先", 1, "优先减少块状痕迹。"),
            EngineOption("平衡", 2, "平衡速度与画面稳定性。"),
            EngineOption("速度优先", 3, "优先速度。"),
        ]

    def health_check(self) -> tuple[bool, str]:
        if self._health_cache is not None:
            return self._health_cache
        if not self.executable_path.exists():
            self._health_cache = False, f"找不到可执行文件：{REALCUGAN_EXE}"
            return self._health_cache
        if not self.models_path.exists():
            self._health_cache = False, f"找不到模型根目录：{self.models_path}"
            return self._health_cache
        if not self.get_model_info():
            self._health_cache = False, "未找到可用模型目录。"
            return self._health_cache
        try:
            help_result = subprocess.run(
                [str(self.executable_path), "-h"],
                cwd=REALCUGAN_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
            )
        except OSError as exc:
            self._health_cache = False, f"Real-CUGAN 无法启动：{exc}"
            return self._health_cache
        if "realcugan-ncnn-vulkan" not in (help_result.stdout or "").lower():
            self._health_cache = False, "Real-CUGAN 启动检查失败。"
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
