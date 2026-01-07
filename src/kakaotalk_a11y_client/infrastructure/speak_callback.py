# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""음성 출력 추상화. 테스트 시 mock으로 대체 가능."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SpeakCallback(Protocol):
    """음성 출력 인터페이스."""

    def __call__(self, text: str) -> None:
        """텍스트를 음성으로 출력."""
        ...


class DefaultSpeakCallback:
    """기본 음성 출력 구현. accessibility.speak() 사용."""

    def __call__(self, text: str) -> None:
        from ..accessibility import speak
        speak(text)


# 싱글톤 인스턴스
_default_speak_callback: DefaultSpeakCallback | None = None


def get_default_speak_callback() -> DefaultSpeakCallback:
    """기본 SpeakCallback 싱글톤 반환."""
    global _default_speak_callback
    if _default_speak_callback is None:
        _default_speak_callback = DefaultSpeakCallback()
    return _default_speak_callback
