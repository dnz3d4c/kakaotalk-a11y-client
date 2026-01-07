# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""디버그 핫키 설정 패널

디버그 모드에서만 표시. 일반 HotkeyPanel과 동일한 UX.
"""

import wx
from typing import TYPE_CHECKING, Optional

from ..accessibility import speak
from ..settings import get_settings, DEBUG_HOTKEY_NAMES, DEFAULT_SETTINGS
from .hotkey_panel import format_hotkey, HotkeyChangeDialog

if TYPE_CHECKING:
    from ..main import EmojiClicker


class DebugHotkeyPanel(wx.Panel):
    """디버그 핫키 설정 패널. 우클릭/Enter로 변경, Delete로 기본값 복원."""

    # 컨텍스트 메뉴 ID
    ID_CHANGE = wx.NewIdRef()
    ID_RESTORE = wx.NewIdRef()

    def __init__(self, parent: wx.Window, clicker: "EmojiClicker"):
        super().__init__(parent)
        self.clicker = clicker
        self.settings = get_settings()
        self._pending_changes: dict = {}
        self._hotkey_names = [
            "dump", "profile", "event_monitor",
            "status", "test_navigation", "test_message"
        ]

        self._create_ui()

    def _create_ui(self) -> None:
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 핫키 설정 섹션
        hotkey_box = wx.StaticBox(self, label="디버그 단축키 설정")
        hotkey_sizer = wx.StaticBoxSizer(hotkey_box, wx.VERTICAL)

        # 안내 텍스트
        help_text = wx.StaticText(
            self,
            label="디버그 모드에서만 동작하는 단축키입니다.\n"
                  "변경 후 '저장'을 누르면 즉시 적용됩니다."
        )
        hotkey_sizer.Add(help_text, 0, wx.ALL, 8)

        # ListCtrl
        self.list_ctrl = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN
        )
        self.list_ctrl.InsertColumn(0, "기능", width=180)
        self.list_ctrl.InsertColumn(1, "단축키", width=150)

        # 핫키 데이터 로드
        self._load_hotkeys()

        # 이벤트 바인딩
        self.list_ctrl.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)
        self.list_ctrl.Bind(wx.EVT_KEY_DOWN, self._on_key_down)

        hotkey_sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 8)

        main_sizer.Add(hotkey_sizer, 1, wx.EXPAND | wx.ALL, 8)

        # 하단 버튼
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        restore_btn = wx.Button(self, label="선택 항목 기본값 복원(&R)")
        restore_btn.Bind(wx.EVT_BUTTON, self._on_restore_selected)
        btn_sizer.Add(restore_btn, 0, wx.RIGHT, 8)

        btn_sizer.AddStretchSpacer()

        reset_all_btn = wx.Button(self, label="모든 단축키 기본값 복원(&A)")
        reset_all_btn.Bind(wx.EVT_BUTTON, self._on_reset_all)
        btn_sizer.Add(reset_all_btn, 0)

        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.SetSizer(main_sizer)

    def _load_hotkeys(self) -> None:
        """ListCtrl에 핫키 데이터 표시. _pending_changes 우선 반영."""
        self.list_ctrl.DeleteAllItems()
        hotkeys = self.settings.get_all_debug_hotkeys()

        for i, name in enumerate(self._hotkey_names):
            # pending 변경사항 우선
            if name in self._pending_changes:
                config = self._pending_changes[name]
            else:
                config = hotkeys.get(name, {})

            display_name = DEBUG_HOTKEY_NAMES.get(name, name)
            hotkey_str = format_hotkey(config) if config else "(미설정)"

            self.list_ctrl.InsertItem(i, display_name)
            self.list_ctrl.SetItem(i, 1, hotkey_str)

    def _get_selected_hotkey_name(self) -> Optional[str]:
        idx = self.list_ctrl.GetFirstSelected()
        if idx == -1:
            return None
        return self._hotkey_names[idx]

    def _on_context_menu(self, event: wx.ContextMenuEvent) -> None:
        if self.list_ctrl.GetFirstSelected() == -1:
            return

        menu = wx.Menu()
        menu.Append(self.ID_CHANGE, "단축키 변경(&C)")
        menu.Append(self.ID_RESTORE, "기본값으로 복원(&R)")

        self.Bind(wx.EVT_MENU, self._on_change, id=self.ID_CHANGE)
        self.Bind(wx.EVT_MENU, self._on_restore, id=self.ID_RESTORE)

        self.PopupMenu(menu)
        menu.Destroy()

    def _on_key_down(self, event: wx.KeyEvent) -> None:
        """Enter/Space: 변경, Delete: 복원."""
        key_code = event.GetKeyCode()

        # Enter 또는 Space: 변경 다이얼로그
        if key_code in (wx.WXK_RETURN, wx.WXK_SPACE):
            self._on_change(None)
        # Delete: 기본값 복원
        elif key_code == wx.WXK_DELETE:
            self._on_restore(None)
        else:
            event.Skip()

    def _on_change(self, event) -> None:
        """변경 다이얼로그 표시 후 결과를 _pending_changes에 저장."""
        hotkey_name = self._get_selected_hotkey_name()
        if not hotkey_name:
            return

        display_name = DEBUG_HOTKEY_NAMES.get(hotkey_name, hotkey_name)

        # 현재 설정 (pending 우선)
        if hotkey_name in self._pending_changes:
            current_config = self._pending_changes[hotkey_name]
        else:
            current_config = self.settings.get_debug_hotkey(hotkey_name) or {}

        # 변경 다이얼로그 (HotkeyChangeDialog 재사용)
        dlg = HotkeyChangeDialog(self, hotkey_name, display_name, current_config)

        if dlg.ShowModal() == wx.ID_OK:
            new_config = dlg.get_new_config()
            if new_config:
                self._pending_changes[hotkey_name] = new_config
                self._load_hotkeys()
                speak(f"{display_name} 단축키 변경됨. 저장 필요.")

        dlg.Destroy()

    def _on_restore(self, event) -> None:
        hotkey_name = self._get_selected_hotkey_name()
        if not hotkey_name:
            return

        self._restore_hotkey(hotkey_name)

    def _on_restore_selected(self, event: wx.CommandEvent) -> None:
        hotkey_name = self._get_selected_hotkey_name()
        if not hotkey_name:
            speak("단축키를 먼저 선택하세요.")
            return

        self._restore_hotkey(hotkey_name)

    def _restore_hotkey(self, hotkey_name: str) -> None:
        """확인 후 기본값을 _pending_changes에 저장."""
        display_name = DEBUG_HOTKEY_NAMES.get(hotkey_name, hotkey_name)
        default_config = DEFAULT_SETTINGS["debug_hotkeys"].get(hotkey_name, {})
        default_str = format_hotkey(default_config) if default_config else "(없음)"

        dlg = wx.MessageDialog(
            self,
            f"'{display_name}' 단축키를 기본값({default_str})으로 복원하시겠습니까?",
            "단축키 복원",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if dlg.ShowModal() == wx.ID_YES:
            import copy
            self._pending_changes[hotkey_name] = copy.deepcopy(default_config)
            self._load_hotkeys()
            speak(f"{display_name} 기본값으로 복원됨. 저장 필요.")

        dlg.Destroy()

    def _on_reset_all(self, event: wx.CommandEvent) -> None:
        dlg = wx.MessageDialog(
            self,
            "모든 디버그 단축키를 기본값으로 복원하시겠습니까?",
            "모든 단축키 복원",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if dlg.ShowModal() == wx.ID_YES:
            import copy
            for name in self._hotkey_names:
                config = DEFAULT_SETTINGS["debug_hotkeys"].get(name, {})
                self._pending_changes[name] = copy.deepcopy(config)

            self._load_hotkeys()
            speak("모든 디버그 단축키 기본값으로 복원됨. 저장 필요.")

        dlg.Destroy()

    def apply_changes(self) -> bool:
        """_pending_changes를 settings에 저장 + 단축키 재등록."""
        if not self._pending_changes:
            return True

        for name, config in self._pending_changes.items():
            self.settings.set_debug_hotkey(name, config["modifiers"], config["key"])

        self._pending_changes.clear()

        if not self.settings.save():
            return False

        # 단축키 재등록
        from ..utils.debug_commands import reload_debug_hotkeys
        reload_debug_hotkeys()

        return True

    def has_changes(self) -> bool:
        return bool(self._pending_changes)
