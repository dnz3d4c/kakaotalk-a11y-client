# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""COM 초기화 유틸리티

스레드별 COM 초기화를 관리하여 중복 호출 방지 및 리소스 누수 방지.

사용법:
    from ..utils.com_utils import ensure_com_initialized, com_thread

    # 데코레이터 사용 (권장)
    @ensure_com_initialized
    def my_uia_function():
        ...

    # 컨텍스트 매니저 사용
    with com_thread():
        ...
"""

import threading
from contextlib import contextmanager
from functools import wraps
from typing import Callable, TypeVar, ParamSpec

import pythoncom

# 스레드별 초기화 상태 추적
_initialized_threads: set[int] = set()
_lock = threading.Lock()

P = ParamSpec('P')
R = TypeVar('R')


def _get_thread_id() -> int:
    """현재 스레드 ID 반환"""
    return threading.current_thread().ident or 0


def init_com_for_thread() -> bool:
    """현재 스레드에서 COM 초기화 (중복 호출 안전)

    Returns:
        True: 새로 초기화됨, False: 이미 초기화됨
    """
    thread_id = _get_thread_id()

    with _lock:
        if thread_id in _initialized_threads:
            return False

        pythoncom.CoInitialize()
        _initialized_threads.add(thread_id)
        return True


def uninit_com_for_thread() -> bool:
    """현재 스레드에서 COM 해제

    Returns:
        True: 해제됨, False: 초기화되지 않았음
    """
    thread_id = _get_thread_id()

    with _lock:
        if thread_id not in _initialized_threads:
            return False

        pythoncom.CoUninitialize()
        _initialized_threads.discard(thread_id)
        return True


def is_com_initialized() -> bool:
    """현재 스레드에서 COM이 초기화되었는지 확인"""
    thread_id = _get_thread_id()
    with _lock:
        return thread_id in _initialized_threads


@contextmanager
def com_thread():
    """COM 초기화 컨텍스트 매니저

    사용법:
        with com_thread():
            control = auto.ControlFromHandle(hwnd)
    """
    newly_initialized = init_com_for_thread()
    try:
        yield
    finally:
        if newly_initialized:
            uninit_com_for_thread()


def ensure_com_initialized(func: Callable[P, R]) -> Callable[P, R]:
    """COM 초기화 보장 데코레이터

    com_thread() 컨텍스트 매니저와 동일한 패턴으로 동작.
    새로 초기화한 경우에만 해제하여 리소스 누수 방지.

    사용법:
        @ensure_com_initialized
        def find_element():
            return auto.WindowControl(Name='창')
    """
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        newly_initialized = init_com_for_thread()
        try:
            return func(*args, **kwargs)
        finally:
            if newly_initialized:
                uninit_com_for_thread()
    return wrapper
