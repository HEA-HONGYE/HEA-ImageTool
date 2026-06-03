from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths

from image_toolbox.core.paths import ensure_project_model_dirs, get_engine_models_dir, is_project_model_path, looks_like_external_asset_path


ENGINE_SETTINGS_ENV = "HEA_ENGINE_SETTINGS_PATH"


@dataclass
class ModelSettings:
    model_id: str
    display_name: str = ""
    path: str = ""
    enabled: bool = True
    is_default: bool = False
    recommended_use: str = ""
    quality_score: int = 3
    speed_score: int = 3
    memory_score: int = 3
    note: str = ""


@dataclass
class EngineSettings:
    engine_id: str
    enabled: bool = True
    executable_path: str = ""
    model_dir: str = ""
    default_model: str = ""
    default_scale: int = 0
    default_tile: int = 0
    low_memory_default: bool = False
    default_noise_level: int = 0
    default_output_format: str = "original"
    syncgap_mode: int = 2
    extra_params: dict[str, Any] = field(default_factory=dict)
    models: dict[str, ModelSettings] = field(default_factory=dict)


@dataclass
class GlobalEngineSettings:
    default_image_engine: str = "realesrgan"
    default_animated_engine: str = ""
    default_video_engine: str = ""
    image_threads: int = 4
    animated_threads: int = 8
    video_threads: int = 8
    gpu_id: str = "auto"
    multi_gpu_enabled: bool = False
    multi_gpu_id: str = "0"
    multi_gpu_tile: int = 128


class EngineSettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_settings_path()
        self.global_settings = GlobalEngineSettings()
        self.engines: dict[str, EngineSettings] = {}
        ensure_project_model_dirs()
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.engines = {}
            self._ensure_project_model_defaults()
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.engines = {}
            self._ensure_project_model_defaults()
            return
        global_raw = data.get("global", {})
        self.global_settings = GlobalEngineSettings(**{k: v for k, v in global_raw.items() if k in GlobalEngineSettings.__dataclass_fields__})
        engines: dict[str, EngineSettings] = {}
        for engine_id, raw_engine in data.get("engines", {}).items():
            models = {
                model_id: ModelSettings(model_id=model_id, **{k: v for k, v in raw_model.items() if k != "model_id"})
                for model_id, raw_model in raw_engine.get("models", {}).items()
            }
            payload = {key: value for key, value in raw_engine.items() if key not in {"engine_id", "models"}}
            engines[engine_id] = EngineSettings(engine_id=engine_id, models=models, **payload)
        self.engines = engines
        self._ensure_project_model_defaults()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 2,
            "global": asdict(self.global_settings),
            "engines": {engine_id: asdict(settings) for engine_id, settings in self.engines.items()},
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_engine(self, engine_id: str) -> EngineSettings:
        if engine_id not in self.engines:
            self.engines[engine_id] = EngineSettings(engine_id=engine_id)
        settings = self.engines[engine_id]
        if not settings.model_dir:
            settings.model_dir = str(get_engine_models_dir(engine_id))
        return self.engines[engine_id]

    def update_engine(self, settings: EngineSettings) -> None:
        self.engines[settings.engine_id] = settings

    def get_model(self, engine_id: str, model_id: str) -> ModelSettings:
        engine = self.get_engine(engine_id)
        if model_id not in engine.models:
            engine.models[model_id] = ModelSettings(model_id=model_id)
        return engine.models[model_id]

    def _ensure_project_model_defaults(self) -> None:
        for engine_id, settings in self.engines.items():
            default_dir = get_engine_models_dir(engine_id)
            if not settings.model_dir:
                settings.model_dir = str(default_dir)
                continue
            configured = Path(settings.model_dir)
            if looks_like_external_asset_path(configured) or not is_project_model_path(configured):
                settings.extra_params["legacy_model_dir"] = settings.model_dir
                settings.extra_params["needs_model_migration"] = True
                settings.model_dir = str(default_dir)


def default_settings_path() -> Path:
    env_path = os.environ.get(ENGINE_SETTINGS_ENV)
    if env_path:
        return Path(env_path)
    config_dir = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
    if config_dir:
        return Path(config_dir) / "engine_settings.json"
    return Path.home() / ".hea" / "engine_settings.json"


_STORE: EngineSettingsStore | None = None


def get_engine_settings_store() -> EngineSettingsStore:
    global _STORE
    if _STORE is None:
        _STORE = EngineSettingsStore()
    return _STORE


def reload_engine_settings_store(path: Path | None = None) -> EngineSettingsStore:
    global _STORE
    _STORE = EngineSettingsStore(path)
    return _STORE


def resolve_executable_path(engine_id: str, default_path: Path) -> Path:
    configured = get_engine_settings_store().get_engine(engine_id).executable_path
    if configured and not looks_like_external_asset_path(configured):
        return Path(configured)
    return default_path


def resolve_model_root(engine_id: str, default_path: Path | None = None) -> Path:
    configured = get_engine_settings_store().get_engine(engine_id).model_dir
    default_model_dir = get_engine_models_dir(engine_id)
    if configured:
        configured_path = Path(configured)
        if is_project_model_path(configured_path):
            return configured_path
    return default_model_dir


def is_engine_enabled(engine_id: str) -> bool:
    return get_engine_settings_store().get_engine(engine_id).enabled


def is_model_enabled(engine_id: str, model_id: str) -> bool:
    engine = get_engine_settings_store().get_engine(engine_id)
    model = engine.models.get(model_id)
    return True if model is None else model.enabled
