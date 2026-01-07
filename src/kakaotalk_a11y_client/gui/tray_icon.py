# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""시스템 트레이 아이콘"""

import wx
import wx.adv
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import EmojiClicker
    from .main_frame import MainFrame


class TrayIcon(wx.adv.TaskBarIcon):
    """시스템 트레이 아이콘. 더블클릭으로 설정, 우클릭 메뉴 제공."""

    ID_SETTINGS = wx.NewIdRef()
    ID_CHECK_UPDATE = wx.NewIdRef()
    ID_EXIT = wx.NewIdRef()

    def __init__(self, frame: "MainFrame", clicker: "EmojiClicker"):
        super().__init__()
        self.frame = frame
        self.clicker = clicker
        self._setup_icon()
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self.on_left_dclick)

    def _setup_icon(self) -> None:
        icon = wx.Icon()
        icon.CopyFromBitmap(
            wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_OTHER, (16, 16))
        )
        self.SetIcon(icon, "카카오톡 접근성 클라이언트")

    def CreatePopupMenu(self) -> wx.Menu:
        menu = wx.Menu()

        # 설정
        menu.Append(self.ID_SETTINGS, "설정(&S)...")
        self.Bind(wx.EVT_MENU, self.on_settings, id=self.ID_SETTINGS)

        # 업데이트 확인
        menu.Append(self.ID_CHECK_UPDATE, "업데이트 확인(&U)...")
        self.Bind(wx.EVT_MENU, self.on_check_update, id=self.ID_CHECK_UPDATE)

        menu.AppendSeparator()

        # 종료
        menu.Append(self.ID_EXIT, "종료(&X)")
        self.Bind(wx.EVT_MENU, self.on_exit, id=self.ID_EXIT)

        return menu

    def on_left_dclick(self, event: wx.adv.TaskBarIconEvent) -> None:
        self.frame.show_settings_dialog()

    def on_settings(self, event: wx.CommandEvent) -> None:
        self.frame.show_settings_dialog()

    def on_check_update(self, event: wx.CommandEvent) -> None:
        self.frame.check_for_update(manual=True)

    def on_exit(self, event: wx.CommandEvent) -> None:
        self.frame.Close(force=True)
