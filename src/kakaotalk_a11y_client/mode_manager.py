# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""모드 상태 관리 - 선택/네비게이션/메뉴 모드 전환"""

import threading
import time
from typing import Optional, TYPE_CHECKING

from .utils.debug import get_logger

if TYPE_CHECKING:
    from .hotkeys import HotkeyManager
    from .navigation import ChatRoomNavigator
    from .navigation.message_monitor import MessageMonitor

log = get_logger("ModeManager")


class ModeManager:
    """모드 상태 관리자"""

    def __init__(self):
        # 스레드 안전을 위한 락 (RLock: 중첩 호출 허용)
        self._lock = threading.RLock()

        # 모드 플래그
        self._in_selection_mode = False
        self._in_navigation_mode = False
        self._in_context_menu_mode = False

        # 관련 상태
        self._current_chat_hwnd: Optional[int] = None
        self._menu_closed_time: float = 0.0

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
    def in_context_menu_mode(self) -> bool:
        with self._lock:
            return self._in_context_menu_mode

    @property
    def current_chat_hwnd(self) -> Optional[int]:
        with self._lock:
            return self._current_chat_hwnd

    @property
    def menu_closed_time(self) -> float:
        with self._lock:
            return self._menu_closed_time

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

    # === 네비게이션 모드 ===

    def enter_navigation_mode(
        self,
        hwnd: int,
        chat_navigator: "ChatRoomNavigator",
        message_monitor: "MessageMonitor",
        hotkey_manager: "HotkeyManager",
    ) -> bool:
        """채팅방 진입 + MessageMonitor 시작. 선택 모드면 자동 종료."""
        # 상태 체크 + 변경은 락 안에서
        with self._lock:
            if self._in_navigation_mode and self._current_chat_hwnd == hwnd:
                return True  # 이미 같은 채팅방에서 활성화됨
            should_exit_selection = self._in_selection_mode

        # 외부 호출은 락 밖에서 (RLock이므로 중첩 호출도 OK)
        if should_exit_selection:
            self.exit_selection_mode(hotkey_manager)

        # 채팅방 진입 (외부 호출)
        if chat_navigator.enter_chat_room(hwnd):
            with self._lock:
                self._current_chat_hwnd = hwnd
                self._in_navigation_mode = True
            # 메시지 자동 읽기 시작
            message_monitor.start(hwnd)
            log.debug(f"navigation mode entered: hwnd={hwnd}")
            return True

        return False

    def exit_navigation_mode(
        self,
        message_monitor: "MessageMonitor",
        chat_navigator: "ChatRoomNavigator",
    ) -> None:
        """MessageMonitor 중지 + 채팅방 종료."""
        with self._lock:
            if not self._in_navigation_mode:
                return
            # 상태 먼저 변경
            self._in_navigation_mode = False
            self._current_chat_hwnd = None

        # 외부 호출은 락 밖에서
        message_monitor.stop()
        chat_navigator.exit_chat_room()
        log.debug("navigation mode exited")

    # === 컨텍스트 메뉴 모드 ===

    def enter_context_menu_mode(self, message_monitor: "MessageMonitor") -> None:
        """MessageMonitor pause. stop 대신 pause로 COM 재등록 방지."""
        with self._lock:
            if self._in_context_menu_mode:
                return
            self._in_context_menu_mode = True
            self._menu_closed_time = time.time()
            should_pause = message_monitor and message_monitor.is_running()

        # 외부 호출은 락 밖에서
        if should_pause:
            message_monitor.pause()
        log.trace("menu mode entered")

    def exit_context_menu_mode(self, message_monitor: "MessageMonitor") -> None:
        """MessageMonitor resume."""
        with self._lock:
            if not self._in_context_menu_mode:
                return
            self._in_context_menu_mode = False
            self._menu_closed_time = time.time()
            should_resume = message_monitor and message_monitor.is_running()

        # 외부 호출은 락 밖에서
        if should_resume:
            message_monitor.resume()
        log.trace("menu mode exited")

    def update_menu_closed_time(self) -> None:
        with self._lock:
            self._menu_closed_time = time.time()

    def should_exit_navigation_by_grace_period(self, grace_period: float = 1.0) -> bool:
        """메뉴 닫힌 후 grace_period 경과 여부."""
        with self._lock:
            return time.time() - self._menu_closed_time > grace_period
