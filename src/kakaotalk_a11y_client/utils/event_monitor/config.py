# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""이벤트 모니터 설정."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .types import (
    EventType,
    OutputFormat,
    DEFAULT_EVENT_TYPES,
    DEBUG_DEFAULT_EVENTS,
    TRACE_DEFAULT_EVENTS,
)


@dataclass
class EventMonitorConfig:
    """이벤트 모니터 설정."""

    # 활성화할 이벤트 타입
    event_types: set[EventType] = field(default_factory=lambda: set(DEFAULT_EVENT_TYPES))

    # 필터링
    filter_control_types: Optional[set[str]] = None  # None=전체
    filter_class_names: Optional[set[str]] = None
    exclude_empty_names: bool = True
    include_only_kakaotalk: bool = True

    # 출력 형식
    output_format: OutputFormat = OutputFormat.CONSOLE

    # 파일 로깅
    log_to_file: bool = False
    log_file_path: Optional[Path] = None

    def should_log_event_type(self, event_type: EventType) -> bool:
        """해당 이벤트 타입을 로깅해야 하는지."""
        return event_type in self.event_types

    def should_log_control(
        self,
        control_type: str,
        class_name: str,
        name: str
    ) -> bool:
        """해당 컨트롤을 로깅해야 하는지."""
        # 빈 이름 필터
        if self.exclude_empty_names and not name:
            return False

        # ControlType 필터
        if self.filter_control_types is not None:
            if control_type not in self.filter_control_types:
                return False

        # ClassName 필터
        if self.filter_class_names is not None:
            if class_name not in self.filter_class_names:
                return False

        return True

    @classmethod
    def from_cli_args(
        cls,
        events_arg: Optional[str] = None,
        filter_arg: Optional[str] = None,
        format_arg: Optional[str] = None,
    ) -> "EventMonitorConfig":
        """CLI 인자로부터 설정 생성.

        Args:
            events_arg: "all" 또는 "focus,structure,property" 형식
            filter_arg: "ListItemControl,MenuItemControl" 형식
            format_arg: "console", "json", "table"
        """
        config = cls()

        # 이벤트 타입 파싱
        if events_arg:
            if events_arg.lower() == "all":
                config.event_types = set(EventType)
            else:
                event_names = [e.strip().upper() for e in events_arg.split(",")]
                config.event_types = set()
                for name in event_names:
                    try:
                        config.event_types.add(EventType[name])
                    except KeyError:
                        pass  # 잘못된 이벤트 이름 무시

        # 필터 파싱
        if filter_arg:
            config.filter_control_types = set(
                f.strip() for f in filter_arg.split(",") if f.strip()
            )

        # 출력 형식 파싱
        if format_arg:
            format_map = {
                "console": OutputFormat.CONSOLE,
                "json": OutputFormat.JSON,
                "table": OutputFormat.TABLE,
            }
            config.output_format = format_map.get(
                format_arg.lower(), OutputFormat.CONSOLE
            )

        return config
