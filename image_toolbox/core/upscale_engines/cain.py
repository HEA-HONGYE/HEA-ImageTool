from __future__ import annotations

from pathlib import Path

from image_toolbox.core.model_library import (
    InterpolationModelInfo,
    build_cain_command,
    list_interpolation_model_info,
    validate_interpolation_model_root,
)
from image_toolbox.core.tool_manager import get_tool_manager


class CAINEngine:
    engine_id = "cain"
    display_name = "CAIN"
    description = "视频帧插值引擎，适合 2x 插帧；4x 通过连续两次 2x 插帧完成。"
    supported_scales = [2, 4]

    def health_check(self) -> tuple[bool, str]:
        try:
            get_tool_manager().require_tool("cain")
            validate_interpolation_model_root("cain")
        except Exception as exc:
            return False, str(exc)
        return True, ""

    def list_models(self) -> list[InterpolationModelInfo]:
        return list_interpolation_model_info("cain")

    def build_command(
        self,
        executable_path: Path,
        input_frames: Path,
        output_frames: Path,
        model_name: str = "cain",
        gpu_id: str = "auto",
        output_pattern: str = "%06d.png",
    ) -> list[str]:
        return build_cain_command(executable_path, input_frames, output_frames, model_name, gpu_id, output_pattern)
