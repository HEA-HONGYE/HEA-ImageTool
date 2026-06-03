from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSettings

from image_toolbox import APP_NAME


class AppConfig:
    def __init__(self, namespace: str) -> None:
        self.settings = QSettings("HEA", APP_NAME)
        self.namespace = namespace

    def get(self, key: str, default: Any = None, value_type: type | None = None) -> Any:
        full_key = f"{self.namespace}/{key}"
        if value_type is None:
            return self.settings.value(full_key, default)
        return self.settings.value(full_key, default, type=value_type)

    def set(self, key: str, value: Any) -> None:
        self.settings.setValue(f"{self.namespace}/{key}", value)
