# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""상태 표시 패널. 모드/채팅방 상태/통계를 실시간 업데이트."""

import wx
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import EmojiClicker


class StatusPanel(wx.Panel):
    """상태 표시 패널. 500ms 간격으로 clicker 상태 반영."""

    UPDATE_INTERVAL = 500  # ms

    def __init__(self, parent: wx.Window, clicker: "EmojiClicker"):
        super().__init__(parent)
        self.clicker = clicker

        self._create_ui()
        self._start_timer()

    def _create_ui(self) -> None:
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 현재 상태 섹션
        status_box = wx.StaticBox(self, label="현재 상태")
        status_sizer = wx.StaticBoxSizer(status_box, wx.VERTICAL)

        # 그리드로 레이블-값 쌍 배치
        grid = wx.FlexGridSizer(rows=2, cols=2, vgap=8, hgap=16)
        grid.AddGrowableCol(1, 1)

        # 모드
        grid.Add(wx.StaticText(self, label="모드:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.mode_label = wx.StaticText(self, label="일반")
        self.mode_label.SetFont(self.mode_label.GetFont().Bold())
        grid.Add(self.mode_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

        # 채팅방
        grid.Add(wx.StaticText(self, label="채팅방:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.chat_label = wx.StaticText(self, label="연결 안됨")
        grid.Add(self.chat_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

        status_sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 8)
        main_sizer.Add(status_sizer, 0, wx.EXPAND | wx.ALL, 8)

        # 통계 섹션
        stats_box = wx.StaticBox(self, label="통계")
        stats_sizer = wx.StaticBoxSizer(stats_box, wx.VERTICAL)

        stats_grid = wx.FlexGridSizer(rows=2, cols=2, vgap=8, hgap=16)
        stats_grid.AddGrowableCol(1, 1)

        # 스캔 횟수
        stats_grid.Add(wx.StaticText(self, label="스캔 횟수:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.scan_count_label = wx.StaticText(self, label="0회")
        stats_grid.Add(self.scan_count_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

        # 메시지 읽음
        stats_grid.Add(wx.StaticText(self, label="메시지 읽음:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.message_count_label = wx.StaticText(self, label="0개")
        stats_grid.Add(self.message_count_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

        stats_sizer.Add(stats_grid, 0, wx.EXPAND | wx.ALL, 8)
        main_sizer.Add(stats_sizer, 0, wx.EXPAND | wx.ALL, 8)

        # 여백 추가
        main_sizer.AddStretchSpacer()

        self.SetSizer(main_sizer)

    def _start_timer(self) -> None:
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_timer, self.timer)
        self.timer.Start(self.UPDATE_INTERVAL)

    def _on_timer(self, event: wx.TimerEvent) -> None:
        self._update_status()

    def _update_status(self) -> None:
        # 모드 표시
        if self.clicker.mode_manager.in_selection_mode:
            mode = "이모지 선택"
            self.mode_label.SetForegroundColour(wx.Colour(0, 128, 0))
        elif self.clicker.mode_manager.in_context_menu_mode:
            mode = "컨텍스트 메뉴"
            self.mode_label.SetForegroundColour(wx.Colour(0, 0, 128))
        elif self.clicker.mode_manager.in_navigation_mode:
            mode = "메시지 탐색"
            self.mode_label.SetForegroundColour(wx.Colour(0, 100, 0))
        else:
            mode = "일반"
            self.mode_label.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
        self.mode_label.SetLabel(mode)

        # 채팅방 상태
        if self.clicker.mode_manager.in_navigation_mode and self.clicker.mode_manager.current_chat_hwnd:
            self.chat_label.SetLabel("연결됨")
            self.chat_label.SetForegroundColour(wx.Colour(0, 128, 0))
        else:
            self.chat_label.SetLabel("연결 안됨")
            self.chat_label.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))

        # 통계
        from ..settings import get_settings
        settings = get_settings()
        scan_count = settings.get("stats.scan_count", 0)
        message_count = settings.get("stats.message_count", 0)

        self.scan_count_label.SetLabel(f"{scan_count}회")
        self.message_count_label.SetLabel(f"{message_count}개")

    def stop_timer(self) -> None:
        """패널 닫을 때 타이머 정리."""
        if hasattr(self, 'timer') and self.timer.IsRunning():
            self.timer.Stop()
