from __future__ import annotations

import hashlib
import json
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from image_toolbox import APP_NAME, APP_VERSION


DEFAULT_UPDATE_MANIFEST_URLS = (
    "https://gitee.com/red-night-hea/hea-image-tool/raw/main/versions.json",
    "https://raw.githubusercontent.com/HEA-HONGYE/HEA-ImageTool/main/versions.json",
)
DEFAULT_UPDATE_MANIFEST_URL = DEFAULT_UPDATE_MANIFEST_URLS[0]
DEFAULT_RELEASE_URL = "https://github.com/HEA-HONGYE/HEA-ImageTool/releases/latest"


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    has_update: bool
    manifest_url: str
    release_url: str
    download_url: str
    download_urls: tuple[str, ...]
    title: str
    notes: str
    sha256: str
    mandatory: bool = False


class UpdateCheckSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class UpdateDownloadSignals(QObject):
    progress = Signal(int)
    finished = Signal(object)
    failed = Signal(str)


def normalize_version(version: str) -> tuple[int, ...]:
    text = str(version).strip().lstrip("vV")
    numbers = [int(item) for item in re.findall(r"\d+", text)]
    return tuple(numbers or [0])


def is_newer_version(latest: str, current: str) -> bool:
    latest_parts = list(normalize_version(latest))
    current_parts = list(normalize_version(current))
    max_length = max(len(latest_parts), len(current_parts))
    latest_parts.extend([0] * (max_length - len(latest_parts)))
    current_parts.extend([0] * (max_length - len(current_parts)))
    return latest_parts > current_parts


def get_default_download_dir() -> Path:
    return Path(tempfile.gettempdir()) / APP_NAME / "updates"


def parse_url_list(value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value]
    else:
        text = str(value or "")
        items = [item.strip() for item in re.split(r"[\s;]+", text)]
    return [item for item in items if item]


def fetch_update_info(manifest_url: str, current_version: str = APP_VERSION, timeout: int = 12) -> UpdateInfo:
    request = urllib.request.Request(
        manifest_url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"{APP_NAME}/{current_version}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8-sig")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接更新服务器：{exc}") from exc

    try:
        manifest = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"更新清单格式错误：{exc}") from exc

    latest_version = str(manifest.get("version", "")).strip()
    if not latest_version:
        raise RuntimeError("更新清单缺少 version 字段。")

    release_url = str(manifest.get("release_url") or manifest.get("url") or DEFAULT_RELEASE_URL).strip()
    download_urls = parse_url_list(manifest.get("download_urls") or manifest.get("mirrors"))
    download_urls.extend(parse_url_list(manifest.get("download_url") or manifest.get("installer_url")))
    download_urls = list(dict.fromkeys(download_urls))
    download_url = download_urls[0] if download_urls else ""
    title = str(manifest.get("title") or f"{APP_NAME} v{latest_version}").strip()
    notes = str(manifest.get("notes") or manifest.get("release_notes") or "").strip()
    sha256 = str(manifest.get("sha256") or "").strip().lower()
    mandatory = bool(manifest.get("mandatory", False))

    return UpdateInfo(
        current_version=current_version,
        latest_version=latest_version,
        has_update=is_newer_version(latest_version, current_version),
        manifest_url=manifest_url,
        release_url=release_url,
        download_url=download_url,
        download_urls=tuple(download_urls),
        title=title,
        notes=notes,
        sha256=sha256,
        mandatory=mandatory,
    )


def fetch_update_info_from_sources(manifest_urls: str | list[str] | tuple[str, ...], current_version: str = APP_VERSION) -> UpdateInfo:
    urls = parse_url_list(manifest_urls)
    if not urls:
        urls = list(DEFAULT_UPDATE_MANIFEST_URLS)

    errors: list[str] = []
    for url in urls:
        try:
            return fetch_update_info(url, current_version)
        except Exception as exc:
            errors.append(f"{url}：{exc}")
    raise RuntimeError("所有更新源都连接失败。\n" + "\n".join(errors))


class UpdateCheckTask(QRunnable):
    def __init__(self, manifest_url: str | list[str] | tuple[str, ...], current_version: str = APP_VERSION) -> None:
        super().__init__()
        self.manifest_url = manifest_url
        self.current_version = current_version
        self.signals = UpdateCheckSignals()

    @Slot()
    def run(self) -> None:
        try:
            info = fetch_update_info_from_sources(self.manifest_url, self.current_version)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(info)


class UpdateDownloadTask(QRunnable):
    def __init__(self, info: UpdateInfo, target_dir: Path | None = None) -> None:
        super().__init__()
        self.info = info
        self.target_dir = target_dir or get_default_download_dir()
        self.signals = UpdateDownloadSignals()

    @Slot()
    def run(self) -> None:
        download_urls = list(self.info.download_urls or parse_url_list(self.info.download_url))
        if not download_urls:
            self.signals.failed.emit("更新清单没有提供下载地址。")
            return

        self.target_dir.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []
        for download_url in download_urls:
            filename = Path(urllib.parse.urlparse(download_url).path).name
            if not filename or "." not in filename:
                filename = f"{APP_NAME}-{self.info.latest_version}-Setup.exe"
            target_path = self.target_dir / filename
            temp_path = target_path.with_suffix(target_path.suffix + ".download")

            request = urllib.request.Request(
                download_url,
                headers={"User-Agent": f"{APP_NAME}/{self.info.current_version}"},
            )
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    total = int(response.headers.get("Content-Length") or 0)
                    downloaded = 0
                    digest = hashlib.sha256()
                    with temp_path.open("wb") as file:
                        while True:
                            chunk = response.read(1024 * 256)
                            if not chunk:
                                break
                            file.write(chunk)
                            digest.update(chunk)
                            downloaded += len(chunk)
                            if total:
                                self.signals.progress.emit(min(100, int(downloaded / total * 100)))
                    actual_sha256 = digest.hexdigest()
            except Exception as exc:
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                errors.append(f"{download_url}：{exc}")
                continue

            if self.info.sha256 and self.info.sha256 != actual_sha256:
                temp_path.unlink(missing_ok=True)
                errors.append(f"{download_url}：更新包校验失败")
                continue

            temp_path.replace(target_path)
            self.signals.progress.emit(100)
            self.signals.finished.emit(target_path)
            return

        self.signals.failed.emit("所有更新包下载地址都失败。\n" + "\n".join(errors))
