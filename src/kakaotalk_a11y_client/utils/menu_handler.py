# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""컨텍스트 메뉴 감지, 상태 관리, 항목 처리 통합 모듈.

window_finder.py와 focus_monitor.py에 분산되어 있던 메뉴 관련 로직을 통합.
"""

import time
import threading
import win32gui
from enum import Enum
from typing import Optional, Callable, TYPE_CHECKING

from ..config import TIMING_MENU_CACHE_TTL
from .debug import get_logger
from .uia_workarounds import get_element_name

if TYPE_CHECKING:
    pass

log = get_logger("MenuHandler")

# 카카오톡 메뉴 클래스명
KAKAOTALK_MENU_CLASS = "EVA_Menu"


class MenuType(Enum):
    """메뉴 종류."""
    UNKNOWN = "unknown"
    CHATROOM_MESSAGE = "chatroom_message"  # 채팅방 메시지 우클릭
    FRIEND_TAB_ITEM = "friend_tab_item"    # 친구 탭 항목 우클릭
    CHAT_TAB_ITEM = "chat_tab_item"        # 채팅 탭 항목 우클릭


class MenuHandler:
    """메뉴 감지 및 상태 관리.

    기능:
    - EVA_Menu 창 감지 (EnumWindows + 캐싱)
    - 메뉴 모드 상태 관리 (진입/종료)
    - 메뉴 종류 판별 (채팅방/친구탭/채팅탭)
    - MenuItemControl 포커스 처리
    """

    def __init__(self):
        # 메뉴 상태
        self._in_menu_mode: bool = False
        self._last_menu_hwnd: Optional[int] = None
        self._menu_enter_time: float = 0.0
        self._menu_exit_time: float = 0.0
        self._current_menu_type: MenuType = MenuType.UNKNOWN
        self._lock = threading.Lock()

        # 메뉴 감지 캐시 (EnumWindows 호출 비용 절감)
        self._menu_cache: dict = {"hwnd": None, "time": 0.0}

        # 콜백
        self._speak_callback: Optional[Callable[[str], None]] = None

    def set_speak_callback(self, callback: Callable[[str], None]) -> None:
        """TTS 콜백 설정."""
        self._speak_callback = callback

    # === 메뉴 감지 (window_finder에서 이동) ===

    def find_menu_window(self) -> Optional[int]:
        """visible한 EVA_Menu 찾기. 캐시 TTL 적용."""
        now = time.time()

        # 캐시 유효하면 바로 반환
        if now - self._menu_cache["time"] < TIMING_MENU_CACHE_TTL:
            return self._menu_cache["hwnd"]

        # 실제 검색
        hwnd = self._find_menu_window_impl()
        self._menu_cache = {"hwnd": hwnd, "time": now}
        return hwnd

    def _find_menu_window_impl(self) -> Optional[int]:
        """EnumWindows로 EVA_Menu 검색."""
        result = None

        def enum_callback(hwnd, _):
            nonlocal result
            if win32gui.IsWindowVisible(hwnd):
                try:
                    class_name = win32gui.GetClassName(hwnd)
                    if class_name == KAKAOTALK_MENU_CLASS:
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

    @staticmethod
    def is_menu_window(hwnd: int) -> bool:
        """EVA_Menu 클래스인지."""
        try:
            class_name = win32gui.GetClassName(hwnd)
            return class_name == KAKAOTALK_MENU_CLASS
        except Exception:
            return False

    # === 메뉴 종류 판별 (새 기능) ===

    def detect_menu_type(self, menu_hwnd: int) -> MenuType:
        """현재 컨텍스트에서 메뉴 종류 판별."""
        from ..window_finder import is_kakaotalk_chat_window, MAIN_WINDOW_TITLE

        fg_hwnd = win32gui.GetForegroundWindow()
        if not fg_hwnd:
            return MenuType.UNKNOWN

        # 1. 채팅방 창에서 열린 메뉴
        if is_kakaotalk_chat_window(fg_hwnd):
            return MenuType.CHATROOM_MESSAGE

        # 2. 메인 창에서 열린 메뉴 → 탭 확인
        try:
            title = win32gui.GetWindowText(fg_hwnd)
            if title == MAIN_WINDOW_TITLE:
                active_tab = self._get_active_tab(fg_hwnd)
                if active_tab == "친구":
                    return MenuType.FRIEND_TAB_ITEM
                elif active_tab == "채팅":
                    return MenuType.CHAT_TAB_ITEM
        except Exception:
            pass

        return MenuType.UNKNOWN

    def _get_active_tab(self, main_hwnd: int) -> Optional[str]:
        """메인 창의 현재 선택된 탭 이름 반환."""
        try:
            import uiautomation as auto

            main_control = auto.ControlFromHandle(main_hwnd)
            if not main_control:
                return None

            # TabControl 찾기 (searchDepth 제한)
            tab_control = main_control.TabControl(searchDepth=4)
            if not tab_control.Exists(maxSearchSeconds=0.2):
                return None

            # 선택된 TabItem 찾기
            for tab_item in tab_control.GetChildren():
                if tab_item.ControlTypeName == 'TabItemControl':
                    try:
                        # SelectionItemPattern으로 선택 여부 확인
                        pattern = tab_item.GetSelectionItemPattern()
                        if pattern and pattern.IsSelected:
                            return tab_item.Name
                    except Exception:
                        pass

            return None

        except Exception as e:
            log.trace(f"_get_active_tab error: {e}")
            return None

    # === 메뉴 상태 관리 (focus_monitor에서 이동) ===

    def enter_menu_mode(self, menu_hwnd: int) -> None:
        """메뉴 모드 진입."""
        with self._lock:
            self._in_menu_mode = True
            self._last_menu_hwnd = menu_hwnd
            self._menu_enter_time = time.time()
            self._current_menu_type = self.detect_menu_type(menu_hwnd)
        log.trace(f"menu mode entered: type={self._current_menu_type.value}, hwnd={menu_hwnd}")

    def exit_menu_mode(self) -> None:
        """메뉴 모드 종료."""
        with self._lock:
            self._in_menu_mode = False
            self._menu_exit_time = time.time()
            self._current_menu_type = MenuType.UNKNOWN
        log.trace("menu mode exited")

    @property
    def in_menu_mode(self) -> bool:
        """메뉴 모드 여부."""
        with self._lock:
            return self._in_menu_mode

    @property
    def current_menu_type(self) -> MenuType:
        """현재 메뉴 종류."""
        with self._lock:
            return self._current_menu_type

    @property
    def menu_enter_time(self) -> float:
        """메뉴 진입 시각."""
        with self._lock:
            return self._menu_enter_time

    @property
    def menu_exit_time(self) -> float:
        """메뉴 종료 시각."""
        with self._lock:
            return self._menu_exit_time

    def is_bridging_period(self, threshold: float = 0.2) -> bool:
        """메뉴 종료 직후 브리징 기간인지."""
        with self._lock:
            return time.time() - self._menu_exit_time < threshold

    # === MenuItem 처리 (focus_monitor, uia_workarounds에서 이동) ===

    def is_kakaotalk_menu_item(self, control) -> bool:
        """부모가 카카오톡 메뉴인지 UIA 속성으로 판단."""
        try:
            parent = control.GetParentControl()
            if not parent:
                return False

            # 조건 1: windowClassName == 'EVA_Menu'
            if parent.ClassName == KAKAOTALK_MENU_CLASS:
                return True

            # 조건 2: automationID == 'KakaoTalk Menu'
            if parent.AutomationId == 'KakaoTalk Menu':
                return True

            # 조건 3: ControlType == MenuControl (POPUPMENU)
            if parent.ControlTypeName == 'MenuControl':
                return True

            return False
        except Exception:
            return False

    def get_menu_item_name(self, control) -> Optional[str]:
        """MenuItemControl 이름 추출. MSAA 우선 (KAKAO-002 대응)."""
        try:
            name = control.Name or ""

            # UIA Name이 있으면 그대로 사용
            if name and name != "Menu Item":
                return name

            # MSAA fallback (KAKAO-002: UIA Name이 거의 항상 비어있음)
            actual_name = get_element_name(control)
            if actual_name:
                return actual_name

            return None
        except Exception:
            return None

    def handle_menu_item_focus(
        self,
        control,
        name: str,
        is_duplicate_callback: Callable[[object, str], bool],
    ) -> bool:
        """MenuItemControl 포커스 처리. 성공하면 True.

        Args:
            control: UIA MenuItemControl
            name: control.Name (비어있을 수 있음)
            is_duplicate_callback: 중복 체크 콜백 (control, name) -> bool

        Returns:
            처리 성공 여부 (발화했으면 True)
        """
        # 카카오톡 메뉴 항목인지 확인
        if not self.is_kakaotalk_menu_item(control):
            return False

        # 이름 추출 (MSAA fallback 적용)
        actual_name = self.get_menu_item_name(control)
        if not actual_name:
            log.trace("[SKIP] MenuItemControl: MSAA fallback 후에도 이름 없음")
            return False

        # 중복 체크
        if is_duplicate_callback(control, actual_name):
            return False

        # 발화
        if self._speak_callback:
            self._speak_callback(actual_name)
        log.trace(f"[이벤트] MenuItem: {actual_name[:30]}...")
        return True


# 싱글톤 인스턴스
_menu_handler: Optional[MenuHandler] = None


def get_menu_handler() -> MenuHandler:
    """MenuHandler 싱글톤 반환."""
    global _menu_handler
    if _menu_handler is None:
        _menu_handler = MenuHandler()
    return _menu_handler
