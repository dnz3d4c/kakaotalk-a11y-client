# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""마우스 클릭 모듈"""

import pyautogui
from .config import CLICK_PAUSE, FAILSAFE

# pyautogui 안전 설정
pyautogui.FAILSAFE = FAILSAFE
pyautogui.PAUSE = CLICK_PAUSE


def click_at(x: int, y: int) -> bool:
    """지정 좌표를 클릭한다.

    Args:
        x: 화면 x 좌표
        y: 화면 y 좌표

    Returns:
        성공 여부
    """
    try:
        pyautogui.click(x, y)
        return True
    except pyautogui.FailSafeException:
        # 사용자가 마우스를 화면 모서리로 이동 - 안전 중단
        return False
    except Exception:
        return False


def click_emoji(detection: dict, window_offset: tuple[int, int] = (0, 0)) -> bool:
    """탐지된 이모지를 클릭한다.

    Args:
        detection: detector.detect_emojis()가 반환한 이모지 정보
        window_offset: 캡처 영역의 화면 좌표 오프셋 (left, top)

    Returns:
        성공 여부
    """
    pos = detection["pos"]
    # 캡처 영역 내 상대 좌표를 화면 절대 좌표로 변환
    screen_x = pos[0] + window_offset[0]
    screen_y = pos[1] + window_offset[1]

    return click_at(screen_x, screen_y)
