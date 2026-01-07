# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""StructureChanged 이벤트 핸들러."""

import time
from typing import Callable, Optional, TYPE_CHECKING

import uiautomation as auto

from ..types import EventType, EventLog, StructureChangeType
from .base import BaseHandler

if TYPE_CHECKING:
    from ..config import EventMonitorConfig

# COM 인터페이스 import
from ...uia_events import (
    HAS_COMTYPES,
    COMObject,
    IUIAutomationStructureChangedEventHandler,
    TreeScope_Subtree,
)
from ...debug import get_logger
from ....window_finder import is_kakaotalk_window, is_kakaotalk_menu_window

log = get_logger("EventMon_Struct")


class _StructureChangedCOMHandler(COMObject):
    """StructureChanged COM 콜백."""

    if HAS_COMTYPES:
        _com_interfaces_ = [IUIAutomationStructureChangedEventHandler]

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def HandleStructureChangedEvent(self, sender, changeType, runtimeId):
        if self._callback and sender:
            try:
                self._callback(sender, changeType, runtimeId)
            except Exception:
                pass


class StructureHandler(BaseHandler):
    """StructureChanged 이벤트 핸들러."""

    def __init__(
        self,
        callback: Callable[[EventLog], None],
        config: "EventMonitorConfig",
        target_hwnd: Optional[int] = None,
    ):
        super().__init__(callback, config)
        self._target_hwnd = target_hwnd
        self._root_element = None

    @property
    def event_type(self) -> EventType:
        return EventType.STRUCTURE

    def register(self, uia_client) -> bool:
        """StructureChanged 이벤트 핸들러 등록."""
        if not HAS_COMTYPES:
            return False

        try:
            self._uia = uia_client

            # 타겟 윈도우 지정 시 해당 윈도우만 감시
            if self._target_hwnd:
                self._root_element = self._uia.ElementFromHandle(self._target_hwnd)
                if not self._root_element:
                    log.error(f"ElementFromHandle 실패: hwnd={self._target_hwnd}")
                    return False
            else:
                # 전체 감시 (데스크톱 루트)
                self._root_element = self._uia.GetRootElement()

            self._com_handler = _StructureChangedCOMHandler(
                callback=self._on_structure_event
            )

            self._uia.AddStructureChangedEventHandler(
                self._root_element,
                TreeScope_Subtree,
                None,  # cacheRequest
                self._com_handler
            )

            log.debug(f"StructureChanged 핸들러 등록 완료 (hwnd={self._target_hwnd})")
            return True

        except Exception as e:
            log.error(f"StructureChanged 핸들러 등록 실패: {e}")
            self._uia = None
            self._com_handler = None
            self._root_element = None
            return False

    def unregister(self) -> None:
        """StructureChanged 이벤트 핸들러 해제."""
        try:
            if self._com_handler and self._uia and self._root_element:
                self._uia.RemoveStructureChangedEventHandler(
                    self._root_element,
                    self._com_handler
                )
                log.debug("StructureChanged 핸들러 해제 완료")
        except Exception as e:
            log.trace(f"StructureChanged 핸들러 해제 오류: {e}")
        finally:
            self._uia = None
            self._com_handler = None
            self._root_element = None

    def _on_structure_event(self, sender, change_type: int, runtime_id) -> None:
        """StructureChanged 이벤트 처리."""
        try:
            import win32gui

            # 카카오톡 필터링
            if self._config.include_only_kakaotalk:
                hwnd = sender.CurrentNativeWindowHandle
                if hwnd:
                    if not (
                        is_kakaotalk_window(hwnd) or
                        is_kakaotalk_menu_window(hwnd)
                    ):
                        return
                else:
                    # hwnd 없으면 포그라운드 창 확인
                    fg_hwnd = win32gui.GetForegroundWindow()
                    if not fg_hwnd or not (
                        is_kakaotalk_window(fg_hwnd) or
                        is_kakaotalk_menu_window(fg_hwnd)
                    ):
                        return

            # changeType 변환
            try:
                change_type_enum = StructureChangeType(change_type)
            except ValueError:
                change_type_enum = None

            # uiautomation Control로 변환
            ctrl = auto.Control(element=sender)
            if not ctrl:
                return

            # EventLog 생성
            event = EventLog(
                timestamp=time.time(),
                event_type=EventType.STRUCTURE,
                control_type=ctrl.ControlTypeName or "",
                name=ctrl.Name or "",
                class_name=ctrl.ClassName or "",
                details={
                    "change_type": change_type_enum.name if change_type_enum else str(change_type),
                    "change_type_value": change_type,
                },
                _control=ctrl,
            )

            self._emit(event)

        except Exception as e:
            log.trace(f"StructureChanged 처리 오류: {e}")
