# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""GitHub 릴리스 기반 자동 업데이트."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .github_client import download_asset, find_asset_url, get_latest_release
from .installer import (
    apply_update,
    cleanup_temp,
    extract_update,
    get_download_path,
    get_install_dir,
)
from .version import is_newer, parse_version
from ..__about__ import __version__
from ..utils.debug import get_logger

log = get_logger("Updater")

# 업데이트 체크 간격 (초)
CHECK_INTERVAL = 4 * 60 * 60  # 4시간

__all__ = [
    "UpdateInfo",
    "check_for_update",
    "check_for_update_if_needed",
    "start_download",
    "apply_and_restart",
    "cleanup",
    "is_frozen",
    "CHECK_INTERVAL",
]


@dataclass
class UpdateInfo:

    version: str
    current_version: str
    release_notes: str
    download_url: str


def is_frozen() -> bool:
    return get_install_dir() is not None


def check_for_update() -> Optional[UpdateInfo]:
    """새 버전 있으면 UpdateInfo 반환."""
    release = get_latest_release()
    if not release:
        return None

    tag = release.get("tag_name", "")
    if not is_newer(tag, __version__):
        log.debug(f"already on latest version: {__version__}")
        return None

    download_url = find_asset_url(release)
    if not download_url:
        return None

    return UpdateInfo(
        version=tag.lstrip("v"),
        current_version=__version__,
        release_notes=release.get("body", "변경사항 없음"),
        download_url=download_url,
    )


def check_for_update_if_needed() -> Optional[UpdateInfo]:
    """4시간 간격으로 체크. 미충족 시 스킵."""
    import time

    from ..settings import get_settings

    settings = get_settings()
    last_check = settings.get_last_update_check()
    now = time.time()

    if (now - last_check) < CHECK_INTERVAL:
        elapsed_hours = (now - last_check) / 3600
        log.debug(f"check interval not met ({elapsed_hours:.1f}h < 4h), skipping")
        return None

    info = check_for_update()

    # 체크 시간 저장 (성공/실패 무관)
    settings.set_last_update_check(now)
    settings.save()

    return info


def start_download(
    update_info: UpdateInfo,
    progress_callback: Optional[Callable[[int, int], bool]] = None,
) -> Optional[Path]:
    """다운로드. 성공 시 zip 경로 반환."""
    dest = get_download_path()

    if download_asset(update_info.download_url, dest, progress_callback):
        return dest

    cleanup_temp()
    return None


def apply_and_restart(zip_path: Path) -> bool:
    """압축 해제 + 적용. 성공 시 프로그램 종료됨."""
    extracted = extract_update(zip_path)
    if not extracted:
        cleanup_temp()
        return False

    if apply_update(extracted):
        log.info("update applied, terminating program")
        return True

    cleanup_temp()
    return False


def cleanup() -> None:
    cleanup_temp()
