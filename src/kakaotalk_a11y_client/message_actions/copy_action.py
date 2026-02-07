# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""메시지 복사 액션"""

from ..accessibility import speak
from ..utils.clipboard import copy_to_clipboard
from ..utils.debug import get_logger
from .base import MessageAction
from .extractor import MessageTextExtractor

log = get_logger("CopyAction")


class CopyMessageAction(MessageAction):
    """C 키 - 메시지 복사"""

    def __init__(self, extractor: MessageTextExtractor):
        self._extractor = extractor

    def execute(self) -> None:
        log.debug("복사 시작")

        # 키 입력 시점에 현재 포커스에서 실시간 추출
        text = self._extractor.extract_from_current_focus()
        if not text:
            log.debug("텍스트 없음")
            speak("메시지 없음")
            return

        log.debug(f"추출된 텍스트: {len(text)}자")
        if copy_to_clipboard(text):
            speak("메시지 복사됨")
            log.info(f"복사 완료: {text[:50]}...")
        else:
            speak("메시지 복사 실패")
            log.error("클립보드 접근 실패")
