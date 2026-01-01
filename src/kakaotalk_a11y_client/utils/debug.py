# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""통합 디버그 로깅 모듈

모든 모듈에서 일관된 디버그 로깅 제공.

사용법:
    from ..utils.debug import get_logger

    log = get_logger("ModuleName")
    log.debug("디버그 메시지")
    log.info("정보 메시지")

로그 파일: <프로젝트>/logs/debug.log
"""

import os
import sys
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Optional, TextIO


def _get_project_root() -> Path:
    """프로젝트 루트 디렉토리 반환"""
    # debug.py 위치: src/kakaotalk_a11y_client/utils/debug.py
    # 프로젝트 루트: 3단계 상위
    return Path(__file__).parent.parent.parent.parent


class LogLevel(IntEnum):
    """로그 레벨

    TRACE: 고빈도 루프 로그 (포커스 모니터 상태 등)
    DEBUG: 상태 변경, 주요 이벤트
    INFO: 모드 전환, 사용자 인지 필요
    WARNING: 복구 가능한 문제
    ERROR: 치명적 오류
    NONE: 로깅 비활성화
    """
    TRACE = 0
    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4
    NONE = 5


# 환경변수에서 로그 레벨 결정
# DEBUG=1 → DEBUG 레벨, DEBUG=2 → TRACE 레벨 (최상세)
_env_debug = os.environ.get("DEBUG", "0")
if _env_debug == "1":
    _global_level = LogLevel.DEBUG
elif _env_debug == "2":
    _global_level = LogLevel.TRACE
else:
    _global_level = LogLevel.NONE

# 로그 파일 설정
_log_file: Optional[TextIO] = None
_log_file_path: Optional[Path] = None

def _init_log_file() -> None:
    """로그 파일 초기화"""
    global _log_file, _log_file_path
    if _global_level >= LogLevel.NONE:
        return
    try:
        # 프로젝트 루트/logs 디렉토리
        logs_dir = _get_project_root() / "logs"
        logs_dir.mkdir(exist_ok=True)

        _log_file_path = logs_dir / "debug.log"
        _log_file = open(_log_file_path, "a", encoding="utf-8")
        _log_file.write(f"\n{'='*60}\n")
        _log_file.write(f"Session started: {datetime.now().isoformat()}\n")
        _log_file.write(f"{'='*60}\n")
        _log_file.flush()
    except Exception:
        _log_file = None

# 디버그 모드일 때만 로그 파일 초기화
if _global_level < LogLevel.NONE:
    _init_log_file()


class Logger:
    """간단한 디버그 로거"""

    def __init__(self, name: str, level: Optional[LogLevel] = None):
        self.name = name
        self.level = level if level is not None else _global_level

    def _log(self, level: LogLevel, msg: str) -> None:
        if level >= self.level:
            prefix = f"[{level.name}:{self.name}]"
            line = f"{prefix} {msg}"

            # 콘솔 출력
            try:
                print(line)
            except UnicodeEncodeError:
                # Windows 콘솔 인코딩 문제 대응
                clean = ''.join(c if ord(c) < 0x10000 else '?' for c in msg)
                print(f"{prefix} {clean}")

            # 파일 출력
            if _log_file:
                try:
                    _log_file.write(f"{line}\n")
                    _log_file.flush()
                except Exception:
                    pass

    def trace(self, msg: str) -> None:
        """TRACE 레벨 로그 (고빈도 루프용)"""
        self._log(LogLevel.TRACE, msg)

    def debug(self, msg: str) -> None:
        """DEBUG 레벨 로그"""
        self._log(LogLevel.DEBUG, msg)

    def info(self, msg: str) -> None:
        """INFO 레벨 로그"""
        self._log(LogLevel.INFO, msg)

    def warning(self, msg: str) -> None:
        """WARNING 레벨 로그"""
        self._log(LogLevel.WARNING, msg)

    def error(self, msg: str) -> None:
        """ERROR 레벨 로그"""
        self._log(LogLevel.ERROR, msg)


# 로거 캐시
_loggers: dict[str, Logger] = {}


def get_logger(name: str) -> Logger:
    """이름으로 로거 가져오기 (캐싱)"""
    if name not in _loggers:
        _loggers[name] = Logger(name)
    return _loggers[name]


def set_global_level(level: LogLevel) -> None:
    """전역 로그 레벨 설정"""
    global _global_level
    _global_level = level
    # 기존 로거들도 업데이트
    for logger in _loggers.values():
        logger.level = level
    # 로그 파일 초기화 (CLI --debug 옵션 지원)
    if _log_file is None and level < LogLevel.NONE:
        _init_log_file()


# 하위 호환성: 기존 debug_log 패턴 대체
def is_debug_enabled() -> bool:
    """DEBUG 모드 활성화 여부 (DEBUG 이상)"""
    return _global_level <= LogLevel.DEBUG


def is_trace_enabled() -> bool:
    """TRACE 모드 활성화 여부 (최상세)"""
    return _global_level <= LogLevel.TRACE


def get_log_file_path() -> Optional[str]:
    """로그 파일 경로 반환"""
    return str(_log_file_path) if _log_file_path else None
