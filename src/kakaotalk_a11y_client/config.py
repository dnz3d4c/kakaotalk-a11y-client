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
