# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""핫키 설정 패널

스크린 리더 친화적인 핫키 설정 UI.
ListCtrl + 컨텍스트 메뉴 방식.
"""

import wx
from typing import TYPE_CHECKING, Optional

from ..accessibility import speak
from ..settings import get_settings, HOTKEY_NAMES, DEFAULT_SETTINGS

if TYPE_CHECKING:
    from ..main import EmojiClicker


# 키 코드 → 키 이름 매핑
KEY_CODE_MAP = {
    # 방향키
    wx.WXK_UP: "UP",
    wx.WXK_DOWN: "DOWN",
    wx.WXK_LEFT: "LEFT",
    wx.WXK_RIGHT: "RIGHT",
    # 네비게이션
    wx.WXK_HOME: "HOME",
    wx.WXK_END: "END",
    wx.WXK_PAGEUP: "PAGEUP",
    wx.WXK_PAGEDOWN: "PAGEDOWN",
    wx.WXK_INSERT: "INSERT",
    wx.WXK_DELETE: "DELETE",
    # 기타
    wx.WXK_SPACE: "SPACE",
    wx.WXK_TAB: "TAB",
    wx.WXK_RETURN: "ENTER",
    wx.WXK_ESCAPE: "ESC",
    wx.WXK_BACK: "BACKSPACE",
}


def format_hotkey(hotkey_config: dict) -> str:
    """핫키 설정을 문자열로 포맷"""
    modifiers = hotkey_config.get("modifiers", [])
    key = hotkey_config.get("key", "")

    parts = []
    if "ctrl" in modifiers:
        parts.append("Ctrl")
    if "alt" in modifiers:
        parts.append("Alt")
    if "shift" in modifiers:
        parts.append("Shift")
    if "win" in modifiers:
        parts.append("Win")

    parts.append(key.upper())
    return "+".join(parts)


class HotkeyChangeDialog(wx.Dialog):
    """핫키 변경 다이얼로그"""

    def __init__(self, parent: wx.Window, hotkey_name: str, display_name: str, current_config: dict):
        super().__init__(
            parent,
            title=f"단축키 변경 - {display_name}",
            style=wx.DEFAULT_DIALOG_STYLE
        )
        self.hotkey_name = hotkey_name
        self.display_name = display_name
        self.current_config = current_config
        self.new_config: Optional[dict] = None

        self._create_ui()
        self.Centre()

    def _create_ui(self) -> None:
        """UI 생성"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 현재 값 표시
        current_str = format_hotkey(self.current_config)
        current_label = wx.StaticText(
            self,
            label=f"현재 단축키: {current_str}"
        )
        main_sizer.Add(current_label, 0, wx.ALL, 12)

        # 안내 텍스트
        help_label = wx.StaticText(
            self,
            label="새 단축키를 입력하세요.\nCtrl, Alt, Shift, Win 중 하나 이상 + 키"
        )
        main_sizer.Add(help_label, 0, wx.LEFT | wx.RIGHT, 12)

        # 입력 필드
        self.input_field = wx.TextCtrl(
            self,
            style=wx.TE_READONLY | wx.TE_CENTER,
            size=(250, -1)
        )
        self.input_field.SetHint("여기서 키 조합을 누르세요")
        self.input_field.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        main_sizer.Add(self.input_field, 0, wx.ALL | wx.EXPAND, 12)

        # 상태 텍스트
        self.status_label = wx.StaticText(self, label="")
        self.status_label.SetForegroundColour(wx.Colour(0, 100, 0))
        main_sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        # 버튼
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()

        self.ok_btn = wx.Button(self, wx.ID_OK, "확인(&O)")
        self.ok_btn.Disable()
        btn_sizer.Add(self.ok_btn, 0, wx.RIGHT, 8)

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "취소(&C)")
        btn_sizer.Add(cancel_btn, 0)

        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 12)

        self.SetSizer(main_sizer)
        self.Fit()

        # 포커스 설정
        self.input_field.SetFocus()

    def _on_key_down(self, event: wx.KeyEvent) -> None:
        """키 입력 캡처"""
        key_code = event.GetKeyCode()

        # modifier 키만 누른 경우 무시
        if key_code in (wx.WXK_CONTROL, wx.WXK_ALT, wx.WXK_SHIFT,
                        wx.WXK_WINDOWS_LEFT, wx.WXK_WINDOWS_RIGHT):
            return

        # modifier 확인
        modifiers = []
        if event.ControlDown():
            modifiers.append("ctrl")
        if event.AltDown():
            modifiers.append("alt")
        if event.ShiftDown():
            modifiers.append("shift")
        # Win 키 감지: wx.GetKeyState() 사용
        if wx.GetKeyState(wx.WXK_WINDOWS_LEFT) or wx.GetKeyState(wx.WXK_WINDOWS_RIGHT):
            modifiers.append("win")

        # modifier 없으면 무시
        if not modifiers:
            msg = "수정자 키가 필요합니다"
            self.status_label.SetLabel("Ctrl, Alt, Shift, Win 중 하나 이상 필요")
            self.status_label.SetForegroundColour(wx.Colour(200, 0, 0))
            speak(msg)
            return

        # 키 이름 가져오기
        key_name = ""
        if key_code in KEY_CODE_MAP:
            key_name = KEY_CODE_MAP[key_code]
        elif 65 <= key_code <= 90:  # A-Z
            key_name = chr(key_code)
        elif 48 <= key_code <= 57:  # 0-9
            key_name = chr(key_code)
        elif 0x70 <= key_code <= 0x7B:  # F1-F12
            key_name = f"F{key_code - 0x6F}"
        else:
            msg = "지원하지 않는 키입니다"
            self.status_label.SetLabel("지원하지 않는 키")
            self.status_label.SetForegroundColour(wx.Colour(200, 0, 0))
            speak(msg)
            return

        # 새 핫키 설정
        self.new_config = {"modifiers": modifiers, "key": key_name}
        hotkey_str = format_hotkey(self.new_config)

        self.input_field.SetValue(hotkey_str)
        self.status_label.SetLabel(f"'{hotkey_str}'로 변경됩니다")
        self.status_label.SetForegroundColour(wx.Colour(0, 100, 0))
        self.ok_btn.Enable()
        speak(f"{hotkey_str}로 변경됩니다")

    def get_new_config(self) -> Optional[dict]:
        """새 설정 반환"""
        return self.new_config


