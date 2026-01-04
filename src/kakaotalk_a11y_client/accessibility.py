# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""접근성 출력 모듈 (accessible_output2)

accessible_output2가 NVDA → SAPI5 자동 fallback 처리.
SAPI5도 SVSFlagsAsync로 비동기 발화.
"""

# 로거는 지연 초기화 (순환 import 방지)
_log = None


def _get_logger():
    """로거 지연 초기화"""
    global _log
    if _log is None:
        from .utils.debug import get_logger
        _log = get_logger("Speech")
    return _log

# accessible_output2 (NVDA/JAWS/SAPI5 등)
_ao2_output = None
try:
    from accessible_output2.outputs.auto import Auto

    _ao2_output = Auto()
except ImportError:
    pass


def speak(text: str, interrupt: bool = False) -> bool:
    """텍스트를 음성으로 출력한다.

    accessible_output2 사용 (NVDA 우선, SAPI5 fallback).
    모두 비동기 발화.

    Args:
        text: 출력할 텍스트
        interrupt: 이전 출력 중단 여부

    Returns:
        출력 성공 여부
    """
    _get_logger().debug(f"text={text!r}, interrupt={interrupt}")
    if _ao2_output is not None:
        try:
            _ao2_output.speak(text, interrupt=interrupt)
            return True
        except Exception:
            pass

    # fallback: 로그 출력 (스크린 리더 없음)
    _get_logger().warning(f"TTS fallback (no screen reader): {text}")
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
