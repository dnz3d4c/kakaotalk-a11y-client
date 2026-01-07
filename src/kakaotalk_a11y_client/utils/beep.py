# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""테스트용 비프음. 모두 비동기 실행."""

import winsound
import threading


def beep_start() -> None:
    threading.Thread(
        target=lambda: winsound.Beep(1000, 200),
        daemon=True
    ).start()


def beep_end() -> None:
    threading.Thread(
        target=lambda: winsound.Beep(500, 200),
        daemon=True
    ).start()


def beep_success() -> None:
    def _beeps():
        winsound.Beep(800, 100)
        winsound.Beep(1200, 150)
    threading.Thread(target=_beeps, daemon=True).start()


def beep_error() -> None:
    def _beeps():
        winsound.Beep(800, 100)
        winsound.Beep(400, 200)
    threading.Thread(target=_beeps, daemon=True).start()
