# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""이벤트 모니터 타입 정의."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class EventType(Enum):
    """UIA 이벤트 타입."""
    FOCUS = "FocusChanged"
    STRUCTURE = "StructureChanged"
    PROPERTY = "PropertyChanged"
    NOTIFICATION = "Notification"
    WINDOW_OPENED = "WindowOpened"
    WINDOW_CLOSED = "WindowClosed"
    MENU_OPENED = "MenuOpened"
    MENU_CLOSED = "MenuClosed"


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


# 기본 활성화 이벤트 (Property는 기본 비활성)
DEFAULT_EVENT_TYPES = frozenset({EventType.FOCUS, EventType.STRUCTURE})

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
