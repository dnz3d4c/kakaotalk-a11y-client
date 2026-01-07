# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""테이블 출력 포맷터."""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import EventLog

# 이벤트 타입 짧은 태그
EVENT_TAGS = {
    "FocusChanged": "FOCUS",
    "StructureChanged": "STRUCT",
    "PropertyChanged": "PROP",
    "Notification": "NOTIFY",
    "WindowOpened": "WIN+",
    "WindowClosed": "WIN-",
    "MenuOpened": "MENU+",
    "MenuClosed": "MENU-",
}


class TableFormatter:
    """테이블 형식 출력 포맷터."""

    def __init__(
        self,
        show_header: bool = True,
        max_name_length: int = 30,
        max_class_length: int = 20,
    ):
        self.show_header = show_header
        self.max_name_length = max_name_length
        self.max_class_length = max_class_length
        self._header_printed = False

    def _truncate(self, s: str, max_len: int) -> str:
        """문자열 길이 제한."""
        if len(s) > max_len:
            return s[:max_len - 2] + ".."
        return s

    def _get_header(self) -> str:
        """테이블 헤더 생성."""
        header = (
            f"| {'Time':<12} | {'Event':<7} | {'ControlType':<15} | "
            f"{'Name':<{self.max_name_length}} | {'Class':<{self.max_class_length}} |"
        )
        separator = (
            f"|{'-' * 14}|{'-' * 9}|{'-' * 17}|"
            f"{'-' * (self.max_name_length + 2)}|{'-' * (self.max_class_length + 2)}|"
        )
        return f"{header}\n{separator}"

    def format(self, event: "EventLog") -> str:
        """이벤트를 테이블 행으로 변환."""
        # 타임스탬프
        dt = datetime.fromtimestamp(event.timestamp)
        time_str = dt.strftime("%H:%M:%S.") + f"{dt.microsecond // 1000:03d}"

        # 이벤트 태그
        tag = EVENT_TAGS.get(event.event_type.value, event.event_type.value[:7])

        # 컨트롤 타입 (Control 접미사 제거)
        ctrl_type = event.control_type.replace("Control", "") if event.control_type else "?"

        # 이름/클래스 truncate
        name = self._truncate(event.name or "(none)", self.max_name_length)
        class_name = self._truncate(event.class_name or "", self.max_class_length)

        return (
            f"| {time_str:<12} | {tag:<7} | {ctrl_type:<15} | "
            f"{name:<{self.max_name_length}} | {class_name:<{self.max_class_length}} |"
        )

    def print(self, event: "EventLog") -> None:
        """이벤트를 테이블 형식으로 출력."""
        # 첫 번째 이벤트에서 헤더 출력
        if self.show_header and not self._header_printed:
            print(self._get_header())
            self._header_printed = True

        print(self.format(event))

    def reset(self) -> None:
        """헤더 출력 상태 초기화."""
        self._header_printed = False
