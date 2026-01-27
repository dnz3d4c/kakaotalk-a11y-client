# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""시스템 트레이 아이콘"""

import wx
import wx.adv
from typing import TYPE_CHECKING

from ..utils.debug import get_logger

if TYPE_CHECKING:
    from ..main import EmojiClicker
    from .main_frame import MainFrame

log = get_logger("TrayIcon")


class TrayIcon(wx.adv.TaskBarIcon):
    """시스템 트레이 아이콘. 더블클릭으로 설정, 우클릭 메뉴 제공."""

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
        """우클릭 메뉴 생성. 메뉴에 직접 이벤트 바인딩."""
        menu = wx.Menu()

        # 설정
        item_settings = menu.Append(wx.ID_ANY, "설정(&S)...")
        menu.Bind(wx.EVT_MENU, self.on_settings, item_settings)

        # 업데이트 확인
        item_update = menu.Append(wx.ID_ANY, "업데이트 확인(&U)...")
        menu.Bind(wx.EVT_MENU, self.on_check_update, item_update)

        menu.AppendSeparator()

        # 종료
        item_exit = menu.Append(wx.ID_ANY, "종료(&X)")
        menu.Bind(wx.EVT_MENU, self.on_exit, item_exit)

        return menu

    def on_left_dclick(self, event: wx.adv.TaskBarIconEvent) -> None:
        self.frame.show_settings_dialog()

    def on_settings(self, event: wx.CommandEvent) -> None:
        log.debug("settings menu clicked")
        self.frame.show_settings_dialog()

    def on_check_update(self, event: wx.CommandEvent) -> None:
        log.debug("check update menu clicked")
        try:
            self.frame.check_for_update(manual=True)
        except Exception as e:
            import traceback
            log.error(f"check_for_update exception: {e}\n{traceback.format_exc()}")
            wx.MessageBox(f"업데이트 확인 실패:\n{e}", "오류", wx.OK | wx.ICON_ERROR)

    def on_exit(self, event: wx.CommandEvent) -> None:
        log.debug("exit menu clicked")
        self.frame.Close(force=True)
