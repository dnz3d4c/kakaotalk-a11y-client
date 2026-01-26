# SPDX-License-Identifier: MIT
"""Updater 단위 테스트."""

from unittest.mock import patch, MagicMock
import urllib.error

import pytest

from kakaotalk_a11y_client.updater import check_for_update, UpdateInfo


# 테스트용 버전 상수
CURRENT_VERSION = "0.5.1"


@pytest.fixture
def mock_github_success():
    """새 버전 응답 Mock."""
    release = {
        "tag_name": "v0.6.0",
        "body": "## 변경사항\n- 새 기능 추가",
        "assets": [
            {
                "name": "KakaotalkA11y-v0.6.0-win64.zip",
                "browser_download_url": "https://github.com/dnz3d4c/kakaotalk-a11y-client/releases/download/v0.6.0/KakaotalkA11y-v0.6.0-win64.zip",
            }
        ],
    }
    with patch(
        "kakaotalk_a11y_client.updater.get_latest_release", return_value=release
    ):
        yield release


@pytest.fixture
def mock_github_latest():
    """현재 버전과 동일한 버전 응답 Mock."""
    release = {
        "tag_name": f"v{CURRENT_VERSION}",
        "body": "현재 버전",
        "assets": [
            {
                "name": f"KakaotalkA11y-v{CURRENT_VERSION}-win64.zip",
                "browser_download_url": f"https://github.com/dnz3d4c/kakaotalk-a11y-client/releases/download/v{CURRENT_VERSION}/KakaotalkA11y-v{CURRENT_VERSION}-win64.zip",
            }
        ],
    }
    with patch(
        "kakaotalk_a11y_client.updater.get_latest_release", return_value=release
    ):
        yield release


@pytest.fixture
def mock_github_network_error():
    """네트워크 오류 Mock."""
    with patch(
        "kakaotalk_a11y_client.updater.get_latest_release", return_value=None
    ):
        yield


@pytest.fixture
def mock_github_no_asset():
    """에셋 없는 릴리스 응답 Mock."""
    release = {
        "tag_name": "v0.6.0",
        "body": "에셋 없음",
        "assets": [
            {
                "name": "source.zip",  # 패턴 불일치
                "browser_download_url": "https://github.com/example/source.zip",
            }
        ],
    }
    with patch(
        "kakaotalk_a11y_client.updater.get_latest_release", return_value=release
    ):
        yield release


class TestCheckForUpdate:
    """check_for_update 함수 테스트."""

    def test_check_for_update_success(self, mock_github_success):
        """새 버전 발견 시 UpdateInfo 반환."""
        result = check_for_update()

        assert result is not None
        assert isinstance(result, UpdateInfo)
        assert result.version == "0.6.0"
        assert result.current_version == CURRENT_VERSION
        assert "KakaotalkA11y-v0.6.0-win64.zip" in result.download_url
        assert "새 기능" in result.release_notes

    def test_check_for_update_network_error(self, mock_github_network_error):
        """네트워크 오류 시 None 반환."""
        result = check_for_update()

        assert result is None

    def test_check_for_update_already_latest(self, mock_github_latest):
        """현재 버전과 동일하면 None 반환."""
        result = check_for_update()

        assert result is None

    def test_check_for_update_no_asset(self, mock_github_no_asset):
        """에셋 패턴 불일치 시 None 반환."""
        result = check_for_update()

        assert result is None
