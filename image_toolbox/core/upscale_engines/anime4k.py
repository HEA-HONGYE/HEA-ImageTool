from __future__ import annotations

import re
import subprocess
from pathlib import Path

from image_toolbox.core.upscale_engines.base import BaseUpscaleEngine
from image_toolbox.core.upscale_engines.types import (
    ENGINE_NOT_FOUND,
    INVALID_CONFIG,
    OUTPUT_ERROR,
    PROCESS_FAILED,
    EngineCommand,
    EngineError,
    EngineInfo,
    UpscaleConfig,
    UpscaleModel,
)


ANIME4K_ROOT = Path(__file__).resolve().parents[3] / "ai超分参考文件" / "waifu2x-extension-gui" / "Anime4K"
ANIME4K_EXE = ANIME4K_ROOT / "Anime4K_waifu2xEX.exe"


class Anime4kEngine(BaseUpscaleEngine):
    engine_id = "anime4k"
    display_name = "Anime4K"
    description = "适合动漫图片快速增强，速度较快，适合预览和轻量处理。"
    supported_models = [UpscaleModel("default", "默认快速增强", "Anime4KCPP 保守默认参数。")]
    supported_scales = [2]
    supported_formats = ["png", "jpg", "webp"]
    supports_tile = False
    supports_gpu_info = True
    supports_progress_parse = True

    def __init__(self) -> None:
        self._health_cache: tuple[bool, str] | None = None

    @property
    def executable_path(self) -> Path:
        return ANIME4K_EXE

    def validate_config(self, config: UpscaleConfig) -> None:
        if not self.executable_path.exists():
            raise FileNotFoundError(f"{ENGINE_NOT_FOUND}：找不到 Anime4K 可执行文件：{ANIME4K_EXE}")
        if config.model_name != "default":
            raise ValueError(f"{INVALID_CONFIG}：Anime4K 当前只开放默认快速增强。")
        if config.scale != 2:
            raise ValueError(f"{INVALID_CONFIG}：Anime4K 当前保守只开放 2x。")
        if not config.keep_original_format and config.output_format not in self.supported_formats:
            raise ValueError(f"{INVALID_CONFIG}：Anime4K 不支持输出格式：{config.output_format}")

    def build_command(self, input_path: Path, output_path: Path, config: UpscaleConfig, engine_format: str) -> EngineCommand:
        command = [
            str(self.executable_path),
            "-i",
            str(input_path.resolve()),
            "-o",
            str(output_path.resolve()),
            "-z",
            "2",
            "-p",
            "2",
            "-n",
            "2",
            "-c",
            "0.3",
            "-g",
            "1",
            "-q",
            "-a",
        ]
        return EngineCommand(command=command, cwd=ANIME4K_ROOT, engine_format=engine_format)

    def parse_progress(self, line: str) -> int | None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
        if not match:
            return None
        return max(0, min(100, int(float(match.group(1)))))

    def parse_error(self, output: str, returncode: int | None) -> EngineError:
        text = output.lower()
        if "output" in text and ("failed" in text or "write" in text):
            return EngineError(OUTPUT_ERROR, "输出失败，请检查输出目录权限。", output)
        if "opencl" in text and "error" in text:
            return EngineError(PROCESS_FAILED, "Anime4K OpenCL/GPU 执行失败，可尝试关闭其它占用显卡的程序。", output)
        return EngineError(PROCESS_FAILED, f"Anime4K 执行失败，返回码：{returncode}", output)

    def get_default_tile(self, low_memory: bool = False) -> int:
        return 0

    def get_model_info(self) -> list[UpscaleModel]:
        return list(self.supported_models)

    def health_check(self) -> tuple[bool, str]:
        if self._health_cache is not None:
            return self._health_cache
        if not self.executable_path.exists():
            self._health_cache = False, f"找不到可执行文件：{ANIME4K_EXE}"
            return self._health_cache
        try:
            completed = subprocess.run(
                [str(self.executable_path), "-?"],
                cwd=ANIME4K_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
            )
        except OSError as exc:
            self._health_cache = False, f"Anime4K 无法启动：{exc}"
            return self._health_cache
        if "anime4k" not in (completed.stdout or "").lower():
            self._health_cache = False, "Anime4K 启动检查失败。"
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
