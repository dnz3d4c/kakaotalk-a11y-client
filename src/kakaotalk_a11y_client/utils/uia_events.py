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
            IUIAutomationFocusChangedEventHandler,
            IUIAutomationStructureChangedEventHandler,
            TreeScope_Subtree,
            CoalesceEventsOptions_Enabled,
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
                IUIAutomationFocusChangedEventHandler,
                IUIAutomationStructureChangedEventHandler,
                TreeScope_Subtree,
            )
            HAS_COMTYPES = True
            HAS_UIA6 = False
            CoalesceEventsOptions_Enabled = None
        except Exception:
            HAS_COMTYPES = False
            HAS_UIA6 = False
            CoalesceEventsOptions_Enabled = None
            COMObject = object
            IUIAutomationFocusChangedEventHandler = None
            IUIAutomationStructureChangedEventHandler = None
            TreeScope_Subtree = None
    except Exception:
        HAS_COMTYPES = False
        HAS_UIA6 = False
        HAS_UIA8 = False
        CoalesceEventsOptions_Enabled = None
        COMObject = object  # 폴백
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
    IUIAutomationFocusChangedEventHandler = None
    IUIAutomationStructureChangedEventHandler = None
    TreeScope_Subtree = None

from .debug import get_logger

log = get_logger("UIA_Events")


def _create_uia_client():
    """UIA 클라이언트 생성. IUIAutomation6 CoalesceEvents 활성화 시도."""
    # CUIAutomation8 우선 시도 (IUIAutomation6 지원)
    if HAS_UIA8:
        try:
            uia = CreateObject(CUIAutomation8)
            uia6 = uia.QueryInterface(IUIAutomation6)
            uia6.CoalesceEvents = CoalesceEventsOptions_Enabled
            log.debug("IUIAutomation6 CoalesceEvents 활성화 (CUIAutomation8)")
            return uia6
        except Exception as e:
            log.debug(f"CUIAutomation8 실패, CUIAutomation 시도: {e}")

    # 폴백: 기본 CUIAutomation
    return CreateObject(CUIAutomation)


# =============================================================================
# 하위 호환성을 위한 re-export
# =============================================================================

from .uia_focus_handler import (
    FocusEvent,
    FocusChangedHandler,
    FocusMonitor,
    get_focus_monitor,
    start_focus_monitoring,
    stop_focus_monitoring,
)

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
    "IUIAutomationFocusChangedEventHandler",
    "IUIAutomationStructureChangedEventHandler",
    "TreeScope_Subtree",
    "CoalesceEventsOptions_Enabled",
    # 유틸리티
    "_create_uia_client",
    # Focus 모니터 (uia_focus_handler)
    "FocusEvent",
    "FocusChangedHandler",
    "FocusMonitor",
    "get_focus_monitor",
    "start_focus_monitoring",
    "stop_focus_monitoring",
    # Message 모니터 (uia_message_monitor)
    "StructureChangedHandler",
    "MessageEvent",
    "MessageListMonitor",
]
