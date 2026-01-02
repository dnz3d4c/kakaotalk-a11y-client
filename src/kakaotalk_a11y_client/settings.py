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
        "reread": {"modifiers": ["ctrl", "shift"], "key": "S"},
        "exit": {"modifiers": ["win", "ctrl"], "key": "K"},
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
    "reread": "다시 읽기",
    "exit": "프로그램 종료",
}


class Settings:
    """설정 관리 클래스"""

    def __init__(self):
        self.path = Path.home() / ".kakaotalk_a11y" / "settings.json"
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        """설정 파일 로드"""
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                log.debug(f"설정 로드: {self.path}")
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"설정 로드 실패, 기본값 사용: {e}")
                self._data = {}
        else:
            self._data = {}

        # 기본값으로 누락된 키 채우기
        self._merge_defaults()

    def _merge_defaults(self) -> None:
        """기본값과 병합"""
        self._data = self._deep_merge(DEFAULT_SETTINGS, self._data)

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """딥 머지: base를 override로 덮어쓰기"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def save(self) -> bool:
        """설정 파일 저장"""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            log.debug(f"설정 저장: {self.path}")
            return True
        except OSError as e:
            log.error(f"설정 저장 실패: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """설정값 가져오기 (점 표기법 지원)

        예: settings.get("hotkeys.scan.key")
        """
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """설정값 저장 (점 표기법 지원)

        예: settings.set("hotkeys.scan.key", "F")
        """
        keys = key.split(".")
        data = self._data
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value

    def get_hotkey(self, name: str) -> Optional[dict]:
        """핫키 설정 가져오기"""
        return self.get(f"hotkeys.{name}")

    def set_hotkey(self, name: str, modifiers: list[str], key: str) -> None:
        """핫키 설정 저장"""
        self.set(f"hotkeys.{name}", {"modifiers": modifiers, "key": key})

    def get_all_hotkeys(self) -> dict:
        """모든 핫키 설정 가져오기"""
        return self.get("hotkeys", {})

    def reset_hotkeys(self) -> None:
        """핫키 설정 초기화"""
        self._data["hotkeys"] = DEFAULT_SETTINGS["hotkeys"].copy()

    def increment_stat(self, name: str) -> None:
        """통계 증가"""
        current = self.get(f"stats.{name}", 0)
        self.set(f"stats.{name}", current + 1)

    def get_last_update_check(self) -> float:
        """마지막 업데이트 체크 시간(timestamp) 반환"""
        return self.get("update.last_check_timestamp", 0)

    def set_last_update_check(self, timestamp: float) -> None:
        """마지막 업데이트 체크 시간 저장"""
        self.set("update.last_check_timestamp", timestamp)

    @property
    def data(self) -> dict:
        """전체 설정 데이터"""
        return self._data


# 전역 싱글톤 인스턴스
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """설정 싱글톤 인스턴스 가져오기"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
