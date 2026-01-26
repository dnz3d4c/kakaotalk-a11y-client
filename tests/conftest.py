# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""pytest 공용 fixtures."""

import pytest

# 현재 버전 (테스트에서 비교용)
CURRENT_VERSION = "0.5.1"


# =============================================================================
# wx 모킹 fixtures
# =============================================================================


@pytest.fixture
def mock_wx_app():
    """wx.App 생성 - GUI 테스트에 필요."""
    import wx

    app = wx.App(redirect=False)
    yield app
    app.Destroy()


@pytest.fixture
def mock_message_box(mocker):
    """wx.MessageBox 모킹 - 호출 여부 검증용."""
    import wx

    mock = mocker.patch("wx.MessageBox", return_value=wx.OK)
    return mock


@pytest.fixture
def mock_busy_cursor(mocker):
    """wx.BeginBusyCursor, wx.EndBusyCursor 모킹."""
    begin = mocker.patch("wx.BeginBusyCursor")
    end = mocker.patch("wx.EndBusyCursor")
    return {"begin": begin, "end": end}


# =============================================================================
# GitHub API 모킹 fixtures
# =============================================================================


@pytest.fixture
def mock_github_success(mocker):
    """성공 응답 모킹 - 새 버전 있음 (v0.6.0)."""
    release_data = {
        "tag_name": "v0.6.0",
        "body": "## 변경사항\n- 새로운 기능 추가\n- 버그 수정",
        "assets": [
            {
                "name": "KakaotalkA11y-v0.6.0-win64.zip",
                "browser_download_url": "https://github.com/dnz3d4c/kakaotalk-a11y-client/releases/download/v0.6.0/KakaotalkA11y-v0.6.0-win64.zip",
            }
        ],
    }
    mock = mocker.patch(
        "kakaotalk_a11y_client.updater.github_client.get_latest_release",
        return_value=release_data,
    )
    return {"mock": mock, "data": release_data}


@pytest.fixture
def mock_github_latest(mocker):
    """성공 응답 모킹 - 이미 최신 버전 (v0.5.1)."""
    release_data = {
        "tag_name": f"v{CURRENT_VERSION}",
        "body": "현재 버전",
        "assets": [
            {
                "name": f"KakaotalkA11y-v{CURRENT_VERSION}-win64.zip",
                "browser_download_url": f"https://github.com/dnz3d4c/kakaotalk-a11y-client/releases/download/v{CURRENT_VERSION}/KakaotalkA11y-v{CURRENT_VERSION}-win64.zip",
            }
        ],
    }
    mock = mocker.patch(
        "kakaotalk_a11y_client.updater.github_client.get_latest_release",
        return_value=release_data,
    )
    return {"mock": mock, "data": release_data}


@pytest.fixture
def mock_github_network_error(mocker):
    """네트워크 오류 모킹 - get_latest_release가 None 반환."""
    mock = mocker.patch(
        "kakaotalk_a11y_client.updater.github_client.get_latest_release",
        return_value=None,
    )
    return mock


@pytest.fixture
def mock_github_no_asset(mocker):
    """에셋 없음 모킹 - assets 배열이 비어있거나 패턴 불일치."""
    release_data = {
        "tag_name": "v0.6.0",
        "body": "에셋 없는 릴리스",
        "assets": [],  # 에셋 없음
    }
    mock = mocker.patch(
        "kakaotalk_a11y_client.updater.github_client.get_latest_release",
        return_value=release_data,
    )
    return {"mock": mock, "data": release_data}


@pytest.fixture
def mock_github_wrong_asset_pattern(mocker):
    """에셋 패턴 불일치 모킹 - 에셋은 있지만 패턴이 안 맞음."""
    release_data = {
        "tag_name": "v0.6.0",
        "body": "잘못된 에셋명",
        "assets": [
            {
                "name": "wrong-asset-name.zip",  # 패턴 불일치
                "browser_download_url": "https://example.com/wrong.zip",
            }
        ],
    }
    mock = mocker.patch(
        "kakaotalk_a11y_client.updater.github_client.get_latest_release",
        return_value=release_data,
    )
    return {"mock": mock, "data": release_data}


# =============================================================================
# UpdateInfo 모킹 fixtures
# =============================================================================


@pytest.fixture
def mock_update_info():
    """테스트용 UpdateInfo 객체."""
    from kakaotalk_a11y_client.updater import UpdateInfo

    return UpdateInfo(
        version="0.6.0",
        current_version=CURRENT_VERSION,
        release_notes="## 변경사항\n- 새 기능 추가",
        download_url="https://github.com/dnz3d4c/kakaotalk-a11y-client/releases/download/v0.6.0/KakaotalkA11y-v0.6.0-win64.zip",
    )


@pytest.fixture
def mock_tray_icon(mocker):
    """TrayIcon 모킹 - MainFrame 생성 시 필요."""
    return mocker.patch("kakaotalk_a11y_client.gui.tray_icon.TrayIcon")
