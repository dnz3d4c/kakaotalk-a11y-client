# SPDX-License-Identifier: MIT
"""Updater 단위 테스트."""

from unittest.mock import patch, MagicMock
import urllib.error

import pytest

from kakaotalk_a11y_client.updater import check_for_update, UpdateInfo
from kakaotalk_a11y_client.__about__ import __version__


# 실제 버전에서 동적으로 계산
CURRENT_VERSION = __version__
# 테스트용 새 버전 (현재 버전보다 높은 버전)
_major, _minor, _patch = map(int, CURRENT_VERSION.split("."))
NEWER_VERSION = f"{_major}.{_minor}.{_patch + 1}"


@pytest.fixture
def mock_github_success():
    """새 버전 응답 Mock."""
    release = {
        "tag_name": f"v{NEWER_VERSION}",
        "body": "## 변경사항\n- 새 기능 추가",
        "assets": [
            {
                "name": f"KakaotalkA11y-v{NEWER_VERSION}-win64.zip",
                "browser_download_url": f"https://github.com/dnz3d4c/kakaotalk-a11y-client/releases/download/v{NEWER_VERSION}/KakaotalkA11y-v{NEWER_VERSION}-win64.zip",
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
        "tag_name": f"v{NEWER_VERSION}",
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
        assert result.version == NEWER_VERSION
        assert result.current_version == CURRENT_VERSION
        assert f"KakaotalkA11y-v{NEWER_VERSION}-win64.zip" in result.download_url
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

    def test_check_for_update_with_older_version(self, mock_github_latest):
        """현재 버전을 낮춰서 업데이트 감지 테스트."""
        # 현재 버전을 0.1.0으로 낮춤 → 최신 릴리스가 더 높으면 업데이트 감지
        with patch(
            "kakaotalk_a11y_client.updater.__version__", "0.1.0"
        ):
            result = check_for_update()
            # mock_github_latest는 현재 버전과 동일하므로 0.1.0 < 현재버전 → 업데이트 있음
            assert result is not None
            assert result.current_version == "0.1.0"


class TestInstaller:
    """installer 모듈 테스트."""

    def test_extract_update_valid_zip(self, tmp_path):
        """정상 zip 파일 압축 해제."""
        from kakaotalk_a11y_client.updater.installer import extract_update, EXTRACT_DIR
        import shutil

        # 테스트용 zip 생성
        zip_content_dir = tmp_path / "content" / "KakaotalkA11y"
        zip_content_dir.mkdir(parents=True)
        (zip_content_dir / "KakaotalkA11y.exe").write_text("fake exe")
        (zip_content_dir / "readme.txt").write_text("readme")

        zip_path = tmp_path / "update.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", tmp_path / "content")

        # 테스트 후 정리를 위해 기존 EXTRACT_DIR 백업
        try:
            result = extract_update(zip_path)
            assert result is not None
            assert (result / "KakaotalkA11y.exe").exists()
        finally:
            if EXTRACT_DIR.exists():
                shutil.rmtree(EXTRACT_DIR)

    def test_extract_update_corrupted_zip(self, tmp_path):
        """손상된 zip 파일."""
        from kakaotalk_a11y_client.updater.installer import extract_update

        bad_zip = tmp_path / "bad.zip"
        bad_zip.write_text("this is not a zip file")

        result = extract_update(bad_zip)
        assert result is None

    def test_extract_update_no_exe(self, tmp_path):
        """exe 없는 zip."""
        from kakaotalk_a11y_client.updater.installer import extract_update, EXTRACT_DIR
        import shutil

        # exe 없는 zip 생성
        zip_content_dir = tmp_path / "content"
        zip_content_dir.mkdir()
        (zip_content_dir / "readme.txt").write_text("no exe here")

        zip_path = tmp_path / "no_exe.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", zip_content_dir)

        try:
            result = extract_update(zip_path)
            assert result is None
        finally:
            if EXTRACT_DIR.exists():
                shutil.rmtree(EXTRACT_DIR)

    def test_apply_update_not_frozen(self, tmp_path):
        """개발 환경(not frozen)에서는 업데이트 적용 불가."""
        from kakaotalk_a11y_client.updater.installer import apply_update

        result = apply_update(tmp_path)
        assert result is False

    def test_get_install_dir_not_frozen(self):
        """개발 환경에서 install_dir은 None."""
        from kakaotalk_a11y_client.updater.installer import get_install_dir

        result = get_install_dir()
        assert result is None

    def test_generate_batch_script(self):
        """batch 스크립트 생성 테스트."""
        from kakaotalk_a11y_client.updater.installer import generate_batch_script
        from pathlib import Path

        script = generate_batch_script(
            source_dir=Path("C:/temp/source"),
            install_dir=Path("C:/app"),
            pid=12345,
        )

        assert "12345" in script  # PID
        assert "C:/temp/source" in script or "C:\\temp\\source" in script
        assert "C:/app" in script or "C:\\app" in script
        assert "robocopy" in script  # xcopy 대신 robocopy 사용
        assert "KakaotalkA11y.exe" in script
        # 로그 기능 검증
        assert "LOGFILE" in script
        assert ":log" in script  # 로그 함수
        assert "update_log.txt" in script
        assert "1단계" in script or "1\\xeb\\x8b\\xa8\\xea\\xb3\\x84" in script  # 단계별 로깅
        assert "ERROR" in script  # 에러 로깅
        assert "ROBO_EXIT" in script  # robocopy 종료 코드 체크


class TestDownloadAndApply:
    """다운로드 및 적용 통합 테스트."""

    def test_start_download_success(self, tmp_path):
        """다운로드 성공 테스트."""
        from kakaotalk_a11y_client.updater import start_download, UpdateInfo
        from kakaotalk_a11y_client.updater.installer import TEMP_DIR
        import shutil

        update_info = UpdateInfo(
            version="99.0.0",
            current_version=CURRENT_VERSION,
            release_notes="테스트",
            download_url="https://example.com/update.zip",
        )

        # download_asset mock - 실제 다운로드 대신 파일 생성
        def mock_download(url, dest, callback=None):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"fake zip content")
            return True

        with patch(
            "kakaotalk_a11y_client.updater.download_asset", side_effect=mock_download
        ):
            result = start_download(update_info)
            assert result is not None
            assert result.exists()

        # 정리
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)

    def test_start_download_failure(self):
        """다운로드 실패 테스트."""
        from kakaotalk_a11y_client.updater import start_download, UpdateInfo

        update_info = UpdateInfo(
            version="99.0.0",
            current_version=CURRENT_VERSION,
            release_notes="테스트",
            download_url="https://example.com/update.zip",
        )

        with patch(
            "kakaotalk_a11y_client.updater.download_asset", return_value=False
        ):
            result = start_download(update_info)
            assert result is None

    def test_apply_and_restart_extract_fail(self, tmp_path):
        """압축 해제 실패 시 False 반환."""
        from kakaotalk_a11y_client.updater import apply_and_restart

        bad_zip = tmp_path / "bad.zip"
        bad_zip.write_text("not a zip")

        result = apply_and_restart(bad_zip)
        assert result is False
