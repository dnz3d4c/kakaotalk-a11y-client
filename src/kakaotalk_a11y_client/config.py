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

# =============================================================================
# 앱 정보
# =============================================================================

APP_DISPLAY_NAME = "카카오톡 접근성 클라이언트"

# =============================================================================
# 카카오톡 창/UIA 설정
# =============================================================================

KAKAOTALK_WINDOW_TITLE = "카카오톡"

# 카카오톡 UIA 클래스명
KAKAO_LIST_CONTROL_CLASS = "EVA_VH_ListControl_Dblclk"
CHROME_CLASS_PREFIX = "Chrome_"

# =============================================================================
# 카카오톡 UI 문자열
# =============================================================================

KAKAO_TAB_FRIENDS = "친구"
KAKAO_TAB_CHATS = "채팅"
KAKAO_MESSAGE_LIST_NAME = "메시지"
KAKAO_MENU_ITEM_PLACEHOLDER = "Menu Item"     # 아직 안 그려진 메뉴 항목 기본 이름
KAKAO_MENU_AUTOMATION_ID = "KakaoTalk Menu"   # 메뉴 컨트롤 AutomationId

# =============================================================================
# 타이밍 설정 (초)
# =============================================================================

# 포커스 모니터 폴링 간격
TIMING_MENU_MODE_POLL_INTERVAL = 0.15     # 메뉴 모드: 빠른 폴링
TIMING_INACTIVE_POLL_INTERVAL = 0.5       # 비카카오톡 창: 느린 폴링
TIMING_NORMAL_POLL_INTERVAL = 0.3         # 평상시 폴링

# 캐시 TTL
TIMING_MENU_CACHE_TTL = 0.15              # 메뉴 창 감지 캐시 (EnumWindows 비용 절감)

# 메시지/스레드 타이밍
TIMING_MESSAGE_DEBOUNCE_SECS = 0.2        # 메시지 이벤트 디바운스
TIMING_HWND_CACHE_TTL = 5.0              # 카카오톡 창 hwnd 캐시 TTL
TIMING_THREAD_JOIN_TIMEOUT = 1.0          # 스레드 종료 대기
TIMING_TTS_READ_DELAY = 0.3              # TTS 읽기 대기
TIMING_PROCESS_TERMINATION_WAIT = 0.5    # 프로세스 종료 대기

# =============================================================================
# UIA 탐색 설정
# =============================================================================

# searchDepth 설정
SEARCH_DEPTH_MESSAGE_LIST = 4             # 메시지 목록 탐색
SEARCH_DEPTH_TAB_CONTROL = 4             # 탭 컨트롤 탐색

# 필터링 설정
FILTER_MAX_CONSECUTIVE_EMPTY = 15         # 연속 빈 항목 시 조기 종료 한계

# UIA 검색 타임아웃
SEARCH_MAX_SECONDS_LIST = 0.3             # 메시지 목록 검색 제한시간 (0.5→0.3)
SEARCH_MAX_SECONDS_FALLBACK = 0.2         # 존재 확인용 제한시간 (0.3→0.2)

# =============================================================================
# 포커스 모니터 설정
# =============================================================================

TIMING_MAX_WARMUP = 5.0                   # UIA 초기화 최대 대기시간
TIMING_WARMUP_POLL_INTERVAL = 0.1         # UIA 초기화 대기 폴링 간격
TIMING_SPEAK_DEDUPE_SECS = 1.0            # 같은 Name 재발화 방지 간격
TIMING_CACHE_CLEANUP_INTERVAL = 60        # 캐시 정리 주기 (초)
TIMING_MENU_BRIDGING_THRESHOLD = 0.2      # 메뉴 종료 후 브리징 방지 기간

# 채팅방 진입 재시도 제한
ENTRY_MAX_RETRIES = 3                     # 최대 재시도 횟수
ENTRY_COOLDOWN_SECS = 30.0                # 재시도 쿨다운 (초)

# =============================================================================
# UIA 이벤트 설정
# =============================================================================

TIMING_EVENT_PUMP_INTERVAL = 0.05         # 이벤트 펌프 폴링 간격

# 포커스 이벤트 디바운스
TIMING_FOCUS_DEBOUNCE_SECS = 0.03        # FocusChanged 디바운싱 (30ms)
TIMING_COALESCER_FLUSH_SECS = 0.02       # EventCoalescer 배치 간격 (20ms)

# =============================================================================
# 캐시 설정
# =============================================================================

CACHE_MESSAGE_LIST_TTL = 1.0              # 메시지 목록 캐시 TTL
CACHE_HWND_CLASS_MAX_SIZE = 200           # hwnd→클래스 캐시 최대 크기
CACHE_HWND_CLASS_EVICT_COUNT = 100        # 캐시 초과 시 제거할 항목 수

# =============================================================================
# 성능 프로파일러 설정
# =============================================================================

PERF_SLOW_THRESHOLD_MS = 100              # 느린 작업 경고 임계값 (ms)
PERF_COMPARISON_THRESHOLD_PCT = 20.0      # 성능 비교 임계값 (%)

# =============================================================================
# OpenCV 설정
# =============================================================================

CV_NMS_THRESHOLD = 0.3                    # Non-Maximum Suppression 임계값
