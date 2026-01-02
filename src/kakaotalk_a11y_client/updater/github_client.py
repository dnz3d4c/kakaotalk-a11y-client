# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""GitHub API 클라이언트"""

import json
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Optional

from ..utils.debug import get_logger

log = get_logger("GitHubClient")

REPO_OWNER = "dnz3d4c"
REPO_NAME = "kakaotalk-a11y-client"
ASSET_PATTERN = re.compile(r"KakaotalkA11y-v[\d.]+-win64\.zip")
API_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 60


def get_latest_release() -> Optional[dict]:
    """GitHub에서 최신 릴리스 정보 조회.

    Returns:
        릴리스 정보 dict (tag_name, body, assets 등) 또는 None
    """
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "KakaotalkA11y-Updater",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
            log.debug(f"최신 릴리스: {data.get('tag_name')}")
            return data
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log.warning("릴리스 없음")
        elif e.code == 403:
            log.warning("API rate limit 초과")
        else:
            log.warning(f"API 오류: {e.code}")
        return None
    except urllib.error.URLError as e:
        log.warning(f"네트워크 오류: {e.reason}")
        return None
    except Exception as e:
        log.error(f"릴리스 조회 실패: {e}")
        return None


def find_asset_url(release: dict) -> Optional[str]:
    """릴리스에서 다운로드할 에셋 URL 찾기.

    Args:
        release: 릴리스 정보 dict

    Returns:
        다운로드 URL 또는 None
    """
    assets = release.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        if ASSET_PATTERN.match(name):
            url = asset.get("browser_download_url")
            log.debug(f"에셋 발견: {name}")
            return url

    log.warning("적합한 에셋 없음")
    return None


def download_asset(
    url: str,
    dest: Path,
    progress_callback: Optional[Callable[[int, int], bool]] = None,
) -> bool:
    """에셋 다운로드.

    Args:
        url: 다운로드 URL
        dest: 저장 경로
        progress_callback: 진행률 콜백 (downloaded, total) -> continue?

    Returns:
        성공 여부
    """
    headers = {"User-Agent": "KakaotalkA11y-Updater"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 8192

            dest.parent.mkdir(parents=True, exist_ok=True)

            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback:
                        if not progress_callback(downloaded, total):
                            log.info("다운로드 취소됨")
                            return False

            log.info(f"다운로드 완료: {dest}")
            return True

    except urllib.error.URLError as e:
        log.error(f"다운로드 실패: {e.reason}")
        return False
    except Exception as e:
        log.error(f"다운로드 오류: {e}")
        return False
