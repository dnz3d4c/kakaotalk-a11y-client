# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""테스트용 비프음 유틸

테스트 시작/종료를 알리는 비프음 제공.
"""

import winsound
import threading


def beep_start() -> None:
    """테스트 시작 비프음 (높은 톤)"""
    threading.Thread(
        target=lambda: winsound.Beep(1000, 200),
        daemon=True
    ).start()


def beep_end() -> None:
    """테스트 종료 비프음 (낮은 톤)"""
    threading.Thread(
        target=lambda: winsound.Beep(500, 200),
        daemon=True
    ).start()


def beep_success() -> None:
    """성공 비프음 (상승 톤)"""
    def _beeps():
        winsound.Beep(800, 100)
        winsound.Beep(1200, 150)
    threading.Thread(target=_beeps, daemon=True).start()


def beep_error() -> None:
    """에러 비프음 (하강 톤)"""
    def _beeps():
        winsound.Beep(800, 100)
        winsound.Beep(400, 200)
    threading.Thread(target=_beeps, daemon=True).start()
