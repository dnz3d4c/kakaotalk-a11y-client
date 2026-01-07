# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""콘솔 출력 포맷터."""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import EventLog, EventType


# 이벤트 타입별 짧은 태그
EVENT_TYPE_TAGS = {
    "FocusChanged": "FOCUS",
    "StructureChanged": "STRUCT",
    "PropertyChanged": "PROP",
    "Notification": "NOTIFY",
    "WindowOpened": "WIN_OPEN",
    "WindowClosed": "WIN_CLOSE",
    "MenuOpened": "MENU_OPEN",
    "MenuClosed": "MENU_CLOSE",
}


class ConsoleFormatter:
    """콘솔 출력 포맷터."""

    def __init__(self, show_timestamp: bool = True, max_name_length: int = 50):
        self.show_timestamp = show_timestamp
        self.max_name_length = max_name_length

    def format(self, event: "EventLog") -> str:
        """이벤트를 콘솔 출력 문자열로 변환.

        형식: [HH:MM:SS.fff] [TAG] ControlType: Name (ClassName)
        """
        parts = []

        # 타임스탬프
        if self.show_timestamp:
            dt = datetime.fromtimestamp(event.timestamp)
            time_str = dt.strftime("%H:%M:%S") + f".{dt.microsecond // 1000:03d}"
            parts.append(f"[{time_str}]")

        # 이벤트 타입 태그
        tag = EVENT_TYPE_TAGS.get(event.event_type.value, event.event_type.value)
        parts.append(f"[{tag}]")

        # 컨트롤 타입
        ctrl_type = event.control_type.replace("Control", "") if event.control_type else "?"
        parts.append(f"{ctrl_type}:")

        # 이름 (길이 제한)
        name = event.name or "(이름 없음)"
        if len(name) > self.max_name_length:
            name = name[:self.max_name_length - 3] + "..."
        parts.append(name)

        # 클래스 이름
        if event.class_name:
            parts.append(f"({event.class_name})")

        # 추가 정보 (details)
        if event.details:
            # StructureChanged의 change_type
            if "change_type" in event.details:
                parts.append(f"[{event.details['change_type']}]")
            # PropertyChanged의 property_name, old_value, new_value
            if "property_name" in event.details:
                prop = event.details["property_name"]
                old = event.details.get("old_value", "?")
                new = event.details.get("new_value", "?")
                parts.append(f"[{prop}: {old} -> {new}]")

        return " ".join(parts)

    def print(self, event: "EventLog") -> None:
        """이벤트를 콘솔에 출력."""
        print(self.format(event))
