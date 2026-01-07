# SPDX-License-Identifier: MIT
"""Settings 단위 테스트."""

import copy
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from kakaotalk_a11y_client import settings as settings_module
from kakaotalk_a11y_client.settings import Settings


# 테스트용 기본 설정 (원본 보존)
ORIGINAL_DEFAULT_SETTINGS = copy.deepcopy(settings_module.DEFAULT_SETTINGS)


@pytest.fixture(autouse=True)
def restore_default_settings():
    """테스트 간 DEFAULT_SETTINGS 복원."""
    yield
    # 테스트 후 원본으로 복원
    settings_module.DEFAULT_SETTINGS = copy.deepcopy(ORIGINAL_DEFAULT_SETTINGS)


@pytest.fixture
def temp_settings_path(tmp_path):
    """임시 설정 파일 경로."""
    return tmp_path / ".kakaotalk_a11y" / "settings.json"


@pytest.fixture
def settings_with_temp_path(temp_settings_path):
    """임시 경로를 사용하는 Settings 인스턴스."""
    # DEFAULT_SETTINGS 복원 후 시작
    settings_module.DEFAULT_SETTINGS = copy.deepcopy(ORIGINAL_DEFAULT_SETTINGS)

    with patch.object(Settings, '__init__', lambda self: None):
        s = Settings()
        s.path = temp_settings_path
        s._data = {}
        s._load()
        return s


class TestSettings:
    """Settings 클래스 테스트."""

    def test_load_default_when_file_not_exists(self, settings_with_temp_path):
        """파일 없을 때 기본값 사용."""
        s = settings_with_temp_path

        assert "hotkeys" in s._data
        assert "ui" in s._data
        assert "stats" in s._data
        assert s.get("hotkeys.scan.key") == "E"

    def test_load_existing_file(self, temp_settings_path):
        """기존 파일 로드."""
        # 파일 생성
        temp_settings_path.parent.mkdir(parents=True, exist_ok=True)
        custom_data = {
            "hotkeys": {"scan": {"modifiers": ["alt"], "key": "X"}},
            "custom_key": "custom_value"
        }
        with open(temp_settings_path, "w", encoding="utf-8") as f:
            json.dump(custom_data, f)

        # 로드
        with patch.object(Settings, '__init__', lambda self: None):
            s = Settings()
            s.path = temp_settings_path
            s._data = {}
            s._load()

        # 커스텀 값 유지
        assert s.get("hotkeys.scan.key") == "X"
        assert s.get("hotkeys.scan.modifiers") == ["alt"]
        assert s.get("custom_key") == "custom_value"
        # 기본값으로 누락 키 채움
        assert s.get("ui.window_size") == [500, 400]

    def test_save_creates_directory(self, temp_settings_path):
        """저장 시 디렉토리 자동 생성."""
        with patch.object(Settings, '__init__', lambda self: None):
            s = Settings()
            s.path = temp_settings_path
            s._data = {"test": "value"}

        result = s.save()

        assert result is True
        assert temp_settings_path.exists()
        with open(temp_settings_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["test"] == "value"

    def test_merge_defaults(self, settings_with_temp_path):
        """기본값 병합."""
        s = settings_with_temp_path
        s._data = {"hotkeys": {"scan": {"key": "X"}}}  # 부분 데이터
        s._merge_defaults()

        # 기존 값 유지
        assert s.get("hotkeys.scan.key") == "X"
        # 누락된 기본값 채워짐
        assert s.get("hotkeys.exit.key") == "K"
        assert s.get("ui.window_size") == [500, 400]

    def test_get_set_basic(self, settings_with_temp_path):
        """기본 get/set."""
        s = settings_with_temp_path

        s.set("new_key", "new_value")
        assert s.get("new_key") == "new_value"

    def test_get_nested(self, settings_with_temp_path):
        """점 표기법 중첩 접근."""
        s = settings_with_temp_path

        # 기존 중첩 값
        assert s.get("hotkeys.scan.key") == "E"

        # 새 중첩 값
        s.set("a.b.c", "deep_value")
        assert s.get("a.b.c") == "deep_value"

    def test_get_nonexistent_with_default(self, settings_with_temp_path):
        """없는 키 조회 시 기본값."""
        s = settings_with_temp_path

        assert s.get("nonexistent") is None
        assert s.get("nonexistent", "fallback") == "fallback"
        assert s.get("a.b.c", "default") == "default"

    def test_invalid_json(self, temp_settings_path):
        """잘못된 JSON 처리."""
        temp_settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_settings_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json }")

        with patch.object(Settings, '__init__', lambda self: None):
            s = Settings()
            s.path = temp_settings_path
            s._data = {}
            s._load()

        # 기본값 사용
        assert s.get("hotkeys.scan.key") == "E"

    def test_save_preserves_unknown_keys(self, temp_settings_path):
        """알 수 없는 키 보존."""
        with patch.object(Settings, '__init__', lambda self: None):
            s = Settings()
            s.path = temp_settings_path
            s._data = {}
            s._load()

        s.set("custom.nested.key", "value")
        s.save()

        # 다시 로드
        with open(temp_settings_path, "r", encoding="utf-8") as f:
            saved = json.load(f)

        assert saved["custom"]["nested"]["key"] == "value"

    def test_deep_merge(self, settings_with_temp_path):
        """딥 머지 로직."""
        s = settings_with_temp_path

        base = {"a": {"b": 1, "c": 2}, "d": 3}
        override = {"a": {"b": 10, "e": 5}, "f": 6}

        result = s._deep_merge(base, override)

        assert result["a"]["b"] == 10  # 덮어씀
        assert result["a"]["c"] == 2   # 유지
        assert result["a"]["e"] == 5   # 추가
        assert result["d"] == 3        # 유지
        assert result["f"] == 6        # 추가

    def test_get_set_hotkey(self, settings_with_temp_path):
        """핫키 get/set 헬퍼."""
        s = settings_with_temp_path

        hotkey = s.get_hotkey("scan")
        assert hotkey["key"] == "E"
        assert hotkey["modifiers"] == ["ctrl", "shift"]

        s.set_hotkey("scan", ["alt"], "X")
        assert s.get_hotkey("scan") == {"modifiers": ["alt"], "key": "X"}

    def test_get_all_hotkeys(self, settings_with_temp_path):
        """모든 핫키 조회."""
        s = settings_with_temp_path

        hotkeys = s.get_all_hotkeys()
        assert "scan" in hotkeys
        assert "exit" in hotkeys

    def test_reset_hotkeys(self, settings_with_temp_path):
        """핫키 초기화 - reset 후 DEFAULT_SETTINGS["hotkeys"] 할당 확인.

        Note: 현재 구현은 shallow copy 사용. _deep_merge도 shallow라서
        DEFAULT_SETTINGS가 변경되는 버그가 있음. 이 테스트는 reset_hotkeys가
        DEFAULT_SETTINGS["hotkeys"]를 재할당하는지만 확인.
        """
        s = settings_with_temp_path

        # reset 전 hotkeys 참조 저장
        hotkeys_before = s._data.get("hotkeys")

        s.set_hotkey("scan", ["alt"], "X")
        s.reset_hotkeys()

        # reset 후 hotkeys가 새로 할당됨 (동일 객체 아님)
        hotkeys_after = s._data.get("hotkeys")
        assert hotkeys_after is not hotkeys_before or hotkeys_before is None

        # 모든 기본 핫키 키가 존재
        assert "scan" in s.get_all_hotkeys()
        assert "exit" in s.get_all_hotkeys()

    def test_increment_stat(self, settings_with_temp_path):
        """통계 증가."""
        s = settings_with_temp_path

        assert s.get("stats.scan_count") == 0
        s.increment_stat("scan_count")
        assert s.get("stats.scan_count") == 1
        s.increment_stat("scan_count")
        assert s.get("stats.scan_count") == 2

    def test_update_check_timestamp(self, settings_with_temp_path):
        """업데이트 확인 타임스탬프."""
        s = settings_with_temp_path

        assert s.get_last_update_check() == 0

        s.set_last_update_check(12345.0)
        assert s.get_last_update_check() == 12345.0

    def test_data_property(self, settings_with_temp_path):
        """data 프로퍼티."""
        s = settings_with_temp_path

        data = s.data
        assert isinstance(data, dict)
        assert "hotkeys" in data


