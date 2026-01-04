# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""카카오톡 창 찾기 모듈"""

import time
import win32gui
import win32con
from typing import Optional
from dataclasses import dataclass

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
    """카카오톡이 실행 중인지 확인한다.

    Returns:
        실행 중이면 True
    """
    windows = _enumerate_kakaotalk_windows()
    return len(windows) > 0


def check_uia_available() -> dict:
    """UIA(UI Automation) 사용 가능 여부만 체크한다.

    카카오톡 실행 여부와 무관하게, 시스템에서 UIA가 동작하는지 확인.

    Returns:
        {
            "available": bool,       # UIA 사용 가능 여부
            "message": str,          # 사용자용 메시지
            "error_detail": str,     # 디버그용 상세 오류
        }
    """
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
    """카카오톡 UIA 접근 가능 여부를 체크한다.

    Returns:
        {
            "accessible": bool,      # UIA 접근 가능 여부
            "kakaotalk_running": bool,  # 카카오톡 실행 여부
            "chat_window_found": bool,  # 채팅방 창 발견 여부
            "message": str           # 상태 메시지
        }
    """
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
                ClassName=KAKAOTALK_LIST_CLASS, searchDepth=3
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
    """열린 채팅방 창의 핸들을 반환한다.

    Returns:
        채팅방 창 핸들(hwnd) 또는 None
    """
    windows = _enumerate_kakaotalk_windows()
    chat_windows = [w for w in windows if w.is_chat]

    if chat_windows:
        return chat_windows[0].hwnd
    return None


def find_main_window() -> Optional[int]:
    """카카오톡 메인 창의 핸들을 반환한다.

    Returns:
        메인 창 핸들(hwnd) 또는 None
    """
    windows = _enumerate_kakaotalk_windows()
    main_windows = [w for w in windows if not w.is_chat]

    if main_windows:
        return main_windows[0].hwnd
    return None


def get_active_chat_windows() -> list[KakaoWindow]:
    """열린 모든 채팅방 목록을 반환한다.

    Returns:
        KakaoWindow 리스트
    """
    windows = _enumerate_kakaotalk_windows()
    return [w for w in windows if w.is_chat]


def find_kakaotalk_window() -> Optional[int]:
    """카카오톡 창 핸들을 찾아 반환한다. (채팅방 우선)

    Returns:
        창 핸들(hwnd) 또는 None
    """
    # 채팅방 창 우선
    chat_hwnd = find_chat_window()
    if chat_hwnd:
        return chat_hwnd

    # 메인 창
    return find_main_window()


def is_kakaotalk_chat_window(hwnd: int) -> bool:
    """카카오톡 채팅방 창인지 확인한다.

    Args:
        hwnd: 창 핸들

    Returns:
        채팅방 창이면 True
    """
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
    """카카오톡 창인지 확인 (메인 창, 채팅방 창, 메뉴 포함).

    Args:
        hwnd: 창 핸들

    Returns:
        카카오톡 창이면 True (메인 창, 채팅방 창, EVA_Menu 모두 포함)
    """
    try:
        class_name = win32gui.GetClassName(hwnd)
        # EVA_Window_Dblclk 클래스 또는 EVA_Menu 클래스면 카카오톡 창
        return class_name == KAKAOTALK_WINDOW_CLASS or class_name == 'EVA_Menu'
    except Exception:
        return False


def is_kakaotalk_menu_window(hwnd: int) -> bool:
    """카카오톡 팝업메뉴 창인지 확인.

    Args:
        hwnd: 창 핸들

    Returns:
        팝업메뉴 창이면 True
    """
    try:
        class_name = win32gui.GetClassName(hwnd)
        return class_name == 'EVA_Menu'
    except Exception:
        return False


# 메뉴 감지 캐시 (EnumWindows 호출 비용 절감)
_menu_cache: dict = {"hwnd": None, "time": 0.0}
_MENU_CACHE_TTL = 0.15  # 150ms 캐싱