class HotkeyPanel(wx.Panel):
    """핫키 설정 패널 - ListCtrl + 컨텍스트 메뉴"""

    # 컨텍스트 메뉴 ID
    ID_CHANGE = wx.NewIdRef()
    ID_RESTORE = wx.NewIdRef()

    def __init__(self, parent: wx.Window, clicker: "EmojiClicker"):
        super().__init__(parent)
        self.clicker = clicker
        self.settings = get_settings()
        self._pending_changes: dict = {}
        self._hotkey_names = ["scan", "reread", "exit"]

        self._create_ui()

    def _create_ui(self) -> None:
        """UI 생성"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 핫키 설정 섹션
        hotkey_box = wx.StaticBox(self, label="단축키 설정")
        hotkey_sizer = wx.StaticBoxSizer(hotkey_box, wx.VERTICAL)

        # 안내 텍스트
        help_text = wx.StaticText(
            self,
            label="단축키를 선택하고 우클릭하여 변경할 수 있습니다."
        )
        hotkey_sizer.Add(help_text, 0, wx.ALL, 8)

        # ListCtrl
        self.list_ctrl = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN
        )
        self.list_ctrl.InsertColumn(0, "기능", width=150)
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
        """핫키 데이터 로드"""
        self.list_ctrl.DeleteAllItems()
        hotkeys = self.settings.get_all_hotkeys()

        for i, name in enumerate(self._hotkey_names):
            # pending 변경사항 우선
            if name in self._pending_changes:
                config = self._pending_changes[name]
            else:
                config = hotkeys.get(name, {})

            display_name = HOTKEY_NAMES.get(name, name)
            hotkey_str = format_hotkey(config)

            self.list_ctrl.InsertItem(i, display_name)
            self.list_ctrl.SetItem(i, 1, hotkey_str)

    def _get_selected_hotkey_name(self) -> Optional[str]:
        """선택된 핫키 이름 반환"""
        idx = self.list_ctrl.GetFirstSelected()
        if idx == -1:
            return None
        return self._hotkey_names[idx]

    def _on_context_menu(self, event: wx.ContextMenuEvent) -> None:
        """컨텍스트 메뉴 표시"""
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
        """키보드 단축키 처리"""
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
        """변경 메뉴 클릭"""
        hotkey_name = self._get_selected_hotkey_name()
        if not hotkey_name:
            return

        display_name = HOTKEY_NAMES.get(hotkey_name, hotkey_name)

        # 현재 설정 (pending 우선)
        if hotkey_name in self._pending_changes:
            current_config = self._pending_changes[hotkey_name]
        else:
            current_config = self.settings.get_hotkey(hotkey_name) or {}

        # 변경 다이얼로그
        dlg = HotkeyChangeDialog(self, hotkey_name, display_name, current_config)

        if dlg.ShowModal() == wx.ID_OK:
            new_config = dlg.get_new_config()
            if new_config:
                self._pending_changes[hotkey_name] = new_config
                self._load_hotkeys()

                from ..accessibility import speak
                speak(f"{display_name} 단축키 변경됨. 저장 필요.")

        dlg.Destroy()

    def _on_restore(self, event) -> None:
        """복원 메뉴 클릭"""
        hotkey_name = self._get_selected_hotkey_name()
        if not hotkey_name:
            return

        self._restore_hotkey(hotkey_name)

    def _on_restore_selected(self, event: wx.CommandEvent) -> None:
        """선택 항목 기본값 복원 버튼"""
        hotkey_name = self._get_selected_hotkey_name()
        if not hotkey_name:
            from ..accessibility import speak
            speak("단축키를 먼저 선택하세요.")
            return

        self._restore_hotkey(hotkey_name)

    def _restore_hotkey(self, hotkey_name: str) -> None:
        """단축키 기본값 복원"""
        display_name = HOTKEY_NAMES.get(hotkey_name, hotkey_name)
        default_config = DEFAULT_SETTINGS["hotkeys"].get(hotkey_name, {})
        default_str = format_hotkey(default_config)

        dlg = wx.MessageDialog(
            self,
            f"'{display_name}' 단축키를 기본값({default_str})으로 복원하시겠습니까?",
            "단축키 복원",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if dlg.ShowModal() == wx.ID_YES:
            self._pending_changes[hotkey_name] = default_config.copy()
            self._load_hotkeys()

            from ..accessibility import speak
            speak(f"{display_name} 기본값으로 복원됨. 저장 필요.")

        dlg.Destroy()

    def _on_reset_all(self, event: wx.CommandEvent) -> None:
        """모든 단축키 기본값 복원"""
        dlg = wx.MessageDialog(
            self,
            "모든 단축키를 기본값으로 복원하시겠습니까?",
            "모든 단축키 복원",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if dlg.ShowModal() == wx.ID_YES:
            for name in self._hotkey_names:
                config = DEFAULT_SETTINGS["hotkeys"].get(name, {})
                self._pending_changes[name] = config.copy()

            self._load_hotkeys()

            from ..accessibility import speak
            speak("모든 단축키 기본값으로 복원됨. 저장 필요.")

        dlg.Destroy()

    def apply_changes(self) -> bool:
        """변경사항 적용"""
        if not self._pending_changes:
            return True

        for name, config in self._pending_changes.items():
            self.settings.set_hotkey(name, config["modifiers"], config["key"])

        self._pending_changes.clear()
        return self.settings.save()

    def has_changes(self) -> bool:
        """변경사항 있는지 확인"""
        return bool(self._pending_changes)
