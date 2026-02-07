# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""디버그 모드 설정 관리. debug_config 전역 인스턴스 사용."""

from dataclasses import dataclass, field
from typing import Set, Optional, Any
from pathlib import Path


def _get_project_root() -> Path:
    return Path(__file__).parent.parent.parent.parent


@dataclass
class DebugConfig:

    # 기본 설정
    enabled: bool = False

    # 도구별 활성화
    enable_profiler: bool = True
    enable_inspector: bool = True
    enable_event_monitor: bool = False  # 기본 비활성 (오버헤드)
    enable_auto_dump: bool = True

    # 이벤트 모니터 설정 (EventMonitorConfig 인스턴스)
    event_monitor_config: Optional[Any] = None

    # 자동 덤프 트리거 조건
    auto_dump_on_error: bool = True
    auto_dump_on_slow: bool = True
    slow_threshold_ms: float = 500  # 이 시간 초과 시 자동 덤프

    # 덤프 파일 관리
    max_dump_files: int = 50  # auto_* 최대 보관 (쌍 단위, 실제 파일 수는 2배)
    dump_cooldown_seconds: float = 60.0  # 동일 트리거 덤프 최소 간격(초)
    max_profile_files: int = 10  # profile_*.log 최대 보관

    # 로깅 레벨
    log_level: str = 'DEBUG'  # 일반 모드는 'INFO'

    # 출력 디렉토리 (프로젝트/logs 폴더)
    debug_output_dir: Path = field(
        default_factory=lambda: _get_project_root() / 'logs'
    )

    # 활성화된 자동 분석 시나리오
    auto_analyze_scenarios: Set[str] = field(default_factory=lambda: {
        'menu_fail',      # 컨텍스트 메뉴 실패 시
        'empty_list',     # 빈 리스트 감지 시
        'focus_lost',     # 포커스 유실 시
        'slow_operation', # 느린 작업 감지 시
    })


# 전역 인스턴스
debug_config = DebugConfig()


def init_debug_mode(
    enabled: bool = True,
    **kwargs
) -> None:
    """디버그 모드 초기화. kwargs로 DebugConfig 필드 오버라이드 가능."""
    global debug_config
    debug_config.enabled = enabled

    for key, value in kwargs.items():
        if hasattr(debug_config, key):
            setattr(debug_config, key, value)

    if enabled:
        debug_config.debug_output_dir.mkdir(parents=True, exist_ok=True)
