# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""UIA 이벤트 모니터링 패키지."""

from .types import (
    EventType,
    EventLog,
    OutputFormat,
    StructureChangeType,
    DEFAULT_EVENT_TYPES,
    ALL_EVENT_TYPES,
)
from .config import EventMonitorConfig
from .monitor import EventMonitor
from .formatters import ConsoleFormatter, JsonFormatter, TableFormatter
from .recommender import (
    get_recommendations,
    get_recommendations_for_control,
    format_recommendations,
    print_recommendations,
    print_recommendations_for_control,
    CONTROL_TYPE_RECOMMENDATIONS,
    EVENT_TYPE_DESCRIPTIONS,
)
from .handlers import PROPERTY_IDS, DEFAULT_PROPERTY_IDS

__all__ = [
    # 타입
    "EventType",
    "EventLog",
    "OutputFormat",
    "StructureChangeType",
    "DEFAULT_EVENT_TYPES",
    "ALL_EVENT_TYPES",
    # 설정
    "EventMonitorConfig",
    # 모니터
    "EventMonitor",
    # 포맷터
    "ConsoleFormatter",
    "JsonFormatter",
    "TableFormatter",
    # 권장 이벤트
    "get_recommendations",
    "get_recommendations_for_control",
    "format_recommendations",
    "print_recommendations",
    "print_recommendations_for_control",
    "CONTROL_TYPE_RECOMMENDATIONS",
    "EVENT_TYPE_DESCRIPTIONS",
    # 속성 ID
    "PROPERTY_IDS",
    "DEFAULT_PROPERTY_IDS",
]
