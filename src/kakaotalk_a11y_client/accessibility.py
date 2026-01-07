# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""접근성 출력 모듈 (accessible_output2)

음성과 점자 모두 출력. NVDA → SAPI5 자동 fallback.
"""

# 로거는 지연 초기화 (순환 import 방지)
_log = None


def _get_logger():
    """지연 초기화로 순환 import 방지."""
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
    """음성+점자 출력. interrupt=True면 음성만 (이전 발화 중단)."""
    _get_logger().debug(f"text={text!r}, interrupt={interrupt}")
    if _ao2_output is not None:
        try:
            if interrupt:
                # 이전 발화 중단 필요 시 음성만
                _ao2_output.speak(text, interrupt=True)
            else:
                # 일반 출력: 음성 + 점자
                _ao2_output.output(text)
            return True
        except Exception:
            pass

    # fallback: 로그 출력 (스크린 리더 없음)
    _get_logger().warning(f"TTS fallback (no screen reader): {text}")
    return False


def announce_scan_start() -> None:
    speak("스캔 중")


def announce_scan_result(result_text: str) -> None:
    speak(result_text)


def announce_selection(emoji_name: str) -> None:
    speak(f"{emoji_name} 클릭")


def announce_cancel() -> None:
    speak("취소")


def announce_error(message: str) -> None:
    speak(message)
