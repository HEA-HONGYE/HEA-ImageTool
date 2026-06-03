from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from image_toolbox.core.upscale_engines.types import EngineCommand, EngineError, EngineInfo, EngineOption, UpscaleConfig, UpscaleModel


class BaseUpscaleEngine(ABC):
    engine_id: str
    display_name: str
    description: str
    supported_models: list[UpscaleModel]
    supported_scales: list[int]
    supported_formats: list[str]
    supports_tile: bool = True
    supports_gpu_info: bool = True
    supports_progress_parse: bool = True
    supports_noise: bool = False
    supports_syncgap: bool = False

    @abstractmethod
    def validate_config(self, config: UpscaleConfig) -> None:
        raise NotImplementedError

    @abstractmethod
    def build_command(self, input_path: Path, output_path: Path, config: UpscaleConfig, engine_format: str) -> EngineCommand:
        raise NotImplementedError

    @abstractmethod
    def parse_progress(self, line: str) -> int | None:
        raise NotImplementedError

    @abstractmethod
    def parse_error(self, output: str, returncode: int | None) -> EngineError:
        raise NotImplementedError

    @abstractmethod
    def get_default_tile(self, low_memory: bool = False) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_model_info(self) -> list[UpscaleModel]:
        raise NotImplementedError

    @abstractmethod
    def get_info(self) -> EngineInfo:
        raise NotImplementedError

    def health_check(self) -> tuple[bool, str]:
        info = self.get_info()
        return info.available, info.unavailable_reason

    def get_noise_options(self) -> list[EngineOption]:
        return []

    def get_syncgap_options(self) -> list[EngineOption]:
        return []

    def scan_models(self) -> list[UpscaleModel]:
        return self.get_model_info()

    def get_model_path(self, model_id: str) -> Path | None:
        return None

    def recommendation(self) -> str:
        return self.description
