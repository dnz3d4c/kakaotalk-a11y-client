# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""UIA 유틸리티. NVDA 패턴 (COMError 핸들링, 캐싱, 이벤트)."""

from .debug import get_logger, is_debug_enabled, LogLevel, set_global_level
from .uia_utils import (
    find_all_descendants,
    get_children_recursive,
    safe_uia_call,
)
from .uia_cache import (
    UIACache,
    CacheEntry,
    message_list_cache,
)
from .uia_events import (
    FocusMonitor,
    FocusEvent,
)
from .com_utils import (
    init_com_for_thread,
    uninit_com_for_thread,
    com_thread,
)

__all__ = [
    # debug
    "get_logger",
    "is_debug_enabled",
    "LogLevel",
    "set_global_level",
    # uia_utils
    "find_all_descendants",
    "get_children_recursive",
    "safe_uia_call",
    # uia_cache
    "UIACache",
    "CacheEntry",
    "message_list_cache",
    # uia_events
    "FocusMonitor",
    "FocusEvent",
    # com_utils
    "init_com_for_thread",
    "uninit_com_for_thread",
    "com_thread",
]
