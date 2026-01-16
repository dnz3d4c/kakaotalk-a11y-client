# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""설정 저장/로드 모듈

JSON 기반 설정 영속화.
"""

import json
from pathlib import Path
from typing import Any, Optional

from .utils.debug import get_logger

log = get_logger("Settings")

# 기본 설정값
DEFAULT_SETTINGS = {
    "hotkeys": {
        "scan": {"modifiers": ["ctrl", "shift"], "key": "E"},
        "exit": {"modifiers": ["win", "ctrl"], "key": "K"},
    },
    "debug_hotkeys": {
        "dump": {"modifiers": ["ctrl", "shift"], "key": "D"},
        "profile": {"modifiers": ["ctrl", "shift"], "key": "P"},
        "event_monitor": {"modifiers": ["ctrl", "shift"], "key": "R"},
        "status": {"modifiers": ["ctrl", "shift"], "key": "S"},
        "test_navigation": {"modifiers": ["ctrl", "shift"], "key": "1"},
        "test_message": {"modifiers": ["ctrl", "shift"], "key": "2"},
    },
    "ui": {
        "window_size": [500, 400],
    },
    "stats": {
        "scan_count": 0,
        "message_count": 0,
    },
    "update": {
        "last_check_timestamp": 0,
    },
}

# 핫키 이름 매핑 (UI 표시용)
HOTKEY_NAMES = {
    "scan": "이모지 스캔",
    "exit": "프로그램 종료",
}

# 디버그 핫키 이름 매핑 (UI 표시용)
DEBUG_HOTKEY_NAMES = {
    "dump": "즉시 덤프",
    "profile": "프로파일 요약",
    "event_monitor": "이벤트 모니터 토글",
    "status": "디버그 상태 확인",
    "test_navigation": "탐색 테스트",
    "test_message": "메시지 테스트",
}


class Settings:
    """설정 관리 클래스"""

    def __init__(self):
        self.path = Path.home() / ".kakaotalk_a11y" / "settings.json"
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                log.debug(f"settings loaded: {self.path}")
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"settings load failed, using defaults: {e}")
                self._data = {}
        else:
            self._data = {}

        # 기본값으로 누락된 키 채우기
        self._merge_defaults()

    def _merge_defaults(self) -> None:
        self._data = self._deep_merge(DEFAULT_SETTINGS, self._data)

    def _deep_merge(self, base: dict, override: dict) -> dict:
        import copy
        result = copy.deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            log.debug(f"settings saved: {self.path}")
            return True
        except OSError as e:
            log.error(f"settings save failed: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """점 표기법: "hotkeys.scan.key" """
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """점 표기법: "hotkeys.scan.key" """
        keys = key.split(".")
        data = self._data
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value

    def get_hotkey(self, name: str) -> Optional[dict]:
        return self.get(f"hotkeys.{name}")

    def set_hotkey(self, name: str, modifiers: list[str], key: str) -> None:
        self.set(f"hotkeys.{name}", {"modifiers": modifiers, "key": key})

    def get_all_hotkeys(self) -> dict:
        return self.get("hotkeys", {})

    def reset_hotkeys(self) -> None:
        self._data["hotkeys"] = DEFAULT_SETTINGS["hotkeys"].copy()

    def get_debug_hotkey(self, name: str) -> Optional[dict]:
        return self.get(f"debug_hotkeys.{name}")

    def set_debug_hotkey(self, name: str, modifiers: list[str], key: str) -> None:
        self.set(f"debug_hotkeys.{name}", {"modifiers": modifiers, "key": key})

    def get_all_debug_hotkeys(self) -> dict:
        return self.get("debug_hotkeys", {})

    def reset_debug_hotkeys(self) -> None:
        import copy
        self._data["debug_hotkeys"] = copy.deepcopy(DEFAULT_SETTINGS["debug_hotkeys"])

    def increment_stat(self, name: str) -> None:
        current = self.get(f"stats.{name}", 0)
        self.set(f"stats.{name}", current + 1)

    def get_last_update_check(self) -> float:
        return self.get("update.last_check_timestamp", 0)

    def set_last_update_check(self, timestamp: float) -> None:
        self.set("update.last_check_timestamp", timestamp)

    @property
    def data(self) -> dict:
        return self._data


# 전역 싱글톤 인스턴스
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
