# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""디버그 모드 초기화. main.py에서 호출."""

import atexit

from .debug import get_logger, set_global_level, LogLevel
from .debug_config import init_debug_mode, debug_config
from .debug_tools import debug_tools
from .profiler import init_profiler

log = get_logger("DebugSetup")


def setup_debug(args) -> None:
    """CLI 인자 기반 디버그 모드 초기화.

    --debug: 이벤트 모니터 + 프로파일러 + 디버그 핫키
    --debug-profile: 프로파일러만
    """
    if args.debug:
        _setup_full_debug(args)
    elif args.debug_profile:
        _setup_profile_only()
    else:
        # 환경변수 기반 초기화 (하위 호환)
        init_profiler()


def _setup_full_debug(args) -> None:
    """--debug 모드 전체 초기화."""
    # 로그 레벨 설정
    if args.trace:
        set_global_level(LogLevel.TRACE)
        print("[DEBUG] TRACE 모드 활성화 (고빈도 로그 포함)")
    else:
        set_global_level(LogLevel.DEBUG)
        print("[DEBUG] 디버그 모드 활성화")

    init_profiler(enabled=True)

    # 이벤트 모니터 설정 생성
    from .event_monitor import EventMonitorConfig
    from .event_monitor.types import DEBUG_DEFAULT_EVENTS

    if args.debug_events is not None:
        # 명시적 --debug-events 옵션 사용
        event_monitor_config = EventMonitorConfig.from_cli_args(
            events_arg=args.debug_events if args.debug_events != 'default' else None,
            filter_arg=args.debug_events_filter,
        )
    else:
        # --debug 기본 이벤트 모니터 (Focus + Structure)
        event_monitor_config = EventMonitorConfig(event_types=set(DEBUG_DEFAULT_EVENTS))
        print(f"[DEBUG] 이벤트 모니터 자동 활성화: {', '.join(e.name for e in DEBUG_DEFAULT_EVENTS)}")

    init_debug_mode(
        enabled=True,
        enable_event_monitor=True,
        event_monitor_config=event_monitor_config,
    )

    # 시작 시 덤프
    if args.debug_dump_on_start:
        try:
            dump_path = debug_tools.dump_to_file(filename_prefix='startup')
            print(f"[DEBUG] 시작 덤프 저장: {dump_path}")
        except Exception as e:
            print(f"[DEBUG] 시작 덤프 실패: {e}")

    # 디버그 단축키 등록
    from .debug_commands import register_debug_hotkeys, auto_start_event_monitor, stop_event_monitor
    register_debug_hotkeys()

    # 이벤트 모니터 자동 시작
    auto_start_event_monitor()
    atexit.register(stop_event_monitor)

    # 세션 리포트 생성 등록
    atexit.register(lambda: debug_tools.generate_session_report())


def _setup_profile_only() -> None:
    """--debug-profile 모드."""
    init_profiler(enabled=True)
    init_debug_mode(
        enabled=True,
        enable_inspector=False,
        enable_event_monitor=False,
    )
    print("[DEBUG] 프로파일러 전용 모드")
