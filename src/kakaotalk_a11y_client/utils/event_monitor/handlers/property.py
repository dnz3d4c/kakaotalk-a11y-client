# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""PropertyChanged 이벤트 핸들러."""

import time
from typing import Callable, Optional, TYPE_CHECKING

import uiautomation as auto

from ..types import EventType, EventLog
from .base import BaseHandler

if TYPE_CHECKING:
    from ..config import EventMonitorConfig

from ...debug import get_logger
from ....window_finder import filter_kakaotalk_hwnd

log = get_logger("EventMon_Prop")

# comtypes PropertyChanged 인터페이스 import
try:
    from comtypes import COMObject
    from comtypes.client import GetModule
    GetModule("UIAutomationCore.dll")
    from comtypes.gen.UIAutomationClient import (
        IUIAutomationPropertyChangedEventHandler,
        TreeScope_Subtree,
    )
    HAS_PROPERTY_HANDLER = True
except ImportError:
    HAS_PROPERTY_HANDLER = False
    COMObject = object
    IUIAutomationPropertyChangedEventHandler = None
    TreeScope_Subtree = None


# UIA 속성 ID 매핑
PROPERTY_IDS = {
    30005: "Name",
    30006: "AcceleratorKey",
    30007: "AccessKey",
    30008: "HasKeyboardFocus",
    30009: "IsKeyboardFocusable",
    30010: "IsEnabled",
    30011: "AutomationId",
    30012: "ClassName",
    30013: "HelpText",
    30014: "ClickablePoint",
    30015: "Culture",
    30016: "IsControlElement",
    30017: "IsContentElement",
    30018: "LabeledBy",
    30019: "IsPassword",
    30020: "NativeWindowHandle",
    30021: "ItemType",
    30022: "IsOffscreen",
    30023: "Orientation",
    30024: "FrameworkId",
    30025: "IsRequiredForForm",
    30026: "ItemStatus",
    30027: "BoundingRectangle",
    30028: "ProcessId",
    30029: "RuntimeId",
    30030: "LocalizedControlType",
    30031: "DescribedBy",
    30032: "FlowsTo",
    30033: "ProviderDescription",
    30035: "Value.Value",
    30043: "IsSelected",
    30044: "SelectionItem.SelectionContainer",
    30045: "TableItem.RowHeaderItems",
    30046: "TableItem.ColumnHeaderItems",
    30047: "RangeValue.Value",
    30048: "RangeValue.IsReadOnly",
    30049: "RangeValue.Minimum",
    30050: "RangeValue.Maximum",
    30051: "RangeValue.LargeChange",
    30052: "RangeValue.SmallChange",
    30053: "Scroll.HorizontalScrollPercent",
    30054: "Scroll.HorizontalViewSize",
    30055: "Scroll.VerticalScrollPercent",
    30056: "Scroll.VerticalViewSize",
    30057: "Scroll.HorizontallyScrollable",
    30058: "Scroll.VerticallyScrollable",
    30059: "Selection.Selection",
    30060: "Selection.CanSelectMultiple",
    30061: "Selection.IsSelectionRequired",
    30062: "Grid.RowCount",
    30063: "Grid.ColumnCount",
    30064: "GridItem.Row",
    30065: "GridItem.Column",
    30066: "GridItem.RowSpan",
    30067: "GridItem.ColumnSpan",
    30068: "GridItem.ContainingGrid",
    30069: "Dock.DockPosition",
    30070: "ExpandCollapse.ExpandCollapseState",
    30071: "MultipleView.CurrentView",
    30072: "MultipleView.SupportedViews",
    30073: "Window.CanMaximize",
    30074: "Window.CanMinimize",
    30075: "Window.WindowVisualState",
    30076: "Window.WindowInteractionState",
    30077: "Window.IsModal",
    30078: "Window.IsTopmost",
    30079: "Toggle.ToggleState",
    30080: "Transform.CanMove",
    30081: "Transform.CanResize",
    30082: "Transform.CanRotate",
    30091: "PositionInSet",
    30092: "SizeOfSet",
    30093: "Level",
}

# 모니터링할 주요 속성 ID
DEFAULT_PROPERTY_IDS = [
    30005,  # Name
    30008,  # HasKeyboardFocus - 포커스 변경 감지용
    30010,  # IsEnabled
    30022,  # IsOffscreen
    30026,  # ItemStatus
    30035,  # Value.Value
    30043,  # IsSelected
    30079,  # Toggle.ToggleState
]


