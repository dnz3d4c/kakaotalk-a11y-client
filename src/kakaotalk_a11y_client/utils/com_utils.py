# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""COM 초기화 유틸리티. 스레드별 중복 호출 방지."""

import threading
from contextlib import contextmanager

import pythoncom

# 스레드별 초기화 상태 추적
_initialized_threads: set[int] = set()
_lock = threading.Lock()


def _get_thread_id() -> int:
    return threading.current_thread().ident or 0


def init_com_for_thread() -> bool:
    """현재 스레드 COM 초기화. 새로 초기화 시 True, 이미 됐으면 False."""
    thread_id = _get_thread_id()

    with _lock:
        if thread_id in _initialized_threads:
            return False

        pythoncom.CoInitialize()
        _initialized_threads.add(thread_id)
        return True


def uninit_com_for_thread() -> bool:
    """현재 스레드 COM 해제. 해제 시 True, 초기화 안 됐으면 False."""
    thread_id = _get_thread_id()

    with _lock:
        if thread_id not in _initialized_threads:
            return False

        pythoncom.CoUninitialize()
        _initialized_threads.discard(thread_id)
        return True


@contextmanager
def com_thread():
    """COM 초기화/해제 컨텍스트 매니저. 새로 초기화한 경우에만 해제."""
    newly_initialized = init_com_for_thread()
    try:
        yield
    finally:
        if newly_initialized:
            uninit_com_for_thread()
