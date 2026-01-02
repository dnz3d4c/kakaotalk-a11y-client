# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""메인 wx.App 클래스"""

import wx
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import EmojiClicker


class KakaoA11yApp(wx.App):
    """카카오톡 접근성 클라이언트 wx 앱"""

    def __init__(self, clicker: "EmojiClicker"):
        self.clicker = clicker
        super().__init__(redirect=False)

    def OnInit(self) -> bool:
        """앱 초기화 - 메인 프레임 생성"""
        from .main_frame import MainFrame

        self.frame = MainFrame(self.clicker)

        # 5초 후 자동 업데이트 확인
        wx.CallLater(5000, self._check_update_background)

        return True

    def _check_update_background(self) -> None:
        """백그라운드 업데이트 확인"""
        import threading

        def check():
            try:
                from ..updater import check_for_update, is_frozen
                if not is_frozen():
                    return

                info = check_for_update()
                if info:
                    # GUI 스레드에서 알림 표시
                    wx.CallAfter(self._show_update_notification, info)
            except Exception:
                pass  # 조용히 실패

        thread = threading.Thread(target=check, daemon=True)
        thread.start()

    def _show_update_notification(self, info) -> None:
        """업데이트 알림 표시 (GUI 스레드)"""
        from .update_dialogs import run_update_flow, show_update_available

        if show_update_available(self.frame, info):
            run_update_flow(self.frame, info)

    def OnExit(self) -> int:
        """앱 종료"""
        return 0
