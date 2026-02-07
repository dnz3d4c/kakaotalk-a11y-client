# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""클립보드 유틸리티"""

import wx

from .debug import get_logger

log = get_logger("Clipboard")


def copy_to_clipboard(text: str) -> bool:
    """텍스트를 클립보드에 복사. 성공 시 True."""
    if not wx.TheClipboard.Open():
        log.error("클립보드 열기 실패")
        return False

    try:
        data = wx.TextDataObject(text)
        result = wx.TheClipboard.SetData(data)
        if result:
            log.debug(f"클립보드 복사: {len(text)}자")
        else:
            log.error("SetData 실패")
        return result
    finally:
        wx.TheClipboard.Close()
