# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""모드 상태 관리 - 선택/네비게이션 모드 상태 추적

메뉴 모드: FocusMonitorService 로컬 관리
네비게이션 모드: hwnd 추적만 (조율은 FocusMonitorService)
"""

import threading
from typing import Optional, TYPE_CHECKING

from .utils.debug import get_logger

if TYPE_CHECKING:
    from .hotkeys import HotkeyManager

log = get_logger("ModeManager")


class ModeManager:
    """모드 상태 관리자"""

    def __init__(self):
        # 스레드 안전을 위한 락 (RLock: 중첩 호출 허용)
        self._lock = threading.RLock()

        # 모드 플래그
        self._in_selection_mode = False
        self._in_navigation_mode = False

        # 관련 상태
        self._current_chat_hwnd: Optional[int] = None

    # === 읽기 전용 프로퍼티 ===

    @property
    def in_selection_mode(self) -> bool:
        with self._lock:
            return self._in_selection_mode

    @property
    def in_navigation_mode(self) -> bool:
        with self._lock:
            return self._in_navigation_mode

    @property
    def current_chat_hwnd(self) -> Optional[int]:
        with self._lock:
            return self._current_chat_hwnd

    # === 선택 모드 ===

    def enter_selection_mode(self, hotkey_manager: "HotkeyManager") -> None:
        """ESC, 숫자키 핫키 등록."""
        with self._lock:
            self._in_selection_mode = True
        # 외부 호출은 락 밖에서
        hotkey_manager.enable_selection_mode()
        log.debug("selection mode entered")

    def exit_selection_mode(self, hotkey_manager: "HotkeyManager") -> None:
        """ESC, 숫자키 핫키 해제."""
        with self._lock:
            self._in_selection_mode = False
        # 외부 호출은 락 밖에서
        hotkey_manager.disable_selection_mode()
        log.debug("selection mode exited")

    # === 네비게이션 모드 (상태 추적만) ===

    def is_same_chat_room(self, hwnd: int) -> bool:
        """이미 같은 채팅방에 있는지 확인."""
        with self._lock:
            return self._in_navigation_mode and self._current_chat_hwnd == hwnd

    def set_navigation_mode(self, hwnd: int) -> None:
        """네비게이션 모드 상태 설정. 조율은 호출자가 담당."""
        with self._lock:
            self._current_chat_hwnd = hwnd
            self._in_navigation_mode = True
        log.debug(f"navigation mode set: hwnd={hwnd}")

    def clear_navigation_mode(self) -> None:
        """네비게이션 모드 상태 해제. 조율은 호출자가 담당."""
        with self._lock:
            if not self._in_navigation_mode:
                return
            self._in_navigation_mode = False
            self._current_chat_hwnd = None
        log.debug("navigation mode cleared")
