# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""메인 프레임 - 숨겨진 상태로 wx.App 유지"""

import wx
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import EmojiClicker


class MainFrame(wx.Frame):
    """숨겨진 메인 프레임 (wx.App 유지용, 설정 다이얼로그 호스트)"""

    def __init__(self, clicker: "EmojiClicker"):
        super().__init__(
            parent=None,
            title="카카오톡 접근성 클라이언트",
            style=wx.FRAME_NO_TASKBAR,  # 작업표시줄 미표시
        )
        self.clicker = clicker
        self._settings_dialog = None

        # 트레이 아이콘 생성
        from .tray_icon import TrayIcon

        self.tray_icon = TrayIcon(self, clicker)

        # 이벤트 바인딩
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # 시작 시 숨김
        self.Hide()

    def show_settings_dialog(self) -> None:
        """설정 다이얼로그 표시"""
        from .settings_dialog import SettingsDialog

        # 이미 열려있으면 포커스
        if self._settings_dialog:
            self._settings_dialog.Raise()
            return

        self._settings_dialog = SettingsDialog(self, self.clicker)
        self._settings_dialog.ShowModal()
        self._settings_dialog.Destroy()
        self._settings_dialog = None

    def on_close(self, event: wx.CloseEvent) -> None:
        """창 닫기 처리"""
        if event.CanVeto():
            # 일반 닫기 요청 → 숨기기
            self.Hide()
            event.Veto()
        else:
            # 강제 종료 (트레이 메뉴 "종료" 등)
            self.tray_icon.RemoveIcon()
            self.tray_icon.Destroy()
            self.clicker.cleanup()
            self.Destroy()
            wx.GetApp().ExitMainLoop()
