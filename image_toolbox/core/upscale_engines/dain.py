from __future__ import annotations

from pathlib import Path

from image_toolbox.core.model_library import (
    InterpolationModelInfo,
    build_dain_command,
    list_interpolation_model_info,
    validate_interpolation_model_root,
)
from image_toolbox.core.tool_manager import get_tool_manager


class DAINEngine:
    engine_id = "dain"
    display_name = "DAIN"
    description = "视频帧插值引擎，支持 2x / 4x 插帧。"
    supported_scales = [2, 4]

    def health_check(self) -> tuple[bool, str]:
        try:
            get_tool_manager().require_tool("dain")
            validate_interpolation_model_root("dain")
        except Exception as exc:
            return False, str(exc)
        return True, ""

    def list_models(self) -> list[InterpolationModelInfo]:
        return list_interpolation_model_info("dain")

    def build_command(
        self,
        executable_path: Path,
        input_frames: Path,
        output_frames: Path,
        scale: int = 2,
        model_name: str = "best",
        gpu_id: str = "auto",
        target_frame_count: int | None = None,
        output_pattern: str = "%06d.png",
    ) -> list[str]:
        return build_dain_command(
            executable_path,
            input_frames,
            output_frames,
            scale,
            model_name,
            gpu_id,
            target_frame_count,
            output_pattern,
        )