def find_kakaotalk_menu_window() -> Optional[int]:
    """현재 열려있는 카카오톡 팝업메뉴 창 찾기.

    GetForegroundWindow()와 달리, visible한 모든 창 중에서 찾음.
    팝업메뉴는 오버레이로 표시되어 포그라운드가 아닐 수 있음.

    캐싱: 150ms 이내 재호출 시 이전 결과 반환 (EnumWindows 비용 절감)

    Returns:
        팝업메뉴 창 핸들 또는 None
    """
    global _menu_cache
    now = time.time()

    # 캐시 유효하면 바로 반환
    if now - _menu_cache["time"] < _MENU_CACHE_TTL:
        return _menu_cache["hwnd"]

    # 실제 검색
    hwnd = _find_kakaotalk_menu_window_impl()
    _menu_cache = {"hwnd": hwnd, "time": now}
    return hwnd


def _find_kakaotalk_menu_window_impl() -> Optional[int]:
    """메뉴 창 찾기 실제 구현 (EnumWindows 호출)."""
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
    """모든 카카오톡 창을 열거한다.

    Returns:
        KakaoWindow 리스트
    """
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
    """창의 좌표와 크기를 반환한다.

    Returns:
        (left, top, right, bottom) 튜플
    """
    return win32gui.GetWindowRect(hwnd)


def get_client_rect(hwnd: int) -> tuple[int, int, int, int]:
    """창의 클라이언트 영역(타이틀바 제외) 좌표를 반환한다.

    Returns:
        (left, top, right, bottom) 튜플 (화면 좌표)
    """
    client_rect = win32gui.GetClientRect(hwnd)
    left, top = win32gui.ClientToScreen(hwnd, (0, 0))
    right = left + client_rect[2]
    bottom = top + client_rect[3]

    return (left, top, right, bottom)


def bring_window_to_front(hwnd: int) -> bool:
    """창을 최상단으로 가져온다.

    Returns:
        성공 여부
    """
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def activate_chat_from_list(skip_first: bool = True) -> dict:
    """채팅방 목록에서 채팅방을 활성화한다.

    메인 창의 채팅 목록에서 채팅방을 더블클릭하여 활성화한다.
    중요 채팅방 보호를 위해 첫 번째 항목은 건너뛸 수 있다.

    Args:
        skip_first: 첫 번째 항목 건너뛰기 (기본 True)

    Returns:
        {
            "success": bool,
            "message": str,
            "chat_name": str or None  # 활성화된 채팅방 이름
        }
    """
    result = {"success": False, "message": "", "chat_name": None}

    try:
        import uiautomation as auto
        import time

        # 1. 메인 창 찾기 및 포그라운드
        main_hwnd = find_main_window()
        if not main_hwnd:
            result["message"] = "카카오톡 메인 창을 찾을 수 없습니다"
            return result

        bring_window_to_front(main_hwnd)
        time.sleep(0.3)  # 창 전환 대기

        # 2. UIA로 메인 창 컨트롤 가져오기
        main_control = auto.ControlFromHandle(main_hwnd)
        if not main_control:
            result["message"] = "UIA 컨트롤 생성 실패"
            return result

        # 3. 채팅 목록 찾기 (Name: "채팅", Class: EVA_VH_ListControl_Dblclk)
        # searchDepth=6: 성능 최적화 (10에서 감소)
        chat_list = main_control.ListControl(
            Name="채팅", ClassName=KAKAOTALK_LIST_CLASS, searchDepth=6
        )
        if not chat_list.Exists(maxSearchSeconds=2):
            result["message"] = "채팅 목록을 찾을 수 없습니다"
            return result

        # 4. 채팅방 항목 가져오기
        items = chat_list.GetChildren()
        if not items:
            result["message"] = "채팅방이 없습니다"
            return result

        # 5. 선택할 인덱스 결정 (skip_first면 1, 아니면 0)
        target_index = 1 if skip_first else 0
        if len(items) <= target_index:
            result["message"] = f"채팅방이 {target_index + 1}개 미만입니다"
            return result

        # 6. 대상 채팅방 선택 및 활성화
        target_item = items[target_index]
        chat_name = target_item.Name or "(이름 없음)"

        # 더블클릭으로 채팅방 열기
        target_item.DoubleClick()
        time.sleep(0.5)  # 창 열리기 대기

        result["success"] = True
        result["message"] = f"채팅방 '{chat_name}' 활성화 완료"
        result["chat_name"] = chat_name

    except ImportError:
        result["message"] = "uiautomation 패키지가 설치되지 않았습니다"
    except Exception as e:
        result["message"] = f"오류: {str(e)[:100]}"

    return result
