# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""Unified debug logging with rotation. Log file: <project>/logs/debug.log"""

import os
from datetime import datetime
from enum import IntEnum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def _get_project_root() -> Path:
    # debug.py location: src/kakaotalk_a11y_client/utils/debug.py (3 levels up)
    return Path(__file__).parent.parent.parent.parent


class LogLevel(IntEnum):
    """TRACE < DEBUG < INFO < WARNING < ERROR < NONE"""
    TRACE = 0
    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4
    NONE = 5


# Determine log level from environment variable
# DEBUG=1 → DEBUG level, DEBUG=2 → TRACE level (most verbose)
_env_debug = os.environ.get("DEBUG", "0")
if _env_debug == "1":
    _global_level = LogLevel.DEBUG
elif _env_debug == "2":
    _global_level = LogLevel.TRACE
else:
    _global_level = LogLevel.NONE

# Log file settings (RotatingFileHandler for size-based rotation)
_file_handler: Optional[RotatingFileHandler] = None
_log_file_path: Optional[Path] = None

def _init_log_file() -> None:
    global _file_handler, _log_file_path
    if _global_level >= LogLevel.NONE:
        return
    try:
        logs_dir = _get_project_root() / "logs"
        logs_dir.mkdir(exist_ok=True)

        _log_file_path = logs_dir / "debug.log"
        _file_handler = RotatingFileHandler(
            _log_file_path,
            maxBytes=1_048_576,  # 1MB
            backupCount=3,       # debug.log, .1, .2, .3 (total 4MB max)
            encoding='utf-8'
        )
        # Session start marker
        _file_handler.stream.write(f"\n{'='*60}\n")
        _file_handler.stream.write(f"Session started: {datetime.now().isoformat()}\n")
        _file_handler.stream.write(f"{'='*60}\n")
        _file_handler.flush()
    except Exception:
        _file_handler = None

# Initialize log file only in debug mode
if _global_level < LogLevel.NONE:
    _init_log_file()


class Logger:

    def __init__(self, name: str, level: Optional[LogLevel] = None):
        self.name = name
        self.level = level if level is not None else _global_level

    def _log(self, level: LogLevel, msg: str) -> None:
        if level >= self.level:
            timestamp = datetime.now().strftime("%H:%M:%S")
            prefix = f"[{level.name}:{self.name}]"
            line = f"{timestamp} {prefix} {msg}"

            # Console output
            try:
                print(line)
            except UnicodeEncodeError:
                # Handle Windows console encoding issues
                clean = ''.join(c if ord(c) < 0x10000 else '?' for c in msg)
                print(f"{timestamp} {prefix} {clean}")

            # File output with rotation
            if _file_handler:
                try:
                    _file_handler.stream.write(f"{line}\n")
                    _file_handler.flush()
                except Exception:
                    pass

    def trace(self, msg: str) -> None:
        self._log(LogLevel.TRACE, msg)

    def debug(self, msg: str) -> None:
        self._log(LogLevel.DEBUG, msg)

    def info(self, msg: str) -> None:
        self._log(LogLevel.INFO, msg)

    def warning(self, msg: str) -> None:
        self._log(LogLevel.WARNING, msg)

    def error(self, msg: str) -> None:
        self._log(LogLevel.ERROR, msg)


# Logger cache
_loggers: dict[str, Logger] = {}


def get_logger(name: str) -> Logger:
    """Get module logger. Same name is cached."""
    if name not in _loggers:
        _loggers[name] = Logger(name)
    return _loggers[name]


def set_global_level(level: LogLevel) -> None:
    """Set global log level. Updates existing loggers."""
    global _global_level
    _global_level = level
    for logger in _loggers.values():
        logger.level = level
    if _file_handler is None and level < LogLevel.NONE:
        _init_log_file()


def is_debug_enabled() -> bool:
    return _global_level <= LogLevel.DEBUG


def is_trace_enabled() -> bool:
    return _global_level <= LogLevel.TRACE


def get_log_file_path() -> Optional[str]:
    return str(_log_file_path) if _log_file_path else None
