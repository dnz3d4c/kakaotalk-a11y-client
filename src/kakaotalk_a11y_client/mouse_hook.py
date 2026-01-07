# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""마우스 훅 모듈 - 비메시지 항목에서 우클릭 차단

날짜 구분자, 입퇴장 알림 등 비메시지 항목에서 우클릭 시
팝업메뉴가 열리지 않도록 차단.
"""
import ctypes
from ctypes import wintypes
from typing import Callable, Optional

from .utils.debug import get_logger

user32 = ctypes.windll.user32
log = get_logger("MouseHook")

# 비메시지 패턴 (팝업메뉴 차단 대상)
# 목적: 팝업 메뉴 차단 (자동 읽기 필터링과 별도 목적)
NON_MESSAGE_PATTERNS = [
    "년 ",              # 날짜 구분자: "2026년 1월 2일 금요일"
    "읽지 않은 메시지",  # 읽지 않음 구분선
    "님이 들어왔습니다",  # 입장 알림
    "님이 나갔습니다",   # 퇴장 알림
]

WH_MOUSE_LL = 14
WM_RBUTTONDOWN = 0x0204


class MouseHook:
    """Low-Level 마우스 훅 - 비메시지 항목 우클릭 차단"""

    def __init__(self, get_last_focused_name: Callable[[], Optional[str]]):
        self._get_last_focused_name = get_last_focused_name
        self._hook_id = None

        # C 콜백 타입 정의 (prevent garbage collection)
        self._HOOKPROC = ctypes.CFUNCTYPE(
            ctypes.c_long,
            ctypes.c_int,
            wintypes.WPARAM,
            wintypes.LPARAM
        )
        self._hook_proc = self._HOOKPROC(self._mouse_callback)

    def _is_non_message_item(self, name: str) -> bool:
        for pattern in NON_MESSAGE_PATTERNS:
            if pattern in name:
                return True
        return False

    def _mouse_callback(self, nCode: int, wParam: int, lParam: int) -> int:
        """비메시지 항목 우클릭 시 1 반환(차단)."""
        if nCode >= 0 and wParam == WM_RBUTTONDOWN:
            # 우클릭 감지 → 비메시지 항목이면 차단
            last_name = self._get_last_focused_name()
            if last_name and self._is_non_message_item(last_name):
                preview = last_name[:30] + "..." if len(last_name) > 30 else last_name
                log.trace(f"비메시지 항목 우클릭 차단: {preview}")
                return 1  # 이벤트 차단

        # 통과
        return user32.CallNextHookEx(self._hook_id, nCode, wParam, lParam)

    def install(self) -> bool:
        """SetWindowsHookExW 호출. 이미 설치됐으면 True 반환."""
        if self._hook_id:
            return True  # 이미 설치됨

        self._hook_id = user32.SetWindowsHookExW(
            WH_MOUSE_LL,
            self._hook_proc,
            None,
            0
        )
        if self._hook_id:
            log.debug("마우스 훅 설치 완료")
            return True
        else:
            error_code = ctypes.GetLastError()
            log.error(f"마우스 훅 설치 실패: 오류 코드 {error_code}")
            return False

    def uninstall(self) -> None:
        if self._hook_id:
            user32.UnhookWindowsHookEx(self._hook_id)
            self._hook_id = None
            log.debug("마우스 훅 해제 완료")
