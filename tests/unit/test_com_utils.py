# SPDX-License-Identifier: MIT
"""COM 초기화 유틸리티 테스트."""

import threading
from unittest.mock import patch, MagicMock
import pytest

from kakaotalk_a11y_client.utils import com_utils


@pytest.fixture(autouse=True)
def reset_state():
    """테스트 간 상태 초기화."""
    com_utils._initialized_threads.clear()
    yield
    com_utils._initialized_threads.clear()


class TestComUtils:
    """COM 초기화 유틸리티 테스트."""

    @patch('kakaotalk_a11y_client.utils.com_utils.pythoncom')
    def test_init_com_first_call(self, mock_pythoncom):
        """첫 호출 시 True 반환."""
        result = com_utils.init_com_for_thread()

        assert result is True
        mock_pythoncom.CoInitialize.assert_called_once()

    @patch('kakaotalk_a11y_client.utils.com_utils.pythoncom')
    def test_init_com_duplicate(self, mock_pythoncom):
        """재호출 시 False, CoInitialize 안 함."""
        com_utils.init_com_for_thread()
        mock_pythoncom.reset_mock()

        result = com_utils.init_com_for_thread()

        assert result is False
        mock_pythoncom.CoInitialize.assert_not_called()

    @patch('kakaotalk_a11y_client.utils.com_utils.pythoncom')
    def test_uninit_com_after_init(self, mock_pythoncom):
        """초기화 후 해제 시 True."""
        com_utils.init_com_for_thread()
        mock_pythoncom.reset_mock()

        result = com_utils.uninit_com_for_thread()

        assert result is True
        mock_pythoncom.CoUninitialize.assert_called_once()

    @patch('kakaotalk_a11y_client.utils.com_utils.pythoncom')
    def test_uninit_com_without_init(self, mock_pythoncom):
        """초기화 안 했을 때 해제 시 False."""
        result = com_utils.uninit_com_for_thread()

        assert result is False
        mock_pythoncom.CoUninitialize.assert_not_called()

    @patch('kakaotalk_a11y_client.utils.com_utils.pythoncom')
    def test_is_com_initialized(self, mock_pythoncom):
        """상태 추적."""
        assert com_utils.is_com_initialized() is False

        com_utils.init_com_for_thread()
        assert com_utils.is_com_initialized() is True

        com_utils.uninit_com_for_thread()
        assert com_utils.is_com_initialized() is False

    @patch('kakaotalk_a11y_client.utils.com_utils.pythoncom')
    def test_thread_independence(self, mock_pythoncom):
        """스레드별 독립적 상태."""
        # 메인 스레드에서 초기화
        com_utils.init_com_for_thread()
        assert com_utils.is_com_initialized() is True

        # 다른 스레드에서 확인
        other_thread_initialized = [None]

        def check_other_thread():
            other_thread_initialized[0] = com_utils.is_com_initialized()

        t = threading.Thread(target=check_other_thread)
        t.start()
        t.join()

        # 다른 스레드는 초기화 안 됨
        assert other_thread_initialized[0] is False

    @patch('kakaotalk_a11y_client.utils.com_utils.pythoncom')
    def test_context_manager_new_init(self, mock_pythoncom):
        """컨텍스트 매니저: 새로 초기화 시 해제함."""
        with com_utils.com_thread():
            assert com_utils.is_com_initialized() is True
            mock_pythoncom.CoInitialize.assert_called_once()

        mock_pythoncom.CoUninitialize.assert_called_once()
        assert com_utils.is_com_initialized() is False

    @patch('kakaotalk_a11y_client.utils.com_utils.pythoncom')
    def test_context_manager_already_init(self, mock_pythoncom):
        """컨텍스트 매니저: 이미 초기화 시 해제 안 함."""
        # 먼저 초기화
        com_utils.init_com_for_thread()
        mock_pythoncom.reset_mock()

        with com_utils.com_thread():
            pass

        # 이미 초기화돼 있었으므로 해제 안 함
        mock_pythoncom.CoUninitialize.assert_not_called()
        assert com_utils.is_com_initialized() is True

    @patch('kakaotalk_a11y_client.utils.com_utils.pythoncom')
    def test_decorator_new_init(self, mock_pythoncom):
        """데코레이터: 새로 초기화 시 해제함."""
        @com_utils.ensure_com_initialized
        def my_function():
            return "result"

        result = my_function()

        assert result == "result"
        mock_pythoncom.CoInitialize.assert_called_once()
        mock_pythoncom.CoUninitialize.assert_called_once()

    @patch('kakaotalk_a11y_client.utils.com_utils.pythoncom')
    def test_decorator_already_init(self, mock_pythoncom):
        """데코레이터: 이미 초기화 시 해제 안 함."""
        com_utils.init_com_for_thread()
        mock_pythoncom.reset_mock()

        @com_utils.ensure_com_initialized
        def my_function():
            return "result"

        result = my_function()

        assert result == "result"
        mock_pythoncom.CoInitialize.assert_not_called()
        mock_pythoncom.CoUninitialize.assert_not_called()

    @patch('kakaotalk_a11y_client.utils.com_utils.pythoncom')
    def test_decorator_exception_still_uninits(self, mock_pythoncom):
        """데코레이터: 예외 발생해도 해제함."""
        @com_utils.ensure_com_initialized
        def my_function():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            my_function()

        mock_pythoncom.CoInitialize.assert_called_once()
        mock_pythoncom.CoUninitialize.assert_called_once()
