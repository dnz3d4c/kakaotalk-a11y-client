# SPDX-License-Identifier: MIT
"""WindowFinder 단위 테스트."""

import time
from unittest.mock import patch, MagicMock
import pytest

from kakaotalk_a11y_client import window_finder
from kakaotalk_a11y_client.window_finder import (
    KakaoWindow,
    check_kakaotalk_running,
    find_chat_window,
    find_main_window,
    find_kakaotalk_window,
    find_kakaotalk_menu_window,
    is_kakaotalk_chat_window,
    is_kakaotalk_window,
    is_kakaotalk_menu_window,
    get_active_chat_windows,
    KAKAOTALK_WINDOW_CLASS,
    MAIN_WINDOW_TITLE,
)


@pytest.fixture(autouse=True)
def reset_menu_cache():
    """테스트 간 메뉴 캐시 초기화."""
    window_finder._menu_cache = {"hwnd": None, "time": 0.0}
    yield
    window_finder._menu_cache = {"hwnd": None, "time": 0.0}


class TestWindowFinder:
    """WindowFinder 함수 테스트."""

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_check_kakaotalk_running_true(self, mock_win32gui):
        """카카오톡 창 있을 때 True."""
        def enum_callback(callback, _):
            callback(12345, None)
            return True

        mock_win32gui.EnumWindows.side_effect = enum_callback
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetClassName.return_value = KAKAOTALK_WINDOW_CLASS
        mock_win32gui.GetWindowText.return_value = MAIN_WINDOW_TITLE

        result = check_kakaotalk_running()
        assert result is True

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_check_kakaotalk_running_false(self, mock_win32gui):
        """카카오톡 창 없을 때 False."""
        mock_win32gui.EnumWindows.side_effect = lambda cb, _: None

        result = check_kakaotalk_running()
        assert result is False

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_find_chat_window(self, mock_win32gui):
        """채팅방 창 찾기."""
        def enum_callback(callback, _):
            callback(100, None)  # 메인 창
            callback(200, None)  # 채팅방
            return True

        mock_win32gui.EnumWindows.side_effect = enum_callback
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetClassName.return_value = KAKAOTALK_WINDOW_CLASS
        mock_win32gui.GetWindowText.side_effect = lambda h: MAIN_WINDOW_TITLE if h == 100 else "홍길동"

        result = find_chat_window()
        assert result == 200

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_find_chat_window_none(self, mock_win32gui):
        """채팅방 없을 때 None."""
        def enum_callback(callback, _):
            callback(100, None)
            return True

        mock_win32gui.EnumWindows.side_effect = enum_callback
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetClassName.return_value = KAKAOTALK_WINDOW_CLASS
        mock_win32gui.GetWindowText.return_value = MAIN_WINDOW_TITLE

        result = find_chat_window()
        assert result is None

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_find_main_window(self, mock_win32gui):
        """메인 창 찾기."""
        def enum_callback(callback, _):
            callback(100, None)
            return True

        mock_win32gui.EnumWindows.side_effect = enum_callback
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetClassName.return_value = KAKAOTALK_WINDOW_CLASS
        mock_win32gui.GetWindowText.return_value = MAIN_WINDOW_TITLE

        result = find_main_window()
        assert result == 100

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_find_kakaotalk_window_prefers_chat(self, mock_win32gui):
        """find_kakaotalk_window: 채팅방 우선."""
        def enum_callback(callback, _):
            callback(100, None)  # 메인
            callback(200, None)  # 채팅
            return True

        mock_win32gui.EnumWindows.side_effect = enum_callback
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetClassName.return_value = KAKAOTALK_WINDOW_CLASS
        mock_win32gui.GetWindowText.side_effect = lambda h: MAIN_WINDOW_TITLE if h == 100 else "채팅방"

        result = find_kakaotalk_window()
        assert result == 200  # 채팅방 우선

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_find_kakaotalk_window_fallback_main(self, mock_win32gui):
        """find_kakaotalk_window: 채팅방 없으면 메인."""
        def enum_callback(callback, _):
            callback(100, None)
            return True

        mock_win32gui.EnumWindows.side_effect = enum_callback
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetClassName.return_value = KAKAOTALK_WINDOW_CLASS
        mock_win32gui.GetWindowText.return_value = MAIN_WINDOW_TITLE

        result = find_kakaotalk_window()
        assert result == 100

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_is_kakaotalk_chat_window_true(self, mock_win32gui):
        """채팅방 창 판별 True."""
        mock_win32gui.GetClassName.return_value = KAKAOTALK_WINDOW_CLASS
        mock_win32gui.GetWindowText.return_value = "홍길동"

        result = is_kakaotalk_chat_window(12345)
        assert result is True

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_is_kakaotalk_chat_window_false_main(self, mock_win32gui):
        """메인 창은 채팅방 아님."""
        mock_win32gui.GetClassName.return_value = KAKAOTALK_WINDOW_CLASS
        mock_win32gui.GetWindowText.return_value = MAIN_WINDOW_TITLE

        result = is_kakaotalk_chat_window(12345)
        assert result is False

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_is_kakaotalk_chat_window_false_other(self, mock_win32gui):
        """다른 클래스 창은 채팅방 아님."""
        mock_win32gui.GetClassName.return_value = "OtherClass"
        mock_win32gui.GetWindowText.return_value = "홍길동"

        result = is_kakaotalk_chat_window(12345)
        assert result is False

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_is_kakaotalk_window_true(self, mock_win32gui):
        """카카오톡 창 판별 True."""
        mock_win32gui.GetClassName.return_value = KAKAOTALK_WINDOW_CLASS

        result = is_kakaotalk_window(12345)
        assert result is True

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_is_kakaotalk_window_menu(self, mock_win32gui):
        """EVA_Menu도 카카오톡 창."""
        mock_win32gui.GetClassName.return_value = "EVA_Menu"

        result = is_kakaotalk_window(12345)
        assert result is True

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_is_kakaotalk_window_false(self, mock_win32gui):
        """다른 클래스는 카카오톡 아님."""
        mock_win32gui.GetClassName.return_value = "Notepad"

        result = is_kakaotalk_window(12345)
        assert result is False

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_is_kakaotalk_menu_window(self, mock_win32gui):
        """메뉴 창 판별."""
        mock_win32gui.GetClassName.return_value = "EVA_Menu"
        assert is_kakaotalk_menu_window(12345) is True

        mock_win32gui.GetClassName.return_value = KAKAOTALK_WINDOW_CLASS
        assert is_kakaotalk_menu_window(12345) is False

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_find_kakaotalk_menu_window(self, mock_win32gui):
        """메뉴 창 찾기."""
        def enum_callback(callback, _):
            callback(999, None)
            return True

        mock_win32gui.EnumWindows.side_effect = enum_callback
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetClassName.return_value = "EVA_Menu"

        result = find_kakaotalk_menu_window()
        assert result == 999

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_find_kakaotalk_menu_window_cached(self, mock_win32gui):
        """메뉴 창 캐시 사용."""
        def enum_callback(callback, _):
            callback(888, None)
            return True

        mock_win32gui.EnumWindows.side_effect = enum_callback
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetClassName.return_value = "EVA_Menu"

        # 첫 호출
        result1 = find_kakaotalk_menu_window()
        assert result1 == 888

        # 캐시 히트 (EnumWindows 호출 안 함)
        mock_win32gui.EnumWindows.reset_mock()
        result2 = find_kakaotalk_menu_window()
        assert result2 == 888
        mock_win32gui.EnumWindows.assert_not_called()

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_menu_cache_ttl_expiry(self, mock_win32gui):
        """메뉴 캐시 TTL 만료."""
        def enum_callback(callback, _):
            callback(777, None)
            return True

        mock_win32gui.EnumWindows.side_effect = enum_callback
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetClassName.return_value = "EVA_Menu"

        # 첫 호출
        find_kakaotalk_menu_window()

        # 캐시 만료 시뮬레이션
        window_finder._menu_cache["time"] = time.time() - 1.0

        # 재검색
        mock_win32gui.EnumWindows.reset_mock()
        find_kakaotalk_menu_window()
        mock_win32gui.EnumWindows.assert_called_once()

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_get_active_chat_windows(self, mock_win32gui):
        """활성 채팅방 목록."""
        def enum_callback(callback, _):
            callback(100, None)
            callback(200, None)
            callback(300, None)
            return True

        mock_win32gui.EnumWindows.side_effect = enum_callback
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetClassName.return_value = KAKAOTALK_WINDOW_CLASS
        mock_win32gui.GetWindowText.side_effect = lambda h: {
            100: MAIN_WINDOW_TITLE,
            200: "채팅방1",
            300: "채팅방2",
        }.get(h, "")

        result = get_active_chat_windows()
        assert len(result) == 2
        assert all(w.is_chat for w in result)

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_exclude_titles(self, mock_win32gui):
        """제외할 제목 필터링."""
        def enum_callback(callback, _):
            callback(100, None)
            callback(200, None)
            return True

        mock_win32gui.EnumWindows.side_effect = enum_callback
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetClassName.return_value = KAKAOTALK_WINDOW_CLASS
        mock_win32gui.GetWindowText.side_effect = lambda h: "" if h == 100 else "채팅방"

        result = get_active_chat_windows()
        # 빈 제목은 제외됨
        assert len(result) == 1

    @patch('kakaotalk_a11y_client.window_finder.win32gui')
    def test_exception_handling(self, mock_win32gui):
        """예외 발생 시 안전 처리."""
        mock_win32gui.GetClassName.side_effect = Exception("Win32 Error")

        result = is_kakaotalk_window(12345)
        assert result is False

        result = is_kakaotalk_chat_window(12345)
        assert result is False

        result = is_kakaotalk_menu_window(12345)
        assert result is False


class TestKakaoWindow:
    """KakaoWindow 데이터클래스 테스트."""

    def test_kakao_window_creation(self):
        """KakaoWindow 생성."""
        w = KakaoWindow(hwnd=12345, title="테스트", class_name="EVA_Window_Dblclk", is_chat=True)

        assert w.hwnd == 12345
        assert w.title == "테스트"
        assert w.class_name == "EVA_Window_Dblclk"
        assert w.is_chat is True
