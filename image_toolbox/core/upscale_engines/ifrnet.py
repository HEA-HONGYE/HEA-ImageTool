from __future__ import annotations

from pathlib import Path

from image_toolbox.core.model_library import (
    InterpolationModelInfo,
    build_ifrnet_command,
    list_interpolation_model_info,
    validate_interpolation_model_root,
)
from image_toolbox.core.tool_manager import get_tool_manager


class IFRNetEngine:
    engine_id = "ifrnet"
    display_name = "IFRNet"
    description = "适合视频帧插值，可用于 2x / 4x 视频插帧。"
    supported_scales = [2, 4]

    def health_check(self) -> tuple[bool, str]:
        try:
            get_tool_manager().require_tool("ifrnet")
            validate_interpolation_model_root("ifrnet")
        except Exception as exc:
            return False, str(exc)
        return True, ""

    def list_models(self) -> list[InterpolationModelInfo]:
        return list_interpolation_model_info("ifrnet")

    def build_command(
        self,
        executable_path: Path,
        input_frames: Path,
        output_frames: Path,
        scale: int = 2,
        model_name: str = "",
        gpu_id: str = "auto",
        use_tta: bool = False,
        target_frame_count: int | None = None,
        output_pattern: str = "%06d.png",
    ) -> list[str]:
        return build_ifrnet_command(
            executable_path,
            input_frames,
            output_frames,
            scale,
            model_name,
            gpu_id,
            use_tta,
            target_frame_count,
            output_pattern,
        )
