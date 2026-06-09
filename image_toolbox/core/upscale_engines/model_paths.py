from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path


MODEL_FILE_SUFFIXES = {".bin", ".param", ".json", ".txt"}


def _model_files(source_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in MODEL_FILE_SUFFIXES
    )


def _signature(source_dir: Path) -> str:
    files = _model_files(source_dir)
    size = sum(path.stat().st_size for path in files)
    latest_mtime = max((path.stat().st_mtime_ns for path in files), default=0)
    return f"{source_dir.resolve()}\n{len(files)}\n{size}\n{latest_mtime}"


def ensure_named_model_dir(source_dir: Path, required_name: str, engine_id: str) -> Path:
    source_dir = source_dir.resolve()
    if source_dir.name == required_name:
        return source_dir

    source_hash = hashlib.sha1(str(source_dir).encode("utf-8")).hexdigest()[:16]
    target_dir = Path(tempfile.gettempdir()) / "hea_image_tool_models" / engine_id / source_hash / required_name
    stamp_file = target_dir / ".hea_model_source"
    signature = _signature(source_dir)
    if stamp_file.exists() and stamp_file.read_text(encoding="utf-8", errors="ignore") == signature and _model_files(target_dir):
        return target_dir

    target_dir.mkdir(parents=True, exist_ok=True)
    for source_file in _model_files(source_dir):
        relative_path = source_file.relative_to(source_dir)
        target_file = target_dir / relative_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        if target_file.exists() and target_file.stat().st_size == source_file.stat().st_size:
            continue
        try:
            if target_file.exists():
                target_file.unlink()
            os.link(source_file, target_file)
        except OSError:
            shutil.copy2(source_file, target_file)

    stamp_file.write_text(signature, encoding="utf-8")
    return target_dir
