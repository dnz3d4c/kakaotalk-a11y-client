# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""Infrastructure layer: UIA, Win32 API 등 외부 시스템 접근."""

from .uia_adapter import UIAAdapter, UIAAdapterImpl, get_default_uia_adapter
from .speak_callback import SpeakCallback, DefaultSpeakCallback, get_default_speak_callback

__all__ = [
    "UIAAdapter",
    "UIAAdapterImpl",
    "get_default_uia_adapter",
    "SpeakCallback",
    "DefaultSpeakCallback",
    "get_default_speak_callback",
]
