# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""채팅방 메시지 목록 관리. UIAAdapter 사용으로 UIA 직접 호출 제거."""

from typing import Any, List, Optional, TYPE_CHECKING

from ..config import SEARCH_DEPTH_MESSAGE_LIST
from ..utils.debug_tools import debug_tools
from ..utils.uia_cache import message_list_cache

if TYPE_CHECKING:
    from ..infrastructure.uia_adapter import UIAAdapter


class ChatRoomNavigator:
    """채팅방 메시지 목록 관리. MessageMonitor에서 참조."""

    def __init__(self, uia_adapter: Optional["UIAAdapter"] = None):
        """
        Args:
            uia_adapter: UIA 접근 어댑터. None이면 기본 싱글톤 사용.
        """
        from ..infrastructure.uia_adapter import get_default_uia_adapter
        self._uia = uia_adapter or get_default_uia_adapter()

        self.messages: List[Any] = []
        self.chat_control: Optional[Any] = None
        self.list_control: Optional[Any] = None  # 메시지 목록 ListControl
        self.is_active: bool = False
        self._hwnd: int = 0  # 캐시 키용 창 핸들
        self._current_focused_item: Optional[Any] = None  # 현재 포커스된 메시지 (컨텍스트 메뉴용)

    def enter_chat_room(self, hwnd: int) -> bool:
        """채팅방 진입. COM 초기화 후 메시지 목록 로드."""
        try:
            # COM 초기화 (Adapter가 스레드별 관리)
            self._uia.init_com()

            self._hwnd = hwnd  # 캐시 키용 저장
            self.chat_control = self._uia.get_control_from_handle(hwnd)
            if not self.chat_control:
                return False

            if not self.refresh_messages():
                return False

            self.is_active = True
            return True

        except Exception:
            return False

    def exit_chat_room(self):
        """상태 초기화 및 COM 해제."""
        self.is_active = False
        self.messages = []
        self.chat_control = None
        self.list_control = None
        self._hwnd = 0
        self._current_focused_item = None
        # COM 해제 (Adapter가 스레드별 관리)
        self._uia.uninit_com()

    @property
    def current_focused_item(self) -> Optional[Any]:
        """컨텍스트 메뉴 표시용 포커스 메시지."""
        return self._current_focused_item

    @current_focused_item.setter
    def current_focused_item(self, item: Optional[Any]):
        self._current_focused_item = item

    def refresh_messages(self, use_cache: bool = True) -> bool:
        """메시지 목록 새로고침. hwnd 기반 TTL 캐시 사용."""
        if not self.chat_control:
            return False

        with debug_tools.debug_operation('chat_room.refresh_messages'):
            try:
                # 캐시 확인 (hwnd 기반 키로 히트율 개선)
                cache_key = f"messages_{self._hwnd}"
                if use_cache:
                    cached = message_list_cache.get(cache_key)
                    if cached is not None:
                        self.messages = cached
                        return len(self.messages) > 0

                # 채팅방 내 메시지 리스트 찾기
                msg_list = self._uia.find_list_control(
                    self.chat_control,
                    name="메시지",
                    search_depth=SEARCH_DEPTH_MESSAGE_LIST
                )

                if not msg_list or not self._uia.control_exists(msg_list, max_seconds=1.0):
                    return False

                # 메시지 목록 참조 저장
                self.list_control = msg_list

                # 메시지 항목들 가져오기
                messages = self._uia.get_children(msg_list, max_depth=2, filter_empty=True)

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
