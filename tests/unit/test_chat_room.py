# SPDX-License-Identifier: MIT
"""ChatRoomNavigator 단위 테스트. MockUIAAdapter로 UIA 의존성 제거."""

from typing import Any, List, Optional
from unittest.mock import MagicMock, patch
import pytest

from kakaotalk_a11y_client.navigation.chat_room import ChatRoomNavigator


class MockUIAAdapter:
    """테스트용 Mock UIAAdapter."""

    def __init__(self):
        self.com_initialized = False
        self._mock_control = MagicMock()
        self._mock_list_control = MagicMock()
        self._mock_children: List[Any] = []

        # 기본 동작 설정
        self._control_exists = True
        self._return_control = True
        self._return_list = True

    def get_control_from_handle(self, hwnd: int) -> Optional[Any]:
        if not self._return_control:
            return None
        return self._mock_control

    def find_list_control(
        self,
        parent: Any,
        name: str,
        search_depth: int = 4
    ) -> Optional[Any]:
        if not self._return_list:
            return None
        return self._mock_list_control

    def control_exists(self, control: Any, max_seconds: float = 1.0) -> bool:
        return self._control_exists

    def get_children(
        self,
        control: Any,
        max_depth: int = 2,
        filter_empty: bool = True
    ) -> List[Any]:
        return self._mock_children

    def init_com(self) -> None:
        self.com_initialized = True

    def uninit_com(self) -> None:
        self.com_initialized = False


class TestChatRoomNavigator:
    """ChatRoomNavigator 테스트."""

    @pytest.fixture
    def mock_adapter(self):
        """Mock UIAAdapter fixture."""
        return MockUIAAdapter()

    @pytest.fixture
    def navigator(self, mock_adapter):
        """ChatRoomNavigator with mock adapter."""
        return ChatRoomNavigator(uia_adapter=mock_adapter)

    def test_enter_chat_room_success(self, navigator, mock_adapter):
        """채팅방 진입 성공."""
        # 메시지 항목 설정
        mock_msg = MagicMock()
        mock_msg.Name = "테스트 메시지"
        mock_adapter._mock_children = [mock_msg]

        result = navigator.enter_chat_room(hwnd=12345)

        assert result is True
        assert navigator.is_active is True
        assert navigator._hwnd == 12345
        assert mock_adapter.com_initialized is True

    def test_enter_chat_room_no_control(self, navigator, mock_adapter):
        """컨트롤 못 찾으면 실패."""
        mock_adapter._return_control = False

        result = navigator.enter_chat_room(hwnd=12345)

        assert result is False
        assert navigator.is_active is False

    @patch('kakaotalk_a11y_client.navigation.chat_room.message_list_cache')
    def test_enter_chat_room_no_list(self, mock_cache, navigator, mock_adapter):
        """메시지 리스트 못 찾으면 실패."""
        mock_cache.get.return_value = None  # 캐시 미스
        mock_adapter._return_list = False

        result = navigator.enter_chat_room(hwnd=12345)

        assert result is False
        assert navigator.is_active is False

    @patch('kakaotalk_a11y_client.navigation.chat_room.message_list_cache')
    def test_enter_chat_room_list_not_exists(self, mock_cache, navigator, mock_adapter):
        """리스트가 존재하지 않으면 실패."""
        mock_cache.get.return_value = None  # 캐시 미스
        mock_adapter._control_exists = False

        result = navigator.enter_chat_room(hwnd=12345)

        assert result is False
        assert navigator.is_active is False

    def test_exit_chat_room(self, navigator, mock_adapter):
        """채팅방 종료 시 상태 초기화."""
        # 먼저 진입
        mock_msg = MagicMock()
        mock_msg.Name = "테스트"
        mock_adapter._mock_children = [mock_msg]
        navigator.enter_chat_room(hwnd=12345)

        # 종료
        navigator.exit_chat_room()

        assert navigator.is_active is False
        assert navigator.messages == []
        assert navigator.chat_control is None
        assert navigator._hwnd == 0
        assert mock_adapter.com_initialized is False

    def test_refresh_messages_no_chat_control(self, navigator):
        """chat_control 없으면 refresh 실패."""
        result = navigator.refresh_messages()
        assert result is False

    @patch('kakaotalk_a11y_client.navigation.chat_room.message_list_cache')
    def test_refresh_messages_cached(self, mock_cache, navigator, mock_adapter):
        """캐시 사용 시 캐시에서 반환."""
        # 진입 설정
        mock_msg = MagicMock()
        mock_msg.Name = "캐시된 메시지"
        mock_adapter._mock_children = [mock_msg]

        navigator.enter_chat_room(hwnd=12345)

        # 캐시 설정
        cached_messages = [MagicMock(Name="캐시 메시지")]
        mock_cache.get.return_value = cached_messages

        result = navigator.refresh_messages(use_cache=True)

        assert result is True
        assert navigator.messages == cached_messages

    def test_refresh_messages_empty_list(self, navigator, mock_adapter):
        """빈 메시지 목록이면 False."""
        mock_adapter._mock_children = []  # 빈 목록
        navigator._hwnd = 12345
        navigator.chat_control = mock_adapter._mock_control

        result = navigator.refresh_messages(use_cache=False)

        assert result is False

    def test_current_focused_item_property(self, navigator):
        """current_focused_item 프로퍼티 동작."""
        mock_item = MagicMock()

        navigator.current_focused_item = mock_item
        assert navigator.current_focused_item == mock_item

        navigator.current_focused_item = None
        assert navigator.current_focused_item is None
