# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""트레이 아이콘 메뉴 테스트 (전체 앱 실행 없이)"""

import _common

_common.setup()

import wx

from kakaotalk_a11y_client.gui.tray_icon import TrayIcon


class MockClicker:
    """EmojiClicker Mock - TrayIcon에 필요한 최소 속성"""

    running = True
    settings = {}


class MockFrame(wx.Frame):
    """MainFrame Mock - TrayIcon 이벤트 핸들러용"""

    def __init__(self):
        super().__init__(None, title="트레이 테스트 (숨김)")
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def show_settings_dialog(self):
        """설정 메뉴 클릭 시"""
        print("[Mock] 설정 다이얼로그 호출됨")
        wx.MessageBox("설정 다이얼로그 (Mock)", "테스트")

    def check_for_update(self, manual=False):
        """업데이트 확인 메뉴 클릭 시"""
        print(f"[Mock] 업데이트 확인 호출됨 (manual={manual})")
        wx.MessageBox("업데이트 확인 (Mock)", "테스트")

    def on_close(self, event):
        """종료 시 트레이 아이콘 정리"""
        if hasattr(self, "tray") and self.tray:
            self.tray.RemoveIcon()
            self.tray.Destroy()
        event.Skip()


def test_tray_menu():
    """트레이 메뉴 표시 테스트"""
    app = wx.App()
    frame = MockFrame()
    clicker = MockClicker()

    tray = TrayIcon(frame, clicker)
    frame.tray = tray  # 종료 시 정리용

    print("=" * 50)
    print("트레이 아이콘 테스트")
    print("=" * 50)
    print()
    print("트레이 아이콘 생성됨.")
    print("- 우클릭: 메뉴 표시 (설정, 업데이트 확인, 종료)")
    print("- 더블클릭: 설정 다이얼로그")
    print()
    print("메뉴 항목:")
    print("  - 설정(S)... -> MessageBox 표시")
    print("  - 업데이트 확인(U)... -> MessageBox 표시")
    print("  - 종료(X) -> 프로그램 종료")
    print()
    print("종료하려면 트레이 메뉴에서 '종료' 선택")
    print("또는 Ctrl+C")
    print("=" * 50)

    # 창은 숨기고 트레이만 표시
    frame.Show(False)
    app.MainLoop()


if __name__ == "__main__":
    try:
        test_tray_menu()
    finally:
        _common.cleanup()
