# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""업데이트 관련 대화상자"""

import threading
from typing import TYPE_CHECKING, Optional

import wx

from ..updater import UpdateInfo, apply_and_restart, cleanup, start_download
from ..utils.debug import get_logger

if TYPE_CHECKING:
    from .main_frame import MainFrame

log = get_logger("UpdateDialogs")


def show_update_available(parent: "MainFrame", info: UpdateInfo) -> bool:
    """새 버전 알림. 사용자가 예 선택 시 True."""
    msg = (
        f"새 버전이 있습니다.\n\n"
        f"현재 버전: {info.current_version}\n"
        f"최신 버전: {info.version}\n\n"
        f"업데이트하시겠습니까?"
    )

    dlg = wx.MessageDialog(
        parent,
        msg,
        "업데이트 확인",
        wx.YES_NO | wx.ICON_INFORMATION,
    )

    result = dlg.ShowModal() == wx.ID_YES
    dlg.Destroy()
    return result


class ReleaseNotesDialog(wx.Dialog):
    """릴리스 노트 표시. 업데이트 버튼으로 진행."""

    def __init__(self, parent: wx.Window, info: UpdateInfo):
        super().__init__(
            parent,
            title=f"버전 {info.version} 변경사항",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.info = info
        self._init_ui()
        self.SetSize(500, 400)
        self.CenterOnParent()

    def _init_ui(self) -> None:
        sizer = wx.BoxSizer(wx.VERTICAL)

        # 릴리스 노트 텍스트
        self.text = wx.TextCtrl(
            self,
            value=self.info.release_notes,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
        )
        sizer.Add(self.text, 1, wx.EXPAND | wx.ALL, 10)

        # 버튼
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.update_btn = wx.Button(self, wx.ID_OK, "업데이트(&U)")
        self.cancel_btn = wx.Button(self, wx.ID_CANCEL, "취소(&C)")
        btn_sizer.Add(self.update_btn)
        btn_sizer.Add(self.cancel_btn, 0, wx.LEFT, 10)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.SetSizer(sizer)
        self.update_btn.SetDefault()


def show_release_notes(parent: "MainFrame", info: UpdateInfo) -> bool:
    """릴리스 노트 표시. 사용자가 업데이트 선택 시 True."""
    dlg = ReleaseNotesDialog(parent, info)
    result = dlg.ShowModal() == wx.ID_OK
    dlg.Destroy()
    return result


class DownloadProgressDialog(wx.Dialog):
    """다운로드 진행률 표시. 취소 가능."""

    def __init__(self, parent: wx.Window, info: UpdateInfo):
        super().__init__(
            parent,
            title="업데이트 다운로드",
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        self.info = info
        self.cancelled = False
        self.download_path = None
        self.error_message = None
        self._init_ui()
        self.SetSize(400, 150)
        self.CenterOnParent()

    def _init_ui(self) -> None:
        sizer = wx.BoxSizer(wx.VERTICAL)

        # 상태 텍스트
        self.status_label = wx.StaticText(self, label="다운로드 준비 중...")
        sizer.Add(self.status_label, 0, wx.ALL, 10)

        # 진행률 바
        self.gauge = wx.Gauge(self, range=100, style=wx.GA_HORIZONTAL)
        sizer.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # 진행률 텍스트
        self.progress_label = wx.StaticText(self, label="")
        sizer.Add(self.progress_label, 0, wx.ALL, 10)

        # 취소 버튼
        self.cancel_btn = wx.Button(self, wx.ID_CANCEL, "취소(&C)")
        self.cancel_btn.Bind(wx.EVT_BUTTON, self._on_cancel)
        sizer.Add(self.cancel_btn, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        self.SetSizer(sizer)

    def _on_cancel(self, event: wx.CommandEvent) -> None:
        self.cancelled = True
        self.status_label.SetLabel("취소 중...")
        self.cancel_btn.Enable(False)

    def _progress_callback(self, downloaded: int, total: int) -> bool:
        """워커 스레드에서 호출. False 반환 시 다운로드 취소."""
        if self.cancelled:
            return False

        def update_ui():
            if total > 0:
                percent = int(downloaded * 100 / total)
                self.gauge.SetValue(percent)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                self.progress_label.SetLabel(f"{mb_downloaded:.1f} / {mb_total:.1f} MB")
            else:
                mb_downloaded = downloaded / (1024 * 1024)
                self.progress_label.SetLabel(f"{mb_downloaded:.1f} MB")

        wx.CallAfter(update_ui)
        return True

    def start_download(self) -> None:
        """백그라운드 스레드에서 다운로드 시작."""
        self.status_label.SetLabel(f"버전 {self.info.version} 다운로드 중...")

        def download_worker():
            try:
                self.download_path = start_download(
                    self.info, self._progress_callback
                )
            except Exception as e:
                log.error(f"다운로드 오류: {e}")
                self.error_message = str(e)
            finally:
                wx.CallAfter(self._on_download_complete)

        thread = threading.Thread(target=download_worker, daemon=True)
        thread.start()

    def _on_download_complete(self) -> None:
        """결과에 따라 OK/CANCEL/ABORT로 모달 종료."""
        if self.cancelled:
            cleanup()
            self.EndModal(wx.ID_CANCEL)
        elif self.download_path:
            self.EndModal(wx.ID_OK)
        else:
            self.EndModal(wx.ID_ABORT)


def run_download(parent: "MainFrame", info: UpdateInfo) -> Optional[str]:
    """다운로드 다이얼로그 표시. 성공 시 zip 경로, 실패/취소 시 None."""
    dlg = DownloadProgressDialog(parent, info)

    # 다운로드 시작 후 대화상자 표시
    wx.CallAfter(dlg.start_download)
    result = dlg.ShowModal()

    if result == wx.ID_OK and dlg.download_path:
        path = dlg.download_path
        dlg.Destroy()
        return path
    elif result == wx.ID_ABORT:
        # 다운로드 실패
        wx.MessageBox(
            dlg.error_message or "다운로드에 실패했습니다.",
            "오류",
            wx.OK | wx.ICON_ERROR,
            parent,
        )

    dlg.Destroy()
    return None


def confirm_restart(parent: "MainFrame") -> bool:
    """재시작 확인. 예 선택 시 True."""
    dlg = wx.MessageDialog(
        parent,
        "다운로드가 완료되었습니다.\n\n"
        "지금 프로그램을 종료하고 업데이트를 적용하시겠습니까?",
        "업데이트 적용",
        wx.YES_NO | wx.ICON_QUESTION,
    )

    result = dlg.ShowModal() == wx.ID_YES
    dlg.Destroy()
    return result


def run_update_flow(parent: "MainFrame", info: UpdateInfo) -> None:
    """릴리스 노트 -> 다운로드 -> 재시작 확인 -> 업데이트 적용 순서로 진행."""
    # 1. 릴리스 노트 표시
    if not show_release_notes(parent, info):
        log.info("사용자가 업데이트 취소")
        return

    # 2. 다운로드
    zip_path = run_download(parent, info)
    if not zip_path:
        log.info("다운로드 취소/실패")
        return

    # 3. 재시작 확인
    if not confirm_restart(parent):
        log.info("재시작 취소, 다음 실행 시 적용됨")
        # zip은 임시 폴더에 유지 (다음에 사용 가능)
        return

    # 4. 업데이트 적용 및 종료
    from pathlib import Path

    if apply_and_restart(Path(zip_path)):
        # 앱 종료
        parent.Close(force=True)
    else:
        wx.MessageBox(
            "업데이트 적용에 실패했습니다.\n수동으로 설치해 주세요.",
            "오류",
            wx.OK | wx.ICON_ERROR,
            parent,
        )
        cleanup()
