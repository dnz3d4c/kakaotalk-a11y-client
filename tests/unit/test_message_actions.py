"""메시지 액션 테스트"""
import pytest
from unittest.mock import Mock, patch


class TestMessageActionManager:
    """MessageActionManager 테스트"""

    def test_register_action(self):
        """액션 등록"""
        from kakaotalk_a11y_client.message_actions.manager import MessageActionManager

        manager = MessageActionManager()
        action = Mock()
        manager.register("c", action)
        assert "c" in manager._actions

    def test_activate_registers_hotkeys(self):
        """활성화 시 핫키 등록"""
        from kakaotalk_a11y_client.message_actions.manager import MessageActionManager

        manager = MessageActionManager()
        action = Mock()
        manager.register("c", action)

        with patch("keyboard.add_hotkey") as mock_add:
            manager.activate()
            mock_add.assert_called_once()
            assert manager._active is True

    def test_activate_idempotent(self):
        """이미 활성화된 상태에서 재호출 시 무시"""
        from kakaotalk_a11y_client.message_actions.manager import MessageActionManager

        manager = MessageActionManager()
        manager._active = True

        with patch("keyboard.add_hotkey") as mock_add:
            manager.activate()
            mock_add.assert_not_called()

    def test_deactivate_removes_hotkeys(self):
        """비활성화 시 핫키 해제"""
        from kakaotalk_a11y_client.message_actions.manager import MessageActionManager

        manager = MessageActionManager()
        manager.register("c", Mock())
        manager._active = True

        with patch("keyboard.remove_hotkey") as mock_remove:
            manager.deactivate()
            mock_remove.assert_called_once()
            assert manager._active is False

    def test_deactivate_idempotent(self):
        """이미 비활성화된 상태에서 재호출 시 무시"""
        from kakaotalk_a11y_client.message_actions.manager import MessageActionManager

        manager = MessageActionManager()
        manager._active = False

        with patch("keyboard.remove_hotkey") as mock_remove:
            manager.deactivate()
            mock_remove.assert_not_called()


class TestCopyMessageAction:
    """CopyMessageAction 테스트"""

    def test_execute_success(self):
        """복사 성공"""
        from kakaotalk_a11y_client.message_actions.copy_action import CopyMessageAction

        extractor = Mock()
        extractor.extract_from_current_focus.return_value = "테스트 메시지"

        action = CopyMessageAction(extractor)

        with patch("kakaotalk_a11y_client.message_actions.copy_action.copy_to_clipboard", return_value=True) as mock_copy:
            with patch("kakaotalk_a11y_client.message_actions.copy_action.speak") as mock_speak:
                action.execute()

                mock_copy.assert_called_once_with("테스트 메시지")
                mock_speak.assert_called_once_with("복사됨")

    def test_execute_no_text(self):
        """텍스트 없을 때"""
        from kakaotalk_a11y_client.message_actions.copy_action import CopyMessageAction

        extractor = Mock()
        extractor.extract_from_current_focus.return_value = None

        action = CopyMessageAction(extractor)

        with patch("kakaotalk_a11y_client.message_actions.copy_action.speak") as mock_speak:
            action.execute()
            mock_speak.assert_called_once_with("메시지 없음")

    def test_execute_clipboard_fail(self):
        """클립보드 실패"""
        from kakaotalk_a11y_client.message_actions.copy_action import CopyMessageAction

        extractor = Mock()
        extractor.extract_from_current_focus.return_value = "테스트"

        action = CopyMessageAction(extractor)

        with patch("kakaotalk_a11y_client.message_actions.copy_action.copy_to_clipboard", return_value=False):
            with patch("kakaotalk_a11y_client.message_actions.copy_action.speak") as mock_speak:
                action.execute()
                mock_speak.assert_called_once_with("복사 실패")


class TestMessageTextExtractor:
    """MessageTextExtractor 테스트"""

    def test_extract_success(self):
        """UIA에서 텍스트 추출 성공"""
        from kakaotalk_a11y_client.message_actions.extractor import MessageTextExtractor

        mock_uia = Mock()
        mock_element = Mock()
        mock_element.CurrentName = "홍길동, 오후 2:30\n안녕하세요"
        mock_uia.GetFocusedElement.return_value = mock_element

        extractor = MessageTextExtractor(mock_uia)
        result = extractor.extract_from_current_focus()

        assert result == "홍길동, 오후 2:30\n안녕하세요"

    def test_extract_no_focus(self):
        """포커스 없을 때"""
        from kakaotalk_a11y_client.message_actions.extractor import MessageTextExtractor

        mock_uia = Mock()
        mock_uia.GetFocusedElement.return_value = None

        extractor = MessageTextExtractor(mock_uia)
        result = extractor.extract_from_current_focus()

        assert result is None

    def test_extract_uia_error(self):
        """UIA 접근 오류"""
        from kakaotalk_a11y_client.message_actions.extractor import MessageTextExtractor

        mock_uia = Mock()
        mock_uia.GetFocusedElement.side_effect = Exception("COM 오류")

        extractor = MessageTextExtractor(mock_uia)
        result = extractor.extract_from_current_focus()

        assert result is None
