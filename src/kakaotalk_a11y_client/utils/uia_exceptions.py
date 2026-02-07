# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""COMError 안전 래퍼. NVDA 패턴 - UIA 에러 핸들링."""

from typing import Any, Callable

try:
    from comtypes import COMError
except ImportError:
    COMError = Exception

from .profiler import profile_logger


def safe_uia_call(
    func: Callable,
    default: Any = None,
    log_error: bool = True,
    error_msg: str = ""
) -> Any:
    """COMError 안전 래퍼. 에러 시 default 반환."""
    try:
        return func()
    except COMError as e:
        if log_error:
            msg = f"COMError: {e}"
            if error_msg:
                msg = f"{error_msg} - {msg}"
            profile_logger.warning(msg)
        return default
    except LookupError as e:
        # 요소 못 찾음 - 정상적인 상황일 수 있음
        if log_error:
            profile_logger.debug(f"Element not found: {e}")
        return default
    except Exception as e:
        if log_error:
            msg = f"UIA Error: {e}"
            if error_msg:
                msg = f"{error_msg} - {msg}"
            profile_logger.error(msg)
        return default
