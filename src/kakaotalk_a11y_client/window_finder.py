# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""카카오톡 창 찾기 모듈"""

import time
import win32gui
import win32con
from typing import Optional
from dataclasses import dataclass

from .config import (
    SEARCH_DEPTH_MESSAGE_LIST_CHECK,
    SEARCH_DEPTH_CHAT_LIST,
)

# 로거는 함수 내부에서 lazy import (순환 import 방지)
_log = None


def _get_log():
    global _log
    if _log is None:
        from .utils.debug import get_logger
        _log = get_logger("WindowFinder")
    return _log

# 카카오톡 창 클래스명 패턴
KAKAOTALK_WINDOW_CLASS = "EVA_Window_Dblclk"
KAKAOTALK_CHILD_CLASS = "EVA_ChildWindow"
KAKAOTALK_LIST_CLASS = "EVA_VH_ListControl_Dblclk"
KAKAOTALK_MENU_CLASS = "EVA_Menu"  # 컨텍스트 메뉴

# 창 제목 패턴 (win32gui 기준)
# 메인 창: "카카오톡" (정확히 일치)
# 채팅방 창: 상대방 이름 (예: "홍길동")
# 기타 창: 빈 제목, "KakaoTalk Dialog", 배너 등
MAIN_WINDOW_TITLE = "카카오톡"  # 정확히 일치하는 것만
EXCLUDE_TITLES = ["", "KakaoTalk Dialog", "WebStoreBanner Dialog"]  # 제외할 제목


@dataclass
class KakaoWindow:
    """카카오톡 창 정보"""
    hwnd: int
    title: str
    class_name: str
    is_chat: bool  # True: 채팅방, False: 메인창


def check_kakaotalk_running() -> bool:
    windows = _enumerate_kakaotalk_windows()
    return len(windows) > 0


def check_uia_available() -> dict:
    """시스템 UIA 동작 여부. 카카오톡 실행과 무관."""
    result = {
        "available": False,
        "message": "",
        "error_detail": "",
    }

    try:
        import uiautomation as auto

        # GetRootControl()로 기본 UIA 동작 확인
        root = auto.GetRootControl()
        if root:
            result["available"] = True
            result["message"] = "UIA 정상"
        else:
            result["message"] = "화면 읽기 기능이 동작하지 않습니다"
            result["error_detail"] = "GetRootControl() 반환값 없음"

    except ImportError as e:
        result["message"] = "화면 읽기 기능이 동작하지 않습니다"
        result["error_detail"] = f"uiautomation 미설치: {e}"
    except Exception as e:
        result["message"] = "화면 읽기 기능이 동작하지 않습니다"
        result["error_detail"] = f"{type(e).__name__}: {e}"

    return result


def check_uia_accessibility() -> dict:
    """카카오톡 UIA 접근 가능 여부. 실행 여부, 채팅방 여부 포함."""
    result = {
        "accessible": False,
        "kakaotalk_running": False,
        "chat_window_found": False,
        "message": "",
    }

    # 1. 카카오톡 창 찾기
    windows = _enumerate_kakaotalk_windows()
    if not windows:
        result["message"] = "카카오톡이 실행되지 않았습니다"
        return result

    result["kakaotalk_running"] = True

    # 2. 채팅방 창 찾기
    chat_windows = [w for w in windows if w.is_chat]
    if not chat_windows:
        result["message"] = "열린 채팅방이 없습니다"
        result["accessible"] = True  # 카카오톡은 접근 가능
        return result

    result["chat_window_found"] = True

    # 3. UIA로 메시지 목록 접근 가능 여부 확인
    try:
        import uiautomation as auto

        chat_hwnd = chat_windows[0].hwnd
        chat_control = auto.ControlFromHandle(chat_hwnd)

        if chat_control:
            # 메시지 ListControl 찾기
            msg_list = chat_control.ListControl(
                ClassName=KAKAOTALK_LIST_CLASS, searchDepth=SEARCH_DEPTH_MESSAGE_LIST_CHECK
            )
            if msg_list.Exists(maxSearchSeconds=1):
                result["accessible"] = True
                result["message"] = "카카오톡 접근 가능"
            else:
                result["accessible"] = True
                result["message"] = "채팅방은 찾았으나 메시지 목록 접근 불가"
        else:
            result["accessible"] = True
            result["message"] = "UIA 컨트롤 생성 실패"

    except ImportError:
        result["accessible"] = True
        result["message"] = "uiautomation 미설치 (기본 모드로 동작)"
    except Exception as e:
        result["accessible"] = True
        result["message"] = f"UIA 체크 중 오류: {str(e)[:50]}"

    return result


