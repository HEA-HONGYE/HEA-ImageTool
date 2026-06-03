from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths


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


class EngineSettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_settings_path()
        self.engines: dict[str, EngineSettings] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.engines = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.engines = {}
            return
        engines: dict[str, EngineSettings] = {}
        for engine_id, raw_engine in data.get("engines", {}).items():
            models = {
                model_id: ModelSettings(model_id=model_id, **{k: v for k, v in raw_model.items() if k != "model_id"})
                for model_id, raw_model in raw_engine.get("models", {}).items()
            }
            payload = {key: value for key, value in raw_engine.items() if key not in {"engine_id", "models"}}
            engines[engine_id] = EngineSettings(engine_id=engine_id, models=models, **payload)
        self.engines = engines

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "engines": {engine_id: asdict(settings) for engine_id, settings in self.engines.items()}}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_engine(self, engine_id: str) -> EngineSettings:
        if engine_id not in self.engines:
            self.engines[engine_id] = EngineSettings(engine_id=engine_id)
        return self.engines[engine_id]

    def update_engine(self, settings: EngineSettings) -> None:
        self.engines[settings.engine_id] = settings

    def get_model(self, engine_id: str, model_id: str) -> ModelSettings:
        engine = self.get_engine(engine_id)
        if model_id not in engine.models:
            engine.models[model_id] = ModelSettings(model_id=model_id)
        return engine.models[model_id]


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
    return Path(configured) if configured else default_path


def resolve_model_root(engine_id: str, default_path: Path) -> Path:
    configured = get_engine_settings_store().get_engine(engine_id).model_dir
    return Path(configured) if configured else default_path


def is_engine_enabled(engine_id: str) -> bool:
    return get_engine_settings_store().get_engine(engine_id).enabled


def is_model_enabled(engine_id: str, model_id: str) -> bool:
    engine = get_engine_settings_store().get_engine(engine_id)
    model = engine.models.get(model_id)
    return True if model is None else model.enabled
