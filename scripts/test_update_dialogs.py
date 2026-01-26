# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""업데이트 대화상자 테스트 (전체 앱 실행 없이)"""

import sys
import threading
import time
from pathlib import Path

# src 경로 추가
_src_path = str(Path(__file__).parent.parent / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

import wx

from kakaotalk_a11y_client.updater import UpdateInfo
from kakaotalk_a11y_client.gui.update_dialogs import (
    show_update_available,
    show_release_notes,
    confirm_restart,
    DownloadProgressDialog,
)


def create_mock_update_info() -> UpdateInfo:
    """테스트용 UpdateInfo 생성."""
    return UpdateInfo(
        version="0.6.0",
        current_version="0.5.1",
        release_notes=(
            "## 변경사항\n\n"
            "### 새 기능\n"
            "- 자동 업데이트 기능 추가\n"
            "- 릴리스 노트 표시\n\n"
            "### 개선\n"
            "- 성능 향상\n"
            "- 접근성 개선\n\n"
            "### 버그 수정\n"
            "- 특정 상황에서 오류 발생하던 문제 해결"
        ),
        download_url="https://example.com/test.zip",
    )


def test_update_available() -> None:
    """새 버전 알림 대화상자 테스트"""
    print("\n[테스트] 새 버전 알림 대화상자")
    print("  - '예' 선택 시 True 반환")
    print("  - '아니오' 선택 시 False 반환\n")

    app = wx.App()
    frame = wx.Frame(None, title="업데이트 테스트")

    info = create_mock_update_info()
    result = show_update_available(frame, info)

    print(f"결과: {'업데이트 진행' if result else '취소됨'}")

    frame.Destroy()
    app.Destroy()


def test_release_notes() -> None:
    """릴리스 노트 대화상자 테스트"""
    print("\n[테스트] 릴리스 노트 대화상자")
    print("  - '업데이트' 버튼: True 반환")
    print("  - '취소' 버튼: False 반환\n")

    app = wx.App()
    frame = wx.Frame(None, title="릴리스 노트 테스트")

    info = create_mock_update_info()
    result = show_release_notes(frame, info)

    print(f"결과: {'업데이트 진행' if result else '취소됨'}")

    frame.Destroy()
    app.Destroy()


def test_download_progress() -> None:
    """다운로드 진행률 대화상자 테스트 (Mock)"""
    print("\n[테스트] 다운로드 진행률 대화상자 (Mock)")
    print("  - 3초간 진행률 시뮬레이션")
    print("  - '취소' 버튼으로 중단 가능\n")

    app = wx.App()
    frame = wx.Frame(None, title="다운로드 테스트")

    info = create_mock_update_info()
    dlg = DownloadProgressDialog(frame, info)

    # Mock 다운로드 스레드
    def mock_download():
        """가상 다운로드 시뮬레이션."""
        total = 10 * 1024 * 1024  # 10MB
        downloaded = 0
        chunk = total // 30  # 30단계

        dlg.status_label.SetLabel(f"버전 {info.version} 다운로드 중...")

        while downloaded < total:
            if dlg.cancelled:
                wx.CallAfter(lambda: dlg.EndModal(wx.ID_CANCEL))
                return

            downloaded += chunk
            if downloaded > total:
                downloaded = total

            # UI 업데이트
            def update_ui(d=downloaded, t=total):
                percent = int(d * 100 / t)
                dlg.gauge.SetValue(percent)
                mb_d = d / (1024 * 1024)
                mb_t = t / (1024 * 1024)
                dlg.progress_label.SetLabel(f"{mb_d:.1f} / {mb_t:.1f} MB")

            wx.CallAfter(update_ui)
            time.sleep(0.1)

        # 완료
        dlg.download_path = "/mock/path/update.zip"
        wx.CallAfter(lambda: dlg.EndModal(wx.ID_OK))

    # 다운로드 시작
    thread = threading.Thread(target=mock_download, daemon=True)
    wx.CallAfter(thread.start)

    result = dlg.ShowModal()

    if result == wx.ID_OK:
        print("결과: 다운로드 완료")
    elif result == wx.ID_CANCEL:
        print("결과: 사용자 취소")
    else:
        print("결과: 실패")

    dlg.Destroy()
    frame.Destroy()
    app.Destroy()


def test_restart_confirm() -> None:
    """재시작 확인 대화상자 테스트"""
    print("\n[테스트] 재시작 확인 대화상자")
    print("  - '예' 선택 시 재시작 진행")
    print("  - '아니오' 선택 시 나중에 적용\n")

    app = wx.App()
    frame = wx.Frame(None, title="재시작 확인 테스트")

    result = confirm_restart(frame)

    print(f"결과: {'재시작 진행' if result else '나중에 적용'}")

    frame.Destroy()
    app.Destroy()


def show_menu() -> None:
    """테스트 메뉴 표시."""
    print("\n========================================")
    print("  업데이트 대화상자 테스트")
    print("========================================")
    print("1. 새 버전 알림 대화상자")
    print("2. 릴리스 노트 대화상자")
    print("3. 다운로드 진행률 (Mock)")
    print("4. 재시작 확인 대화상자")
    print("5. 전체 테스트")
    print("0. 종료")
    print("----------------------------------------")


def main() -> None:
    """메인 함수."""
    tests = {
        "1": test_update_available,
        "2": test_release_notes,
        "3": test_download_progress,
        "4": test_restart_confirm,
    }

    while True:
        show_menu()
        choice = input("선택: ").strip()

        if choice == "0":
            print("종료합니다.")
            break
        elif choice == "5":
            # 전체 테스트
            for test_func in tests.values():
                test_func()
                print("\n--- 다음 테스트 ---")
            print("\n전체 테스트 완료")
        elif choice in tests:
            tests[choice]()
        else:
            print("잘못된 선택입니다.")


if __name__ == "__main__":
    main()
