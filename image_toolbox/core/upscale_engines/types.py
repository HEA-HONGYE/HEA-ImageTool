from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


ENGINE_NOT_FOUND = "ENGINE_NOT_FOUND"
MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
INVALID_CONFIG = "INVALID_CONFIG"
INPUT_NOT_FOUND = "INPUT_NOT_FOUND"
OUTPUT_ERROR = "OUTPUT_ERROR"
PROCESS_FAILED = "PROCESS_FAILED"
GPU_MEMORY_ERROR = "GPU_MEMORY_ERROR"
CANCELLED = "CANCELLED"
UNKNOWN_ERROR = "UNKNOWN_ERROR"


@dataclass(frozen=True)
class UpscaleModel:
    name: str
    display_name: str
    description: str = ""


@dataclass(frozen=True)
class UpscaleConfig:
    engine_id: str
    model_name: str
    scale: int
    output_format: str
    keep_original_format: bool
    quality: int
    tile_mode: str
    tile_size: int
    low_memory_mode: bool
    conflict_strategy: str
    output_dir: Path
    gpu_id: str = "auto"
    threads: str = "1:2:2"
    use_tta: bool = False


@dataclass
class UpscaleTask:
    input_path: Path
    output_path: Path | None
    config: UpscaleConfig
    retry_count: int = 0
    status: str = "pending"


@dataclass
class UpscaleResult:
    input_path: Path
    output_path: Path | None = None
    success: bool = False
    skipped: bool = False
    cancelled: bool = False
    error_type: str = ""
    error_message: str = ""
    duration: float = 0.0


@dataclass(frozen=True)
class EngineInfo:
    engine_id: str
    display_name: str
    description: str
    available: bool
    executable_path: Path | None
    models: list[UpscaleModel]
    supported_scales: list[int]
    supported_formats: list[str]
    unavailable_reason: str = ""


@dataclass(frozen=True)
class UpscalePreset:
    preset_id: str
    display_name: str
    description: str
    engine_id: str
    model_name: str
    scale: int
    low_memory_mode: bool = False
    output_format: str = "original"
    tile_mode: str = "auto"
    tile_size: int = 0


@dataclass(frozen=True)
class EngineCommand:
    command: list[str]
    cwd: Path
    engine_format: str


@dataclass(frozen=True)
class EngineError:
    error_type: str
    user_message: str
    debug_message: str = ""
