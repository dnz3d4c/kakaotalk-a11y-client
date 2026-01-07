# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""카카오톡 창 찾기 모듈"""

import time
import win32gui
import win32con
from typing import Optional
from dataclasses import dataclass

from .config import (
    TIMING_MENU_CACHE_TTL,
    SEARCH_DEPTH_MESSAGE_LIST_CHECK,
    SEARCH_DEPTH_CHAT_LIST,
)

# 카카오톡 창 클래스명 패턴
KAKAOTALK_WINDOW_CLASS = "EVA_Window_Dblclk"
KAKAOTALK_CHILD_CLASS = "EVA_ChildWindow"
KAKAOTALK_LIST_CLASS = "EVA_VH_ListControl_Dblclk"

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
        # EVA_Window_Dblclk 클래스 또는 EVA_Menu 클래스면 카카오톡 창
        return class_name == KAKAOTALK_WINDOW_CLASS or class_name == 'EVA_Menu'
    except Exception:
        return False


def is_kakaotalk_menu_window(hwnd: int) -> bool:
    """EVA_Menu 클래스인지."""
    try:
        class_name = win32gui.GetClassName(hwnd)
        return class_name == 'EVA_Menu'
    except Exception:
        return False


# 메뉴 감지 캐시 (EnumWindows 호출 비용 절감)
_menu_cache: dict = {"hwnd": None, "time": 0.0}


def find_kakaotalk_menu_window() -> Optional[int]:
    """visible한 EVA_Menu 찾기. 캐시 TTL 적용 (EnumWindows 비용 절감)."""
    global _menu_cache
    now = time.time()

    # 캐시 유효하면 바로 반환
    if now - _menu_cache["time"] < TIMING_MENU_CACHE_TTL:
        return _menu_cache["hwnd"]

    # 실제 검색
    hwnd = _find_kakaotalk_menu_window_impl()
    _menu_cache = {"hwnd": hwnd, "time": now}
    return hwnd


def _find_kakaotalk_menu_window_impl() -> Optional[int]:
    """EnumWindows로 EVA_Menu 검색."""
    result = None

    def enum_callback(hwnd, _):
        nonlocal result
        if win32gui.IsWindowVisible(hwnd):
            try:
                class_name = win32gui.GetClassName(hwnd)
                if class_name == 'EVA_Menu':
                    result = hwnd
                    return False  # 찾으면 중단
            except Exception:
                pass
        return True

    try:
        win32gui.EnumWindows(enum_callback, None)
    except Exception:
        pass

    return result


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
