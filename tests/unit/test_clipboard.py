"""클립보드 유틸 테스트"""
import pytest
from unittest.mock import patch, Mock, MagicMock


class TestClipboard:
    """클립보드 함수 테스트"""

    def test_copy_success(self):
        """복사 성공"""
        mock_clipboard = MagicMock()
        mock_clipboard.Open.return_value = True
        mock_clipboard.SetData.return_value = True

        with patch("wx.TheClipboard", mock_clipboard):
            from kakaotalk_a11y_client.utils.clipboard import copy_to_clipboard

            result = copy_to_clipboard("테스트")

            assert result is True
            mock_clipboard.Open.assert_called_once()
            mock_clipboard.SetData.assert_called_once()
            mock_clipboard.Close.assert_called_once()

    def test_copy_fail_open(self):
        """클립보드 열기 실패"""
        mock_clipboard = MagicMock()
        mock_clipboard.Open.return_value = False

        with patch("wx.TheClipboard", mock_clipboard):
            from kakaotalk_a11y_client.utils.clipboard import copy_to_clipboard

            result = copy_to_clipboard("테스트")

            assert result is False
            mock_clipboard.SetData.assert_not_called()
