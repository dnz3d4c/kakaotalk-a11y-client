# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""UIA 접근 추상화 레이어. 비즈니스 로직에서 UIA 직접 호출 제거 목적."""

import threading
from typing import Any, List, Optional, Protocol, runtime_checkable

import pythoncom
import uiautomation as auto

from ..utils.uia_utils import safe_uia_call, get_children_recursive
from ..utils.debug import get_logger

log = get_logger("UIAAdapter")


# Type alias for uiautomation Control (duck typing)
Control = Any


@runtime_checkable
class UIAAdapter(Protocol):
    """UIA 접근 인터페이스. 테스트 시 mock으로 대체 가능."""

    def get_control_from_handle(self, hwnd: int) -> Optional[Control]:
        """윈도우 핸들로 컨트롤 가져오기."""
        ...

    def find_list_control(
        self,
        parent: Control,
        name: str,
        search_depth: int = 4
    ) -> Optional[Control]:
        """부모 컨트롤에서 ListControl 찾기."""
        ...

    def control_exists(self, control: Control, max_seconds: float = 1.0) -> bool:
        """컨트롤 존재 여부 확인."""
        ...

    def get_children(
        self,
        control: Control,
        max_depth: int = 2,
        filter_empty: bool = True
    ) -> List[Control]:
        """자식 컨트롤 목록 가져오기."""
        ...

    def init_com(self) -> None:
        """현재 스레드 COM 초기화."""
        ...

    def uninit_com(self) -> None:
        """현재 스레드 COM 해제."""
        ...

    def get_focused_control(self) -> Optional[Control]:
        """현재 포커스된 컨트롤 반환."""
        ...

    def find_menu_item_control(
        self,
        parent: Control,
        search_depth: int = 3
    ) -> Optional[Control]:
        """부모 컨트롤에서 첫 번째 MenuItem 찾기."""
        ...

    def get_direct_children(self, control: Control) -> List[Control]:
        """컨트롤의 직접 자식 목록 (depth=1)."""
        ...


class UIAAdapterImpl:
    """UIAAdapter 실제 구현. uiautomation 라이브러리 래핑."""

    def __init__(self):
        self._com_initialized: dict[int, bool] = {}  # thread_id -> initialized
        self._lock = threading.Lock()

    def get_control_from_handle(self, hwnd: int) -> Optional[Control]:
        """윈도우 핸들로 컨트롤 가져오기. COMError 안전 래핑."""
        return safe_uia_call(
            lambda: auto.ControlFromHandle(hwnd),
            default=None,
            error_msg="ControlFromHandle"
        )

    def find_list_control(
        self,
        parent: Control,
        name: str,
        search_depth: int = 4
    ) -> Optional[Control]:
        """부모 컨트롤에서 ListControl 찾기."""
        if not parent:
            return None

        return safe_uia_call(
            lambda: parent.ListControl(Name=name, searchDepth=search_depth),
            default=None,
            error_msg=f"ListControl(Name={name})"
        )

    def control_exists(self, control: Control, max_seconds: float = 1.0) -> bool:
        """컨트롤 존재 여부 확인."""
        if not control:
            return False

        return safe_uia_call(
            lambda: control.Exists(maxSearchSeconds=max_seconds),
            default=False,
            error_msg="Exists"
        )

    def get_children(
        self,
        control: Control,
        max_depth: int = 2,
        filter_empty: bool = True
    ) -> List[Control]:
        """자식 컨트롤 목록 가져오기. 기존 get_children_recursive 활용."""
        if not control:
            return []

        return safe_uia_call(
            lambda: get_children_recursive(control, max_depth=max_depth, filter_empty=filter_empty),
            default=[],
            error_msg="get_children"
        )

    def init_com(self) -> None:
        """현재 스레드 COM 초기화. 중복 초기화 방지."""
        thread_id = threading.current_thread().ident
        with self._lock:
            if thread_id not in self._com_initialized or not self._com_initialized[thread_id]:
                try:
                    pythoncom.CoInitialize()
                    self._com_initialized[thread_id] = True
                    log.trace(f"COM initialized (thread={thread_id})")
                except Exception as e:
                    log.warning(f"COM init failed: {e}")

    def uninit_com(self) -> None:
        """현재 스레드 COM 해제."""
        thread_id = threading.current_thread().ident
        with self._lock:
            if self._com_initialized.get(thread_id, False):
                try:
                    pythoncom.CoUninitialize()
                    self._com_initialized[thread_id] = False
                    log.trace(f"COM uninitialized (thread={thread_id})")
                except Exception as e:
                    log.trace(f"COM uninit failed (ignored): {e}")

    def get_focused_control(self) -> Optional[Control]:
        """현재 포커스된 컨트롤 반환."""
        return safe_uia_call(
            lambda: auto.GetFocusedControl(),
            default=None,
            error_msg="GetFocusedControl"
        )

    def find_menu_item_control(
        self,
        parent: Control,
        search_depth: int = 3
    ) -> Optional[Control]:
        """부모 컨트롤에서 첫 번째 MenuItem 찾기."""
        if not parent:
            return None

        return safe_uia_call(
            lambda: parent.MenuItemControl(searchDepth=search_depth),
            default=None,
            error_msg="MenuItemControl"
        )

    def get_direct_children(self, control: Control) -> List[Control]:
        """컨트롤의 직접 자식 목록 (depth=1)."""
        if not control:
            return []

        return safe_uia_call(
            lambda: control.GetChildren(),
            default=[],
            error_msg="GetChildren"
        )


# 싱글톤 인스턴스
_default_adapter: Optional[UIAAdapterImpl] = None
_adapter_lock = threading.Lock()


def get_default_uia_adapter() -> UIAAdapterImpl:
    """기본 UIAAdapter 싱글톤 반환."""
    global _default_adapter
    if _default_adapter is None:
        with _adapter_lock:
            if _default_adapter is None:
                _default_adapter = UIAAdapterImpl()
    return _default_adapter
