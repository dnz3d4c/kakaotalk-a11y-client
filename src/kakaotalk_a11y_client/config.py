# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""설정값 정의"""

from pathlib import Path


# 이모지 템플릿 이미지 경로 (패키지 내부)
TEMPLATE_DIR = Path(__file__).parent / "emojis"

# 지원 이모지 목록 (MVP: 4개)
EMOJIS = {
    1: {"name": "하트", "file": "emoji_heart.png", "key": "1"},
    2: {"name": "엄지", "file": "emoji_thumbsup.png", "key": "2"},
    3: {"name": "체크", "file": "emoji_check.png", "key": "3"},
    4: {"name": "웃음", "file": "emoji_smile.png", "key": "4"},
}

# OpenCV 템플릿 매칭 설정
MATCH_THRESHOLD = 0.8  # 매칭 신뢰도 임계값

# pyautogui 설정
CLICK_PAUSE = 0.1  # 클릭 전후 대기 시간(초)
FAILSAFE = True  # 마우스를 화면 모서리로 이동 시 중단

# 카카오톡 창 설정
KAKAOTALK_WINDOW_TITLE = "카카오톡"

# =============================================================================
# 타이밍 설정 (초)
# =============================================================================

# 포커스 모니터 폴링 간격
TIMING_MENU_MODE_POLL_INTERVAL = 0.15     # 메뉴 모드: 빠른 폴링
TIMING_GRACE_POLL_INTERVAL = 0.15         # grace period 중 폴링
TIMING_INACTIVE_POLL_INTERVAL = 0.5       # 비카카오톡 창: 느린 폴링
TIMING_NORMAL_POLL_INTERVAL = 0.3         # 평상시 폴링

# Grace period / Debounce
TIMING_MENU_GRACE_PERIOD = 0.3            # 하위 메뉴 전환 시 잠깐 창 없어지는 현상 대응
TIMING_RESUME_DEBOUNCE = 0.3              # pause 후 resume 무시 (메뉴 감지 플리커 방지)

# 캐시 TTL
TIMING_MENU_CACHE_TTL = 0.15              # 메뉴 창 감지 캐시 (EnumWindows 비용 절감)

# =============================================================================
# UIA 탐색 설정
# =============================================================================

# searchDepth 설정
SEARCH_DEPTH_MESSAGE_LIST_CHECK = 3       # 메시지 목록 존재 확인용
SEARCH_DEPTH_MESSAGE_LIST = 4             # 메시지 목록 탐색
SEARCH_DEPTH_CHAT_LIST = 6                # 채팅 목록 탐색 (메인 창)

# 필터링 설정
FILTER_MAX_CONSECUTIVE_EMPTY = 15         # 연속 빈 항목 시 조기 종료 한계

# UIA 검색 타임아웃
SEARCH_MAX_SECONDS_LIST = 0.3             # 메시지 목록 검색 제한시간 (0.5→0.3)
SEARCH_MAX_SECONDS_FALLBACK = 0.2         # 존재 확인용 제한시간 (0.3→0.2)

# =============================================================================
# 포커스 모니터 설정
# =============================================================================

TIMING_MAX_WARMUP = 5.0                   # UIA 초기화 최대 대기시간
TIMING_NAVIGATION_GRACE = 1.0             # 메뉴 닫힘 후 MessageMonitor 유지

# =============================================================================
# UIA 이벤트 설정
# =============================================================================

TIMING_EVENT_PUMP_INTERVAL = 0.05         # 이벤트 펌프 폴링 간격

# =============================================================================
# 캐시 설정
# =============================================================================

CACHE_MESSAGE_LIST_TTL = 1.0              # 메시지 목록 캐시 TTL

# =============================================================================
# 성능 프로파일러 설정
# =============================================================================

PERF_SLOW_THRESHOLD_MS = 100              # 느린 작업 경고 임계값 (ms)
PERF_COMPARISON_THRESHOLD_PCT = 20.0      # 성능 비교 임계값 (%)

# =============================================================================
# OpenCV 설정
# =============================================================================

CV_NMS_THRESHOLD = 0.3                    # Non-Maximum Suppression 임계값
