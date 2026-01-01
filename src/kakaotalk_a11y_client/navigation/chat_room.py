# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""채팅방 내부 메시지 목록 관리 모듈

NVDA 패턴 적용:
- TTL 캐싱 (message_list_cache)
- safe_uia_call로 COMError 처리
"""

from typing import Optional

import uiautomation as auto
import pythoncom

from ..window_finder import KAKAOTALK_LIST_CLASS
from ..utils.debug_tools import debug_tools
from ..utils.uia_cache import message_list_cache
from ..utils.uia_utils import safe_uia_call


class ChatRoomNavigator:
    """채팅방 내부 메시지 목록 관리 클래스

    MessageMonitor에서 메시지 변화 감지용으로 사용.
    """

    def __init__(self):
        self.messages: list[auto.Control] = []
        self.chat_control: Optional[auto.Control] = None
        self.list_control: Optional[auto.Control] = None  # 메시지 목록 ListControl
        self.is_active: bool = False

    def enter_chat_room(self, hwnd: int) -> bool:
        """채팅방 진입, 메시지 목록 로드

        Args:
            hwnd: 채팅방 창 핸들

        Returns:
            성공 여부
        """
        try:
            # 스레드에서 UIA 사용 시 COM 초기화 필요
            pythoncom.CoInitialize()

            self.chat_control = auto.ControlFromHandle(hwnd)
            if not self.chat_control:
                return False

            if not self.refresh_messages():
                return False

            self.is_active = True
            return True

        except Exception:
            return False

    def exit_chat_room(self):
        """채팅방 나가기"""
        self.is_active = False
        self.messages = []
        self.chat_control = None
        self.list_control = None

    def refresh_messages(self, use_cache: bool = True) -> bool:
        """메시지 목록 새로고침 (NVDA 패턴: TTL 캐싱 적용)

        Args:
            use_cache: 캐시 사용 여부 (기본 True)

        Returns:
            성공 여부
        """
        if not self.chat_control:
            return False

        with debug_tools.debug_operation('chat_room.refresh_messages'):
            try:
                # 캐시 확인 (TTL 0.3초)
                cache_key = f"messages_{id(self.chat_control)}"
                if use_cache:
                    cached = message_list_cache.get(cache_key)
                    if cached is not None:
                        self.messages = cached
                        return len(self.messages) > 0

                # 채팅방 내 메시지 리스트 찾기
                msg_list = safe_uia_call(
                    lambda: self.chat_control.ListControl(Name="메시지", searchDepth=5),
                    default=None,
                    error_msg="메시지 리스트 찾기"
                )

                if not msg_list or not msg_list.Exists(maxSearchSeconds=1):
                    return False

                # 메시지 목록 참조 저장
                self.list_control = msg_list

                # 메시지 항목들 가져오기 (safe_uia_call + 필터링)
                from ..utils.uia_utils import get_children_recursive
                messages = safe_uia_call(
                    lambda: get_children_recursive(msg_list, max_depth=2, filter_empty=True),
                    default=[],
                    error_msg="메시지 항목 가져오기"
                )

                self.messages = messages

                # 빈 리스트 감지 시 덤프
                debug_tools.dump_on_condition(
                    'empty_list',
                    len(messages) == 0,
                    {'list_name': 'messages', 'cache_used': use_cache}
                )

                # 캐시에 저장
                if messages:
                    message_list_cache.set(cache_key, messages)

                return len(self.messages) > 0

            except Exception:
                return False