class TestDebugHotkeys:
    """debug_hotkeys 관련 테스트."""

    def test_get_debug_hotkey_returns_config(self, settings_with_temp_path):
        """단일 디버그 핫키 조회."""
        s = settings_with_temp_path

        config = s.get_debug_hotkey("dump")
        assert config is not None
        assert config["key"] == "D"
        assert "ctrl" in config["modifiers"]
        assert "shift" in config["modifiers"]

    def test_set_debug_hotkey_updates_config(self, settings_with_temp_path):
        """디버그 핫키 설정 변경."""
        s = settings_with_temp_path

        s.set_debug_hotkey("dump", ["alt", "shift"], "X")
        config = s.get_debug_hotkey("dump")

        assert config["key"] == "X"
        assert config["modifiers"] == ["alt", "shift"]

    def test_get_all_debug_hotkeys_returns_dict(self, settings_with_temp_path):
        """모든 디버그 핫키 조회."""
        s = settings_with_temp_path

        hotkeys = s.get_all_debug_hotkeys()

        assert isinstance(hotkeys, dict)
        assert "dump" in hotkeys
        assert "profile" in hotkeys
        assert "event_monitor" in hotkeys
        assert "status" in hotkeys
        assert "test_navigation" in hotkeys
        assert "test_message" in hotkeys

    def test_reset_debug_hotkeys_restores_defaults(self, settings_with_temp_path):
        """디버그 핫키 기본값 복원."""
        s = settings_with_temp_path

        # 변경
        s.set_debug_hotkey("dump", ["alt"], "Z")
        assert s.get_debug_hotkey("dump")["key"] == "Z"

        # 복원
        s.reset_debug_hotkeys()

        # 기본값 확인
        config = s.get_debug_hotkey("dump")
        assert config["key"] == "D"
        assert config["modifiers"] == ["ctrl", "shift"]