def find_chat_window() -> Optional[int]:
    """첫 번째 열린 채팅방 hwnd. 없으면 None."""
    windows = _enumerate_kakaotalk_windows()
    chat_windows = [w for w in windows if w.is_chat]

    if chat_windows:
        return chat_windows[0].hwnd
    return None


def find_main_window() -> Optional[int]:
    """메인 창 hwnd. 없으면 None."""
    windows = _enumerate_kakaotalk_windows()
    main_windows = [w for w in windows if not w.is_chat]

    if main_windows:
        return main_windows[0].hwnd
    return None


def get_active_chat_windows() -> list[KakaoWindow]:
    windows = _enumerate_kakaotalk_windows()
    return [w for w in windows if w.is_chat]


def find_kakaotalk_window() -> Optional[int]:
    """채팅방 우선, 없으면 메인 창."""
    # 채팅방 창 우선
    chat_hwnd = find_chat_window()
    if chat_hwnd:
        return chat_hwnd

    # 메인 창
    return find_main_window()


def is_kakaotalk_chat_window(hwnd: int) -> bool:
    """채팅방 창인지. 메인 창/대화상자는 False."""
    try:
        class_name = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)

        # 클래스명이 EVA_Window_Dblclk이고
        # 메인 창 제목이 아니고, 제외 목록에 없는 것
        if class_name == KAKAOTALK_WINDOW_CLASS:
            if title not in EXCLUDE_TITLES and title != MAIN_WINDOW_TITLE:
                return True

        return False
    except Exception:
        return False


def is_kakaotalk_window(hwnd: int) -> bool:
    """메인/채팅방/메뉴 모두 포함."""
    try:
        class_name = win32gui.GetClassName(hwnd)
        return class_name == KAKAOTALK_WINDOW_CLASS or class_name == KAKAOTALK_MENU_CLASS
    except Exception:
        return False


def is_kakaotalk_menu_window(hwnd: int) -> bool:
    """EVA_Menu 클래스인지."""
    try:
        class_name = win32gui.GetClassName(hwnd)
        return class_name == KAKAOTALK_MENU_CLASS
    except Exception:
        return False


def is_topmost_window(hwnd: int) -> bool:
    """TopMost 창인지 확인 (메뉴, 팝업 등 '떠있는' 창).

    NVDA shouldAcceptEvent 패턴: WS_EX_TOPMOST 플래그로 떠있는 창 감지.
    """
    try:
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        return bool(ex_style & win32con.WS_EX_TOPMOST)
    except Exception:
        return False


def filter_kakaotalk_hwnd(sender, include_menu: bool = True) -> Optional[int]:
    """COM sender에서 카카오톡 창 hwnd 추출. 카카오톡 아니면 None.

    UIA 이벤트 핸들러에서 공통으로 사용하는 필터링 로직.
    hwnd가 없으면 포그라운드 창 → 캐시된 hwnd 순으로 폴백.

    Args:
        sender: COM IUIAutomationElement
        include_menu: EVA_Menu도 허용할지

    Returns:
        검증된 hwnd 또는 None
    """
    hwnd = sender.CurrentNativeWindowHandle
    if hwnd:
        if is_kakaotalk_window(hwnd):
            update_kakaotalk_hwnd_cache(hwnd)  # 캐시 갱신
            return hwnd
        if include_menu and is_kakaotalk_menu_window(hwnd):
            # 메뉴는 캐시하지 않음 (메인/채팅방 hwnd만 캐시)
            return hwnd
        return None

    # hwnd 없으면 포그라운드 체크
    fg_hwnd = win32gui.GetForegroundWindow()
    if fg_hwnd:
        if is_kakaotalk_window(fg_hwnd):
            update_kakaotalk_hwnd_cache(fg_hwnd)  # 캐시 갱신
            return fg_hwnd
        if include_menu and is_kakaotalk_menu_window(fg_hwnd):
            return fg_hwnd

    # 최종 폴백: 캐싱된 hwnd (다른 앱으로 전환해도 5초간 유효)
    cached = get_cached_kakaotalk_hwnd()
    if cached:
        return cached

    return None


