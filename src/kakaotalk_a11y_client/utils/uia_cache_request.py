# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""CacheRequest 래퍼 - COM 호출 최적화

GetFocusedElementBuildCache()로 필요한 속성만 한 번에 가져옴.
기존 uiautomation 라이브러리와 호환 유지.

성능 효과:
- 기존: GetFocusedControl() + ControlTypeName + Name = 3+ COM 호출
- 개선: GetFocusedElementBuildCache() = 1 COM 호출
- 예상 개선율: 60-65% COM 호출 감소
"""

from typing import Optional, NamedTuple, Any

try:
    from comtypes import COMError
    from comtypes.client import CreateObject, GetModule

    GetModule("UIAutomationCore.dll")
    from comtypes.gen.UIAutomationClient import (
        CUIAutomation,
        UIA_ControlTypePropertyId,
        UIA_NamePropertyId,
        UIA_ClassNamePropertyId,
        UIA_AutomationIdPropertyId,
    )
    HAS_CACHE_REQUEST = True
except Exception:
    HAS_CACHE_REQUEST = False
    COMError = Exception

from .debug import get_logger

log = get_logger("CacheRequest")


# ControlType ID -> Name 매핑
CONTROL_TYPE_NAMES = {
    50000: "ButtonControl",
    50001: "CalendarControl",
    50002: "CheckBoxControl",
    50003: "ComboBoxControl",
    50004: "EditControl",
    50005: "HyperlinkControl",
    50006: "ImageControl",
    50007: "ListItemControl",
    50008: "ListControl",
    50009: "MenuControl",
    50010: "MenuBarControl",
    50011: "MenuItemControl",
    50012: "ProgressBarControl",
    50013: "RadioButtonControl",
    50014: "ScrollBarControl",
    50015: "SliderControl",
    50016: "SpinnerControl",
    50017: "StatusBarControl",
    50018: "TabControl",
    50019: "TabItemControl",
    50020: "TextControl",
    50021: "ToolBarControl",
    50022: "ToolTipControl",
    50023: "TreeControl",
    50024: "TreeItemControl",
    50025: "CustomControl",
    50026: "GroupControl",
    50027: "ThumbControl",
    50028: "DataGridControl",
    50029: "DataItemControl",
    50030: "DocumentControl",
    50031: "SplitButtonControl",
    50032: "WindowControl",
    50033: "PaneControl",
    50034: "HeaderControl",
    50035: "HeaderItemControl",
    50036: "TableControl",
    50037: "TitleBarControl",
    50038: "SeparatorControl",
}


class CachedFocusInfo(NamedTuple):
    """캐시된 포커스 정보"""
    control_type: int           # ControlType ID
    control_type_name: str      # ControlTypeName (문자열)
    name: str                   # Name
    class_name: str             # ClassName
    automation_id: str          # AutomationId
    raw_element: Any            # IUIAutomationElement (추가 작업용)


class CacheRequestManager:
    """CacheRequest 관리자

    싱글톤으로 사용하여 UIA 객체 재사용.
    """

    def __init__(self):
        self._uia = None
        self._cache_request = None
        self._initialized = False

    def _ensure_initialized(self) -> bool:
        """지연 초기화"""
        if self._initialized:
            return self._uia is not None

        self._initialized = True

        if not HAS_CACHE_REQUEST:
            log.debug("comtypes 미설치 - CacheRequest 비활성화")
            return False

        try:
            self._uia = CreateObject(CUIAutomation)

            # CacheRequest 생성: 필요한 속성만 지정
            self._cache_request = self._uia.CreateCacheRequest()
            self._cache_request.AddProperty(UIA_ControlTypePropertyId)
            self._cache_request.AddProperty(UIA_NamePropertyId)
            self._cache_request.AddProperty(UIA_ClassNamePropertyId)
            self._cache_request.AddProperty(UIA_AutomationIdPropertyId)

            log.info("CacheRequest 초기화 성공")
            return True

        except Exception as e:
            log.warning(f"CacheRequest 초기화 실패: {e}")
            self._uia = None
            return False

    def get_focused_cached(self) -> Optional[CachedFocusInfo]:
        """캐시된 포커스 정보 가져오기

        GetFocusedElementBuildCache() 사용하여 한 번의 COM 호출로
        필요한 모든 속성 수집.

        Returns:
            CachedFocusInfo 또는 None (실패 시)
        """
        if not self._ensure_initialized():
            return None

        try:
            # 핵심: BuildCache로 한 번에 속성 수집
            element = self._uia.GetFocusedElementBuildCache(self._cache_request)

            if not element:
                return None

            # Cached 속성 접근 (추가 COM 호출 없음)
            control_type = element.CachedControlType
            name = element.CachedName or ""
            class_name = element.CachedClassName or ""
            automation_id = element.CachedAutomationId or ""

            # ControlType ID -> Name 변환
            control_type_name = CONTROL_TYPE_NAMES.get(
                control_type, f"Unknown({control_type})"
            )

            return CachedFocusInfo(
                control_type=control_type,
                control_type_name=control_type_name,
                name=name,
                class_name=class_name,
                automation_id=automation_id,
                raw_element=element,
            )

        except COMError as e:
            log.trace(f"COMError in get_focused_cached: {e}")
            return None
        except Exception as e:
            log.trace(f"Error in get_focused_cached: {e}")
            return None


# 싱글톤 인스턴스
_cache_manager: Optional[CacheRequestManager] = None


def get_cache_manager() -> CacheRequestManager:
    """싱글톤 CacheRequestManager 가져오기"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheRequestManager()
    return _cache_manager


def get_focused_with_cache() -> Optional[CachedFocusInfo]:
    """캐시된 포커스 정보 가져오기 (편의 함수)

    CacheRequest 사용 가능하면 사용, 아니면 None 반환.
    호출자가 None 시 기존 방식으로 폴백.
    """
    return get_cache_manager().get_focused_cached()
