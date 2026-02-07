# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""Infrastructure layer: UIA, Win32 API 등 외부 시스템 접근."""

from .uia_adapter import UIAAdapter, UIAAdapterImpl, get_default_uia_adapter

__all__ = [
    "UIAAdapter",
    "UIAAdapterImpl",
    "get_default_uia_adapter",
]
