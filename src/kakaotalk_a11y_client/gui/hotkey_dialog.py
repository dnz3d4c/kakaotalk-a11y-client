# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""핫키 변경 다이얼로그 + 유틸리티 함수."""

import wx
from typing import Optional

from ..accessibility import speak


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
    """{'modifiers': [...], 'key': 'X'} -> 'Ctrl+Alt+X' 형식으로 변환."""
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
    """단축키 변경 입력 다이얼로그. 수정자 키(Ctrl/Alt/Shift/Win) + 일반 키 조합만 허용."""

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
        """키 조합 캡처 후 new_config에 저장. 수정자 없으면 거부."""
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
        return self.new_config
