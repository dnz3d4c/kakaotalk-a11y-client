# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""UIA 이벤트 핸들링. COM 인터페이스 초기화 + 모듈 re-export."""

try:
    from comtypes import COMError, COMObject
    from comtypes.client import CreateObject, GetModule
    # UIA COM 인터페이스 로드 시도
    try:
        GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import (
            CUIAutomation,
            IUIAutomation6,
            IUIAutomationEventHandler,
            IUIAutomationFocusChangedEventHandler,
            IUIAutomationStructureChangedEventHandler,
            TreeScope_Subtree,
            CoalesceEventsOptions_Enabled,
            ConnectionRecoveryBehaviorOptions_Enabled,
        )
        # CUIAutomation8 시도 (IUIAutomation6 지원)
        try:
            from comtypes.gen.UIAutomationClient import CUIAutomation8
            HAS_UIA8 = True
        except ImportError:
            HAS_UIA8 = False
        HAS_COMTYPES = True
        HAS_UIA6 = True
    except ImportError:
        # IUIAutomation6 없음 (Windows 10 1809 미만)
        HAS_UIA8 = False
        try:
            from comtypes.gen.UIAutomationClient import (
                CUIAutomation,
                IUIAutomationEventHandler,
                IUIAutomationFocusChangedEventHandler,
                IUIAutomationStructureChangedEventHandler,
                TreeScope_Subtree,
            )
            HAS_COMTYPES = True
            HAS_UIA6 = False
            CoalesceEventsOptions_Enabled = None
            ConnectionRecoveryBehaviorOptions_Enabled = None
        except Exception:
            HAS_COMTYPES = False
            HAS_UIA6 = False
            CoalesceEventsOptions_Enabled = None
            ConnectionRecoveryBehaviorOptions_Enabled = None
            COMObject = object
            IUIAutomationEventHandler = None
            IUIAutomationFocusChangedEventHandler = None
            IUIAutomationStructureChangedEventHandler = None
            TreeScope_Subtree = None
    except Exception:
        HAS_COMTYPES = False
        HAS_UIA6 = False
        HAS_UIA8 = False
        CoalesceEventsOptions_Enabled = None
        ConnectionRecoveryBehaviorOptions_Enabled = None
        COMObject = object  # 폴백
        IUIAutomationEventHandler = None
        IUIAutomationFocusChangedEventHandler = None
        IUIAutomationStructureChangedEventHandler = None
        TreeScope_Subtree = None
except ImportError:
    HAS_COMTYPES = False
    HAS_UIA6 = False
    HAS_UIA8 = False
    COMError = Exception
    COMObject = object  # 폴백
    CoalesceEventsOptions_Enabled = None
    ConnectionRecoveryBehaviorOptions_Enabled = None
    IUIAutomationEventHandler = None
    IUIAutomationFocusChangedEventHandler = None
    IUIAutomationStructureChangedEventHandler = None
    TreeScope_Subtree = None

from .debug import get_logger

log = get_logger("UIA_Events")


class FocusChangedHandler(COMObject):
    """FocusChanged COM 콜백. 공용 클래스.

    uia_focus_handler와 event_monitor에서 공통으로 사용.
    """

    if HAS_COMTYPES:
        _com_interfaces_ = [IUIAutomationFocusChangedEventHandler]

    def __init__(self, callback, logger=None):
        super().__init__()
        self._callback = callback
        self._log = logger

    def HandleFocusChangedEvent(self, sender):
        if self._callback and sender:
            try:
                self._callback(sender)
            except Exception as e:
                if self._log:
                    self._log.trace(f"FocusChanged callback error: {e}")


class AutomationEventHandler(COMObject):
    """일반 UIA 이벤트 핸들러. MenuOpened 등에 사용."""

    if HAS_COMTYPES:
        _com_interfaces_ = [IUIAutomationEventHandler]

    def __init__(self, callback, logger=None):
        super().__init__()
        self._callback = callback
        self._log = logger

    def HandleAutomationEvent(self, sender, eventId):
        if self._callback and sender:
            try:
                self._callback(sender, eventId)
            except Exception as e:
                if self._log:
                    self._log.trace(f"AutomationEvent callback error: {e}")


def _create_uia_client():
    """UIA 클라이언트 생성. IUIAutomation6 최적화 활성화.

    NVDA 패턴 (UIAHandler/__init__.py:514-516):
    - CoalesceEvents: 중복 이벤트 병합
    - ConnectionRecoveryBehavior: UIA 연결 끊김 시 자동 복구
    """
    # CUIAutomation8 우선 시도 (IUIAutomation6 지원)
    if HAS_UIA8:
        try:
            uia = CreateObject(CUIAutomation8)
            uia6 = uia.QueryInterface(IUIAutomation6)
            uia6.CoalesceEvents = CoalesceEventsOptions_Enabled
            uia6.ConnectionRecoveryBehavior = ConnectionRecoveryBehaviorOptions_Enabled
            log.debug("IUIAutomation6 CoalesceEvents + ConnectionRecoveryBehavior enabled")
            return uia6
        except Exception as e:
            log.debug(f"CUIAutomation8 failed, falling back to CUIAutomation: {e}")

    # 폴백: 기본 CUIAutomation
    return CreateObject(CUIAutomation)


# =============================================================================
# 하위 호환성을 위한 re-export
# =============================================================================

from .uia_focus_handler import (
    FocusEvent,
    FocusMonitor,
    get_focus_monitor,
    start_focus_monitoring,
    stop_focus_monitoring,
)
# FocusChangedHandler는 이 파일에서 직접 정의 (위 참조)

from .uia_message_monitor import (
    StructureChangedHandler,
    MessageEvent,
    MessageListMonitor,
)

__all__ = [
    # COM 플래그
    "HAS_COMTYPES",
    "HAS_UIA6",
    "HAS_UIA8",
    "COMObject",
    "COMError",
    # COM 인터페이스
    "IUIAutomationEventHandler",
    "IUIAutomationFocusChangedEventHandler",
    "IUIAutomationStructureChangedEventHandler",
    "TreeScope_Subtree",
    "CoalesceEventsOptions_Enabled",
    # 유틸리티
    "_create_uia_client",
    # Focus 모니터 (uia_focus_handler)
    "FocusEvent",
    "FocusChangedHandler",
    "AutomationEventHandler",
    "FocusMonitor",
    "get_focus_monitor",
    "start_focus_monitoring",
    "stop_focus_monitoring",
    # Message 모니터 (uia_message_monitor)
    "StructureChangedHandler",
    "MessageEvent",
    "MessageListMonitor",
]
