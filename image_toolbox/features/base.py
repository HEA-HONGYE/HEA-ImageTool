from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QWidget


class ToolFeature:
    key = ""
    title = ""
    description = ""

    def build_panel(self) -> QWidget:
        raise NotImplementedError

    def create_processor(self, files: list[Path]) -> Callable[[Path, Callable[[str], None]], Path]:
        raise NotImplementedError

    def get_output_dir(self) -> Path | None:
        return None
