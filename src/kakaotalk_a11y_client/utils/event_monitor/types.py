# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""이벤트 모니터 타입 정의."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class EventType(Enum):
    """UIA 이벤트 타입.

    값은 UIA 이벤트 ID 또는 설명 문자열.
    ID 참고: https://learn.microsoft.com/windows/win32/winauto/uiauto-event-ids
    """
    # 핵심 이벤트
    FOCUS = "FocusChanged"              # 20005
    STRUCTURE = "StructureChanged"      # 20002
    PROPERTY = "PropertyChanged"        # 20004

    # 메뉴 이벤트
    MENU_OPENED = "MenuOpened"          # 20003
    MENU_CLOSED = "MenuClosed"          # 20007
    MENU_MODE_START = "MenuModeStart"   # 20018
    MENU_MODE_END = "MenuModeEnd"       # 20019

    # 창 이벤트
    WINDOW_OPENED = "WindowOpened"      # 20016
    WINDOW_CLOSED = "WindowClosed"      # 20017

    # 알림/라이브 영역
    NOTIFICATION = "Notification"       # 20035
    LIVE_REGION = "LiveRegionChanged"   # 20024


class OutputFormat(Enum):
    """출력 형식."""
    CONSOLE = auto()
    JSON = auto()
    TABLE = auto()


class StructureChangeType(Enum):
    """StructureChanged 이벤트 종류."""
    CHILD_ADDED = 0
    CHILD_REMOVED = 1
    CHILDREN_INVALIDATED = 2
    CHILDREN_BULK_ADDED = 3
    CHILDREN_REORDERED = 4


# 기본 활성화 이벤트 (--debug-events 수동 활성화 시)
DEFAULT_EVENT_TYPES = frozenset({EventType.FOCUS, EventType.STRUCTURE})

# --debug 모드 기본 이벤트 (포커스 + 구조 변경)
DEBUG_DEFAULT_EVENTS = frozenset({
    EventType.FOCUS,
    EventType.STRUCTURE,
})

# --trace 모드 기본 이벤트 (전체 추적)
TRACE_DEFAULT_EVENTS = frozenset({
    EventType.FOCUS,
    EventType.STRUCTURE,
    EventType.PROPERTY,
    EventType.MENU_OPENED,
    EventType.MENU_CLOSED,
    EventType.MENU_MODE_START,
    EventType.MENU_MODE_END,
})

# 모든 이벤트
ALL_EVENT_TYPES = frozenset(EventType)


@dataclass
class EventLog:
    """이벤트 로그 데이터."""
    timestamp: float
    event_type: EventType
    control_type: str
    name: str
    class_name: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    # 원본 컨트롤 (필요 시 접근)
    _control: Optional[Any] = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """JSON 직렬화용 dict 변환."""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "control_type": self.control_type,
            "name": self.name,
            "class_name": self.class_name,
            "details": self.details,
        }