class _PropertyChangedCOMHandler(COMObject):
    """PropertyChanged COM 콜백."""

    if HAS_PROPERTY_HANDLER:
        _com_interfaces_ = [IUIAutomationPropertyChangedEventHandler]

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def HandlePropertyChangedEvent(self, sender, propertyId, newValue):
        if self._callback and sender:
            try:
                self._callback(sender, propertyId, newValue)
            except Exception:
                pass


class PropertyHandler(BaseHandler):
    """PropertyChanged 이벤트 핸들러."""

    def __init__(
        self,
        callback: Callable[[EventLog], None],
        config: "EventMonitorConfig",
        target_hwnd: Optional[int] = None,
        property_ids: Optional[list[int]] = None,
    ):
        super().__init__(callback, config)
        self._target_hwnd = target_hwnd
        self._property_ids = property_ids or DEFAULT_PROPERTY_IDS
        self._root_element = None

    @property
    def event_type(self) -> EventType:
        return EventType.PROPERTY

    def register(self, uia_client) -> bool:
        """PropertyChanged 이벤트 핸들러 등록."""
        if not HAS_PROPERTY_HANDLER:
            log.warning("PropertyChanged handler not supported (comtypes required)")
            return False

        try:
            self._uia = uia_client

            # 타겟 윈도우 또는 루트
            if self._target_hwnd:
                self._root_element = self._uia.ElementFromHandle(self._target_hwnd)
                if not self._root_element:
                    log.error(f"ElementFromHandle failed: hwnd={self._target_hwnd}")
                    return False
            else:
                self._root_element = self._uia.GetRootElement()

            self._com_handler = _PropertyChangedCOMHandler(
                callback=self._on_property_event
            )

            # 속성 ID 배열 생성
            from ctypes import c_int, POINTER, cast, pointer
            prop_array = (c_int * len(self._property_ids))(*self._property_ids)

            self._uia.AddPropertyChangedEventHandler(
                self._root_element,
                TreeScope_Subtree,
                None,  # cacheRequest
                self._com_handler,
                prop_array,
            )

            prop_names = [PROPERTY_IDS.get(p, str(p)) for p in self._property_ids]
            log.debug(f"PropertyChanged handler registered: {prop_names}")
            return True

        except Exception as e:
            log.error(f"PropertyChanged handler registration failed: {e}")
            self._uia = None
            self._com_handler = None
            self._root_element = None
            return False

    def unregister(self) -> None:
        """PropertyChanged 이벤트 핸들러 해제."""
        try:
            if self._com_handler and self._uia and self._root_element:
                self._uia.RemovePropertyChangedEventHandler(
                    self._root_element,
                    self._com_handler
                )
                log.debug("PropertyChanged handler unregistered")
        except Exception as e:
            log.trace(f"PropertyChanged handler unregister error: {e}")
        finally:
            self._uia = None
            self._com_handler = None
            self._root_element = None

    def _on_property_event(self, sender, property_id: int, new_value) -> None:
        """PropertyChanged 이벤트 처리."""
        try:
            # 카카오톡 필터링
            if self._config.include_only_kakaotalk:
                if not filter_kakaotalk_hwnd(sender):
                    return

            # 속성 이름 조회
            property_name = PROPERTY_IDS.get(property_id, f"Unknown({property_id})")

            # uiautomation Control로 변환
            ctrl = auto.Control(element=sender)
            if not ctrl:
                return

            # 새 값 문자열 변환
            try:
                new_value_str = str(new_value) if new_value is not None else "(None)"
            except Exception:
                new_value_str = "(conversion failed)"

            # TRACE 로깅 (임시 - 테스트용)
            log.trace(
                f"[PropertyChanged] {property_name}={new_value_str} | "
                f"{ctrl.ControlTypeName}: {ctrl.Name[:30] if ctrl.Name else '(no name)'}"
            )

            # EventLog 생성
            event = EventLog(
                timestamp=time.time(),
                event_type=EventType.PROPERTY,
                control_type=ctrl.ControlTypeName or "",
                name=ctrl.Name or "",
                class_name=ctrl.ClassName or "",
                details={
                    "property_id": property_id,
                    "property_name": property_name,
                    "new_value": new_value_str,
                },
                _control=ctrl,
            )

            self._emit(event)

        except Exception as e:
            log.trace(f"PropertyChanged processing error: {e}")
