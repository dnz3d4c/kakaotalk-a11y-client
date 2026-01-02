# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""업데이터 패키지

GitHub 릴리스 기반 자동 업데이트 기능 제공.
"""

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

__all__ = [
    "UpdateInfo",
    "check_for_update",
    "start_download",
    "apply_and_restart",
    "cleanup",
    "is_frozen",
]


@dataclass
class UpdateInfo:
    """업데이트 정보"""

    version: str
    current_version: str
    release_notes: str
    download_url: str


def is_frozen() -> bool:
    """PyInstaller로 빌드된 환경인지 확인."""
    return get_install_dir() is not None


def check_for_update() -> Optional[UpdateInfo]:
    """업데이트 확인.

    Returns:
        새 버전이 있으면 UpdateInfo, 없으면 None
    """
    release = get_latest_release()
    if not release:
        return None

    tag = release.get("tag_name", "")
    if not is_newer(tag, __version__):
        log.debug(f"최신 버전 사용 중: {__version__}")
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


def start_download(
    update_info: UpdateInfo,
    progress_callback: Optional[Callable[[int, int], bool]] = None,
) -> Optional[Path]:
    """업데이트 다운로드.

    Args:
        update_info: 업데이트 정보
        progress_callback: 진행률 콜백 (downloaded, total) -> continue?

    Returns:
        다운로드된 zip 경로 또는 None
    """
    dest = get_download_path()

    if download_asset(update_info.download_url, dest, progress_callback):
        return dest

    cleanup_temp()
    return None


def apply_and_restart(zip_path: Path) -> bool:
    """업데이트 적용 및 재시작.

    Args:
        zip_path: 다운로드된 zip 파일 경로

    Returns:
        성공 여부 (성공 시 프로그램 종료됨)
    """
    extracted = extract_update(zip_path)
    if not extracted:
        cleanup_temp()
        return False

    if apply_update(extracted):
        log.info("업데이트 적용됨, 프로그램 종료")
        return True

    cleanup_temp()
    return False


def cleanup() -> None:
    """업데이트 취소/실패 시 정리."""
    cleanup_temp()
