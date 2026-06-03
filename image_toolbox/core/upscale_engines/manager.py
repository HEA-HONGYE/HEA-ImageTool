from __future__ import annotations

from image_toolbox.core.upscale_engines.base import BaseUpscaleEngine
from image_toolbox.core.upscale_engines.realesrgan import RealEsrganEngine
from image_toolbox.core.upscale_engines.types import EngineInfo
from image_toolbox.core.upscale_engines.waifu2x import Waifu2xEngine


class EngineManager:
    def __init__(self) -> None:
        self._engines: dict[str, BaseUpscaleEngine] = {}

    def register(self, engine: BaseUpscaleEngine) -> None:
        self._engines[engine.engine_id] = engine

    def get_engine(self, engine_id: str) -> BaseUpscaleEngine:
        if engine_id not in self._engines:
            raise KeyError(f"未注册的超分引擎：{engine_id}")
        return self._engines[engine_id]

    def list_engines(self) -> list[BaseUpscaleEngine]:
        return list(self._engines.values())

    def list_engine_info(self) -> list[EngineInfo]:
        return [engine.get_info() for engine in self.list_engines()]

    def is_available(self, engine_id: str) -> bool:
        return self.get_engine(engine_id).get_info().available


def create_default_engine_manager() -> EngineManager:
    manager = EngineManager()
    manager.register(RealEsrganEngine())
    manager.register(Waifu2xEngine())
    return manager


DEFAULT_ENGINE_MANAGER = create_default_engine_manager()
