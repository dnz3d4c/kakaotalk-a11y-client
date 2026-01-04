# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""모드 상태 관리

세 가지 모드의 상태와 전환을 관리:
- 선택 모드: 이모지 선택 중
- 네비게이션 모드: 채팅방 메시지 탐색 중
- 컨텍스트 메뉴 모드: 우클릭 메뉴 열림

상호 배제 규칙:
1. 네비게이션 모드 진입 시 선택 모드 자동 종료
2. 메뉴 모드 시 MessageMonitor pause/resume
3. 비카카오톡 창에서 네비게이션 모드 자동 종료 (메뉴 모드 아닐 때만)
"""

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
        """이모지 선택 모드 여부"""
        return self._in_selection_mode

    @property
    def in_navigation_mode(self) -> bool:
        """네비게이션 모드 여부"""
        return self._in_navigation_mode

    @property
    def in_context_menu_mode(self) -> bool:
        """컨텍스트 메뉴 모드 여부"""
        return self._in_context_menu_mode

    @property
    def current_chat_hwnd(self) -> Optional[int]:
        """현재 채팅방 윈도우 핸들"""
        return self._current_chat_hwnd

    @property
    def menu_closed_time(self) -> float:
        """메뉴 닫힌 시간 (grace period용)"""
        return self._menu_closed_time

    # === 선택 모드 ===

    def enter_selection_mode(self, hotkey_manager: "HotkeyManager") -> None:
        """선택 모드 진입"""
        self._in_selection_mode = True
        hotkey_manager.enable_selection_mode()
        log.debug("선택 모드 진입")

    def exit_selection_mode(self, hotkey_manager: "HotkeyManager") -> None:
        """선택 모드 종료"""
        self._in_selection_mode = False
        hotkey_manager.disable_selection_mode()
        log.debug("선택 모드 종료")

    # === 네비게이션 모드 ===

    def enter_navigation_mode(
        self,
        hwnd: int,
        chat_navigator: "ChatRoomNavigator",
        message_monitor: "MessageMonitor",
        hotkey_manager: "HotkeyManager",
    ) -> bool:
        """네비게이션 모드 진입

        Args:
            hwnd: 채팅방 윈도우 핸들
            chat_navigator: 채팅방 네비게이터
            message_monitor: 메시지 모니터
            hotkey_manager: 핫키 매니저 (선택 모드 종료용)

        Returns:
            진입 성공 여부
        """
        if self._in_navigation_mode and self._current_chat_hwnd == hwnd:
            return True  # 이미 같은 채팅방에서 활성화됨

        # 상호 배제: 선택 모드 자동 종료
        if self._in_selection_mode:
            self.exit_selection_mode(hotkey_manager)

        # 채팅방 진입
        if chat_navigator.enter_chat_room(hwnd):
            self._current_chat_hwnd = hwnd
            self._in_navigation_mode = True
            # 메시지 자동 읽기 시작
            message_monitor.start(hwnd)
            log.debug(f"네비게이션 모드 진입: hwnd={hwnd}")
            return True

        return False

    def exit_navigation_mode(
        self,
        message_monitor: "MessageMonitor",
        chat_navigator: "ChatRoomNavigator",
    ) -> None:
        """네비게이션 모드 종료"""
        if not self._in_navigation_mode:
            return

        # 메시지 자동 읽기 중지
        message_monitor.stop()
        chat_navigator.exit_chat_room()
        self._in_navigation_mode = False
        self._current_chat_hwnd = None
        log.debug("네비게이션 모드 종료")

    # === 컨텍스트 메뉴 모드 ===

    def enter_context_menu_mode(self, message_monitor: "MessageMonitor") -> None:
        """컨텍스트 메뉴 모드 진입"""
        if self._in_context_menu_mode:
            return

        self._in_context_menu_mode = True
        self._menu_closed_time = time.time()

        # MessageMonitor pause (stop 대신 - COM 재등록 오버헤드 방지)
        if message_monitor and message_monitor.is_running():
            message_monitor.pause()
        log.trace("메뉴 모드 진입")

    def exit_context_menu_mode(self, message_monitor: "MessageMonitor") -> None:
        """컨텍스트 메뉴 모드 종료"""
        if not self._in_context_menu_mode:
            return

        self._in_context_menu_mode = False
        self._menu_closed_time = time.time()

        # MessageMonitor resume
        if message_monitor and message_monitor.is_running():
            message_monitor.resume()
        log.trace("메뉴 모드 종료")

    def update_menu_closed_time(self) -> None:
        """메뉴 닫힌 시간 갱신 (grace period용)"""
        self._menu_closed_time = time.time()

    def should_exit_navigation_by_grace_period(self, grace_period: float = 1.0) -> bool:
        """grace period 경과 여부 확인

        메뉴 닫힌 후 일정 시간이 지났는지 확인.
        """
        return time.time() - self._menu_closed_time > grace_period
