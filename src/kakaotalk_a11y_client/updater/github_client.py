# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""GitHub API 클라이언트. 릴리스 조회 및 에셋 다운로드."""

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
    """최신 릴리스 정보 조회. 실패 시 None."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "KakaotalkA11y-Updater",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
            log.debug(f"latest release: {data.get('tag_name')}")
            return data
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log.warning("no releases found")
        elif e.code == 403:
            log.warning("API rate limit exceeded")
        else:
            log.warning(f"API error: {e.code}")
        return None
    except urllib.error.URLError as e:
        log.warning(f"network error: {e.reason}")
        return None
    except Exception as e:
        log.error(f"release fetch failed: {e}")
        return None


def find_asset_url(release: dict) -> Optional[str]:
    """KakaotalkA11y-vX.Y.Z-win64.zip 패턴 매칭."""
    assets = release.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        if ASSET_PATTERN.match(name):
            url = asset.get("browser_download_url")
            log.debug(f"asset found: {name}")
            return url

    log.warning("no matching asset found")
    return None


def download_asset(
    url: str,
    dest: Path,
    progress_callback: Optional[Callable[[int, int], bool]] = None,
) -> bool:
    """에셋 다운로드. progress_callback이 False 반환하면 취소."""
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
                            log.info("download cancelled")
                            return False

            log.info(f"download completed: {dest}")
            return True

    except urllib.error.URLError as e:
        log.error(f"download failed: {e.reason}")
        return False
    except Exception as e:
        log.error(f"download error: {e}")
        return False
