# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""UIA 유틸리티 패키지

NVDA 패턴 적용:
- COMError 핸들링 (safe_uia_call, handle_uia_errors)
- UIA 신뢰도 판단 (is_good_uia_element, should_use_uia_for_window)
- TTL 캐싱 (UIACache, message_list_cache)
- 이벤트 핸들링 (HybridFocusMonitor)
- Workaround 시스템 (WORKAROUNDS)
"""

from .debug import get_logger, is_debug_enabled, LogLevel, set_global_level
from .uia_utils import (
    find_all_descendants,
    find_first_descendant,
    get_children_recursive,
    dump_tree,
    dump_element_details,
    # NVDA 패턴: COMError 핸들링
    safe_uia_call,
    handle_uia_errors,
    get_children_safe,
    get_focused_safe,
    get_parent_safe,
    # NVDA 패턴: UIA 신뢰도 판단
    is_good_uia_element,
    should_use_uia_for_window,
    KAKAO_GOOD_UIA_CLASSES,
    KAKAO_BAD_UIA_CLASSES,
)
from .uia_cache import (
    UIACache,
    CacheEntry,
    message_list_cache,
    clear_all_caches,
    log_all_cache_stats,
)
from .uia_events import (
    HybridFocusMonitor,
    FocusEvent,
    get_focus_monitor,
    start_focus_monitoring,
    stop_focus_monitoring,
)
from .uia_workarounds import (
    WORKAROUNDS,
    Workaround,
    get_workaround,
    list_workarounds,
    log_workaround,
    should_use_msaa,
    should_skip_element,
    get_element_name,
)
from .com_utils import (
    init_com_for_thread,
    uninit_com_for_thread,
    is_com_initialized,
    com_thread,
    ensure_com_initialized,
)

__all__ = [
    # debug
    "get_logger",
    "is_debug_enabled",
    "LogLevel",
    "set_global_level",
    # uia_utils (기존)
    "find_all_descendants",
    "find_first_descendant",
    "get_children_recursive",
    "dump_tree",
    "dump_element_details",
    # uia_utils (NVDA 패턴: COMError)
    "safe_uia_call",
    "handle_uia_errors",
    "get_children_safe",
    "get_focused_safe",
    "get_parent_safe",
    # uia_utils (NVDA 패턴: 신뢰도)
    "is_good_uia_element",
    "should_use_uia_for_window",
    "KAKAO_GOOD_UIA_CLASSES",
    "KAKAO_BAD_UIA_CLASSES",
    # uia_cache
    "UIACache",
    "CacheEntry",
    "message_list_cache",
    "clear_all_caches",
    "log_all_cache_stats",
    # uia_events
    "HybridFocusMonitor",
    "FocusEvent",
    "get_focus_monitor",
    "start_focus_monitoring",
    "stop_focus_monitoring",
    # uia_workarounds
    "WORKAROUNDS",
    "Workaround",
    "get_workaround",
    "list_workarounds",
    "log_workaround",
    "should_use_msaa",
    "should_skip_element",
    "get_element_name",
    # com_utils
    "init_com_for_thread",
    "uninit_com_for_thread",
    "is_com_initialized",
    "com_thread",
    "ensure_com_initialized",
]