# 카카오톡 hwnd 캐시 (포그라운드 폴백 강화)
# ListItem은 hwnd가 없어서 포그라운드에 의존하는데,
# 사용자가 다른 앱으로 전환해도 최근 카카오톡 hwnd로 이벤트 처리 가능
_kakaotalk_hwnd_cache: dict = {"hwnd": None, "time": 0.0}
KAKAOTALK_HWND_CACHE_TTL = 5.0  # 5초


def get_cached_kakaotalk_hwnd() -> Optional[int]:
    """캐싱된 카카오톡 hwnd 반환. TTL 초과 또는 창 닫힘 시 None."""
    global _kakaotalk_hwnd_cache
    log = _get_log()
    cached_hwnd = _kakaotalk_hwnd_cache["hwnd"]
    cached_time = _kakaotalk_hwnd_cache["time"]

    if not cached_hwnd:
        log.trace("hwnd cache: empty")
        return None

    # TTL 체크
    elapsed = time.time() - cached_time
    if elapsed > KAKAOTALK_HWND_CACHE_TTL:
        log.trace(f"hwnd cache: TTL expired ({elapsed:.1f}s)")
        return None

    # 창 유효성 체크
    if not win32gui.IsWindow(cached_hwnd):
        log.trace(f"hwnd cache: window invalid ({cached_hwnd})")
        _kakaotalk_hwnd_cache = {"hwnd": None, "time": 0.0}
        return None

    log.trace(f"hwnd cache: hit ({cached_hwnd}, {elapsed:.1f}s)")
    return cached_hwnd


def update_kakaotalk_hwnd_cache(hwnd: int) -> None:
    """카카오톡 hwnd 캐시 갱신."""
    global _kakaotalk_hwnd_cache
    log = _get_log()
    _kakaotalk_hwnd_cache = {"hwnd": hwnd, "time": time.time()}
    log.trace(f"hwnd cache: updated ({hwnd})")


def find_kakaotalk_menu_window() -> Optional[int]:
    """visible한 EVA_Menu 찾기. 캐시 TTL 적용."""
    # 순환 import 방지를 위해 lazy import
    from .utils.menu_handler import get_menu_handler
    return get_menu_handler().find_menu_window()


def _enumerate_kakaotalk_windows() -> list[KakaoWindow]:
    """visible한 모든 EVA_Window_Dblclk 창 열거."""
    result = []

    def enum_callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True

        try:
            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)

            # EVA_Window_Dblclk 클래스만
            if class_name == KAKAOTALK_WINDOW_CLASS:
                # 제외할 창 건너뛰기
                if title in EXCLUDE_TITLES:
                    return True

                # 메인 창: "카카오톡" 정확히 일치
                # 채팅방 창: 그 외 (상대방 이름)
                is_main = title == MAIN_WINDOW_TITLE
                result.append(
                    KakaoWindow(
                        hwnd=hwnd,
                        title=title,
                        class_name=class_name,
                        is_chat=not is_main,
                    )
                )
        except Exception:
            pass

        return True

    win32gui.EnumWindows(enum_callback, None)
    return result


def get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) 화면 좌표."""
    return win32gui.GetWindowRect(hwnd)


def get_client_rect(hwnd: int) -> tuple[int, int, int, int]:
    """클라이언트 영역 화면 좌표. 타이틀바 제외."""
    client_rect = win32gui.GetClientRect(hwnd)
    left, top = win32gui.ClientToScreen(hwnd, (0, 0))
    right = left + client_rect[2]
    bottom = top + client_rect[3]

    return (left, top, right, bottom)


def bring_window_to_front(hwnd: int) -> bool:
    """최소화 상태면 복원 후 포그라운드로."""
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False
