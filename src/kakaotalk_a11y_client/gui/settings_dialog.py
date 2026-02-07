# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""설정 다이얼로그. 상태/핫키/정보 탭 구성."""

import webbrowser

import wx
from typing import TYPE_CHECKING, Optional

from .status_panel import StatusPanel
from .hotkey_panel import HotkeyPanel
from .. import __about__
from ..config import APP_DISPLAY_NAME
from ..settings import get_settings, HOTKEY_NAMES, DEBUG_HOTKEY_NAMES
from ..utils.debug_config import debug_config

if TYPE_CHECKING:
    from ..main import EmojiClicker


class SettingsDialog(wx.Dialog):
    """설정 다이얼로그. ESC로 닫기, 저장 안 한 변경사항 경고."""

    def __init__(self, parent: wx.Window, clicker: "EmojiClicker"):
        super().__init__(
            parent,
            title=f"{APP_DISPLAY_NAME} 설정",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.clicker = clicker
        self.debug_hotkey_panel: Optional[HotkeyPanel] = None

        self._create_ui()
        self._set_initial_size()

        # ESC로 닫기
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def _create_ui(self) -> None:
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 노트북 (탭 컨테이너)
        self.notebook = wx.Notebook(self)

        settings = get_settings()

        # 상태 탭
        self.status_panel = StatusPanel(self.notebook, self.clicker)
        self.notebook.AddPage(self.status_panel, "상태(&T)")

        # 단축키 탭
        self.hotkey_panel = HotkeyPanel(
            self.notebook,
            self.clicker,
            hotkey_names=["scan", "exit"],
            name_map=HOTKEY_NAMES,
            settings_getter=settings.get_all_hotkeys,
            settings_item_getter=settings.get_hotkey,
            settings_setter=settings.set_hotkey,
            default_key="hotkeys",
        )
        self.notebook.AddPage(self.hotkey_panel, "단축키(&K)")

        # 디버그 단축키 탭 (디버그 모드에서만)
        if debug_config.enabled:
            from ..utils.debug_commands import reload_debug_hotkeys
            self.debug_hotkey_panel = HotkeyPanel(
                self.notebook,
                self.clicker,
                hotkey_names=[
                    "dump", "profile", "event_monitor",
                    "status", "test_navigation", "test_message",
                ],
                name_map=DEBUG_HOTKEY_NAMES,
                settings_getter=settings.get_all_debug_hotkeys,
                settings_item_getter=settings.get_debug_hotkey,
                settings_setter=settings.set_debug_hotkey,
                default_key="debug_hotkeys",
                section_label="디버그 단축키 설정",
                help_text="디버그 모드에서만 동작하는 단축키입니다.\n"
                          "변경 후 '저장'을 누르면 즉시 적용됩니다.",
                first_col_width=180,
                on_apply_callback=reload_debug_hotkeys,
            )
            self.notebook.AddPage(self.debug_hotkey_panel, "디버그 단축키(&D)")

        # 정보 탭
        self.about_panel = self._create_about_panel()
        self.notebook.AddPage(self.about_panel, "정보(&A)")

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 8)

        # 버튼
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()

        self.save_btn = wx.Button(self, wx.ID_SAVE, "저장(&S)")
        self.save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        btn_sizer.Add(self.save_btn, 0, wx.RIGHT, 8)

        self.close_btn = wx.Button(self, wx.ID_CLOSE, "닫기(&C)")
        self.close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        btn_sizer.Add(self.close_btn, 0)

        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.SetSizer(main_sizer)

        # 기본 포커스
        self.notebook.SetFocus()

    def _create_about_panel(self) -> wx.Panel:
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # 프로그램 정보 그리드
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=16)
        grid.AddGrowableCol(1)

        info_items = [
            ("프로그램", APP_DISPLAY_NAME),
            ("버전", __about__.__version__),
            ("저작자", __about__.__author__),
            ("라이선스", __about__.__license__),
            ("저작권", __about__.__copyright__),
        ]

        for label, value in info_items:
            label_text = wx.StaticText(panel, label=f"{label}:")
            value_text = wx.StaticText(panel, label=value)
            grid.Add(label_text, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
            grid.Add(value_text, 0, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(grid, 0, wx.ALL, 16)

        # GitHub 버튼
        github_btn = wx.Button(panel, label="GitHub 열기(&G)")
        github_btn.Bind(wx.EVT_BUTTON, self._on_open_github)
        sizer.Add(github_btn, 0, wx.LEFT | wx.BOTTOM, 16)

        panel.SetSizer(sizer)
        return panel

    def _on_open_github(self, event: wx.CommandEvent) -> None:
        webbrowser.open(__about__.__url__)
        from ..accessibility import speak
        speak("GitHub 페이지 열림")

    def _set_initial_size(self) -> None:
        """저장된 크기 또는 기본값 적용. 화면 80% 이내로 제한."""
        from ..settings import get_settings
        settings = get_settings()

        # 저장된 크기 또는 기본값
        saved_size = settings.get("ui.window_size", [500, 400])
        width, height = saved_size

        # 최소 크기
        self.SetMinSize((400, 300))

        # 화면 크기 기준 최대 크기 제한
        display = wx.Display(wx.Display.GetFromWindow(self) or 0)
        screen_rect = display.GetClientArea()
        max_width = min(width, int(screen_rect.width * 0.8))
        max_height = min(height, int(screen_rect.height * 0.8))

        self.SetSize((max_width, max_height))
        self.Centre()

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self._try_close()
        else:
            event.Skip()

    def _on_save(self, event: wx.CommandEvent) -> None:
        """핫키 변경사항 + 창 크기 저장."""
        hotkey_ok = self.hotkey_panel.apply_changes()
        debug_ok = True
        if self.debug_hotkey_panel:
            debug_ok = self.debug_hotkey_panel.apply_changes()

        if hotkey_ok and debug_ok:
            # 창 크기 저장
            from ..settings import get_settings
            settings = get_settings()
            size = self.GetSize()
            settings.set("ui.window_size", [size.width, size.height])
            settings.save()

            from ..accessibility import speak
            speak("설정 저장됨")
        else:
            wx.MessageBox(
                "설정 저장에 실패했습니다.",
                "오류",
                wx.OK | wx.ICON_ERROR,
                self
            )

    def _on_close(self, event: wx.CommandEvent) -> None:
        self._try_close()

    def _has_unsaved_changes(self) -> bool:
        """저장되지 않은 변경사항 있는지 확인."""
        if self.hotkey_panel.has_changes():
            return True
        if self.debug_hotkey_panel and self.debug_hotkey_panel.has_changes():
            return True
        return False

    def _try_close(self) -> None:
        """변경사항 있으면 저장 여부 확인 후 닫기."""
        if self._has_unsaved_changes():
            dlg = wx.MessageDialog(
                self,
                "저장하지 않은 변경사항이 있습니다.\n저장하시겠습니까?",
                "변경사항 저장",
                wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION
            )
            result = dlg.ShowModal()
            dlg.Destroy()

            if result == wx.ID_YES:
                self._on_save(None)
                self._close()
            elif result == wx.ID_NO:
                self._close()
            # CANCEL이면 닫지 않음
        else:
            self._close()

    def _close(self) -> None:
        """타이머 정리 후 모달 종료."""
        self.status_panel.stop_timer()
        self.EndModal(wx.ID_CLOSE)

    def ShowModal(self) -> int:
        """열림 시 TTS 알림 후 모달 표시."""
        from ..accessibility import speak
        speak("설정 창 열림")
        return super().ShowModal()
