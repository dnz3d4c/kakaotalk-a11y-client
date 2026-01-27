# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""메인 프레임 - 숨겨진 상태로 wx.App 유지"""

import threading

import wx
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import EmojiClicker


class MainFrame(wx.Frame):
    """숨겨진 메인 프레임. 트레이 아이콘과 설정 다이얼로그의 부모 역할."""

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
        """설정 다이얼로그 모달로 표시. 이미 열려있으면 포커스."""
        from .settings_dialog import SettingsDialog

        # 이미 열려있으면 포커스
        if self._settings_dialog:
            self._settings_dialog.Raise()
            return

        self._settings_dialog = SettingsDialog(self, self.clicker)
        self._settings_dialog.ShowModal()
        self._settings_dialog.Destroy()
        self._settings_dialog = None

    def check_for_update(self, manual: bool = False) -> None:
        """업데이트 확인. HTTP 요청을 별도 스레드에서 수행."""
        from ..utils.debug import get_logger
        log = get_logger("MainFrame")
        log.debug(f"check_for_update called (manual={manual})")

        try:
            from ..updater import check_for_update as do_check, is_frozen
        except Exception as e:
            import traceback
            log.error(f"updater import failed: {e}\n{traceback.format_exc()}")
            if manual:
                wx.MessageBox(f"업데이트 모듈 로딩 실패:\n{e}", "오류", wx.OK | wx.ICON_ERROR)
            return

        # 수동 확인 시 바쁨 커서 표시
        if manual:
            wx.BeginBusyCursor()

        def check_background():
            nonlocal log
            log.debug("check_background thread started")
            info = None
            error = None
            try:
                frozen = is_frozen()
                log.debug(f"is_frozen={frozen}")
                info = do_check()
                log.debug(f"check_for_update result: {info}")
            except Exception as e:
                import traceback
                log.error(f"update check failed: {e}\n{traceback.format_exc()}")
                error = str(e)
            finally:
                if manual:
                    wx.CallAfter(wx.EndBusyCursor)
                wx.CallAfter(self._on_update_check_complete, info, manual, error)

        thread = threading.Thread(target=check_background, daemon=True)
        thread.start()
        log.debug("check_background thread launched")

    def _on_update_check_complete(
        self, info, manual: bool, error: str = None
    ) -> None:
        """업데이트 확인 완료 후 GUI 스레드에서 결과 처리."""
        from ..utils.debug import get_logger
        from .update_dialogs import run_update_flow, show_update_available

        log = get_logger("MainFrame")
        log.debug(f"_on_update_check_complete called: info={info}, error={error}")

        # 오류 발생 시
        if error:
            if manual:
                wx.MessageBox(
                    f"업데이트 확인 중 오류가 발생했습니다.\n\n{error}",
                    "오류",
                    wx.OK | wx.ICON_ERROR,
                    self,
                )
            return

        if not info:
            log.debug("update check completed: already latest version")
            if manual:
                wx.MessageBox(
                    "현재 최신 버전을 사용 중입니다.",
                    "업데이트 확인",
                    wx.OK | wx.ICON_INFORMATION,
                    self,
                )
            return

        # 업데이트 알림
        log.info(f"update available: {info.version}")
        if show_update_available(self, info):
            run_update_flow(self, info)

    def on_close(self, event: wx.CloseEvent) -> None:
        """CanVeto이면 숨기기, 아니면 트레이/리소스 정리 후 종료."""
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
