# SPDX-License-Identifier: MIT
"""FocusMonitorService 단위 테스트. Mock 의존성으로 테스트 가능한 구조 검증."""

from typing import Any, List, Optional
from unittest.mock import MagicMock, patch
import pytest

from kakaotalk_a11y_client.focus_monitor import FocusMonitorService


class MockUIAAdapter:
    """테스트용 Mock UIAAdapter."""

    def __init__(self):
        self.com_initialized = False
        self._mock_control = MagicMock()
        self._mock_menu_item = MagicMock()
        self._mock_children: List[Any] = []

    def get_control_from_handle(self, hwnd: int) -> Optional[Any]:
        return self._mock_control

    def find_list_control(self, parent: Any, name: str, search_depth: int = 4) -> Optional[Any]:
        return MagicMock()

    def control_exists(self, control: Any, max_seconds: float = 1.0) -> bool:
        return True

    def get_children(self, control: Any, max_depth: int = 2, filter_empty: bool = True) -> List[Any]:
        return self._mock_children

    def get_direct_children(self, control: Any) -> List[Any]:
        return self._mock_children

    def get_focused_control(self) -> Optional[Any]:
        return self._mock_control

    def find_menu_item_control(self, parent: Any, search_depth: int = 3) -> Optional[Any]:
        return self._mock_menu_item

    def init_com(self) -> None:
        self.com_initialized = True

    def uninit_com(self) -> None:
        self.com_initialized = False


class MockSpeakCallback:
    """테스트용 Mock SpeakCallback. 호출 기록."""

    def __init__(self):
        self.spoken_texts: List[str] = []

    def __call__(self, text: str) -> None:
        self.spoken_texts.append(text)


class MockModeManager:
    """테스트용 Mock ModeManager."""

    def __init__(self):
        self.in_context_menu_mode = False
        self.in_navigation_mode = False
        self.current_chat_hwnd = 0

    def enter_context_menu_mode(self, message_monitor):
        self.in_context_menu_mode = True

    def exit_context_menu_mode(self, message_monitor):
        self.in_context_menu_mode = False

    def enter_navigation_mode(self, hwnd, chat_navigator, message_monitor, hotkey_manager):
        self.in_navigation_mode = True
        self.current_chat_hwnd = hwnd

    def exit_navigation_mode(self, message_monitor, chat_navigator):
        self.in_navigation_mode = False

    def update_menu_closed_time(self):
        pass

    def should_exit_navigation_by_grace_period(self, grace_period: float) -> bool:
        return True


class TestFocusMonitorService:
    """FocusMonitorService 테스트."""

    @pytest.fixture
    def mock_uia(self):
        return MockUIAAdapter()

    @pytest.fixture
    def mock_speak(self):
        return MockSpeakCallback()

    @pytest.fixture
    def mock_mode_manager(self):
        return MockModeManager()

    @pytest.fixture
    def service(self, mock_uia, mock_speak, mock_mode_manager):
        """FocusMonitorService with mock dependencies."""
        mock_message_monitor = MagicMock()
        mock_chat_navigator = MagicMock()
        mock_hotkey_manager = MagicMock()

        return FocusMonitorService(
            mode_manager=mock_mode_manager,
            message_monitor=mock_message_monitor,
            chat_navigator=mock_chat_navigator,
            hotkey_manager=mock_hotkey_manager,
            uia_adapter=mock_uia,
            speak_callback=mock_speak,
        )

    def test_init_with_injected_dependencies(self, service, mock_uia, mock_speak):
        """의존성 주입 확인."""
        assert service._uia is mock_uia
        assert service._speak is mock_speak

    def test_speak_item_cleans_special_chars(self, service, mock_speak):
        """_speak_item이 특수문자를 제거하는지 확인."""
        service._speak_item("• 테스트\u00a0메시지", "ListItemControl")

        assert len(mock_speak.spoken_texts) == 1
        # bullet과 nbsp가 제거/변환됨
        assert "•" not in mock_speak.spoken_texts[0]

    def test_speak_item_removes_access_key(self, service, mock_speak):
        """MenuItemControl에서 AccessKey 제거 확인."""
        service._speak_item("k채팅방", "MenuItemControl")

        assert len(mock_speak.spoken_texts) == 1
        assert mock_speak.spoken_texts[0] == "채팅방"

    def test_speak_last_message(self, service, mock_uia, mock_speak):
        """마지막 메시지 읽기."""
        mock_msg = MagicMock()
        mock_msg.Name = "마지막 메시지 내용"
        mock_uia._mock_children = [mock_msg]

        mock_list_control = MagicMock()
        service._speak_last_message(mock_list_control)

        assert len(mock_speak.spoken_texts) == 1
        assert mock_speak.spoken_texts[0] == "마지막 메시지 내용"

    def test_speak_last_message_empty_list(self, service, mock_uia, mock_speak):
        """빈 메시지 목록."""
        mock_uia._mock_children = []

        mock_list_control = MagicMock()
        service._speak_last_message(mock_list_control)

        # 아무것도 안 읽음
        assert len(mock_speak.spoken_texts) == 0

    def test_speak_last_message_duplicate_prevention(self, service, mock_uia, mock_speak):
        """중복 메시지 방지."""
        mock_msg = MagicMock()
        mock_msg.Name = "중복 메시지"
        mock_uia._mock_children = [mock_msg]

        mock_list_control = MagicMock()

        # 첫 번째 호출
        service._speak_last_message(mock_list_control)
        # 두 번째 호출 (중복)
        service._speak_last_message(mock_list_control)

        # 한 번만 읽힘
        assert len(mock_speak.spoken_texts) == 1

    def test_get_first_menu_item_name(self, service, mock_uia):
        """첫 메뉴 항목 이름 가져오기."""
        mock_uia._mock_menu_item.Name = "첫 메뉴"

        result = service._get_first_menu_item_name(12345)

        assert result == "첫 메뉴"

    def test_is_running_property(self, service):
        """is_running 프로퍼티."""
        assert service.is_running is False

        service._running = True
        assert service.is_running is True

    def test_last_focused_name_property(self, service):
        """last_focused_name 프로퍼티."""
        assert service.last_focused_name is None

        service._last_focused_name = "테스트"
        assert service.last_focused_name == "테스트"
