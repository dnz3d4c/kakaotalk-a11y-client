# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""접근성 출력 모듈 (NVDA/TTS)"""

from typing import Optional

# accessible_output2 (NVDA/JAWS 등 스크린 리더)
_ao2_output = None
try:
    from accessible_output2.outputs.auto import Auto

    _ao2_output = Auto()
except ImportError:
    pass

# pyttsx3 (로컬 TTS - fallback)
_tts_engine = None
try:
    import pyttsx3

    _tts_engine = pyttsx3.init()
    # 한국어 속도 조절
    _tts_engine.setProperty("rate", 200)
except Exception:
    pass


def speak(text: str, interrupt: bool = True) -> bool:
    """텍스트를 음성으로 출력한다.

    accessible_output2 (스크린 리더) 우선, 실패 시 pyttsx3 사용.

    Args:
        text: 출력할 텍스트
        interrupt: 이전 출력 중단 여부

    Returns:
        출력 성공 여부
    """
    # 1. accessible_output2 시도 (NVDA/JAWS 등)
    if _ao2_output is not None:
        try:
            _ao2_output.speak(text, interrupt=interrupt)
            return True
        except Exception:
            pass

    # 2. pyttsx3 fallback
    if _tts_engine is not None:
        try:
            if interrupt:
                _tts_engine.stop()
            _tts_engine.say(text)
            _tts_engine.runAndWait()
            return True
        except Exception:
            pass

    # 3. 둘 다 실패
    print(f"[TTS] {text}")  # 콘솔 출력이라도
    return False


def announce_scan_start() -> None:
    """스캔 시작 알림"""
    speak("스캔 중")


def announce_scan_result(result_text: str) -> None:
    """스캔 결과 알림"""
    speak(result_text)


def announce_selection(emoji_name: str) -> None:
    """이모지 선택 알림"""
    speak(f"{emoji_name} 클릭")


def announce_cancel() -> None:
    """취소 알림"""
    speak("취소")


def announce_error(message: str) -> None:
    """에러 알림"""
    speak(message)
