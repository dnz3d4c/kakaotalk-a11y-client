# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""UIA 신뢰도 판단. NVDA 패턴 - 클래스별 UIA/MSAA 선택."""

import uiautomation as auto

try:
    from comtypes import COMError
except ImportError:
    COMError = Exception

from ..window_finder import KAKAOTALK_MENU_CLASS


# UIA가 잘 동작하는 카카오톡 클래스
KAKAO_GOOD_UIA_CLASSES = [
    "EVA_Window",
    "EVA_Window_Dblclk",
    "EVA_VH_ListControl_Dblclk",
    KAKAOTALK_MENU_CLASS,
]

# UIA가 불안정한 클래스 (무시하거나 폴백)
KAKAO_BAD_UIA_CLASSES = [
    "Chrome_WidgetWin_0",      # 광고 웹뷰
    "Chrome_WidgetWin_1",      # Chromium 내부
    "Chrome_RenderWidgetHostHWND",  # 웹 콘텐츠
]

# UIA를 무시해야 하는 컨트롤 패턴
KAKAO_IGNORE_PATTERNS = [
    {"ControlTypeName": "ListItemControl", "Name": ""},  # 가상 스크롤 placeholder
]


def is_good_uia_element(control: auto.Control) -> bool:
    """UIA 정보 신뢰도 판단. BAD_UIA_CLASSES나 IGNORE_PATTERNS 매칭 시 False."""
    try:
        class_name = control.ClassName or ""

        # 명시적으로 나쁜 클래스
        if class_name in KAKAO_BAD_UIA_CLASSES:
            return False

        # 무시 패턴 체크
        for pattern in KAKAO_IGNORE_PATTERNS:
            match = True
            for key, value in pattern.items():
                if getattr(control, key, None) != value:
                    match = False
                    break
            if match:
                return False

        return True

    except (COMError, Exception):
        return False


def should_use_uia_for_window(hwnd: int) -> bool:
    """UIA/MSAA 선택. BAD_UIA_CLASSES면 False, 기본 True."""
    try:
        import win32gui
        class_name = win32gui.GetClassName(hwnd)
        if class_name in KAKAO_GOOD_UIA_CLASSES:
            return True
        if class_name in KAKAO_BAD_UIA_CLASSES:
            return False
    except Exception:
        pass
    return True  # 기본은 UIA 사용
