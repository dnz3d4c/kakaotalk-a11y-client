# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""메시지 텍스트 추출기"""

from typing import Any, Optional

from ..utils.debug import get_logger
from ..utils.uia_events import _create_uia_client

log = get_logger("Extractor")


class MessageTextExtractor:
    """메시지 텍스트 추출. current_focused_item 우선, GetFocusedElement 폴백."""

    def __init__(self, uia_client: Optional[Any] = None):
        self._uia = uia_client
        self._get_focused_item: Optional[callable] = None

    def set_focus_provider(self, getter: callable) -> None:
        """current_focused_item getter 연결. main.py에서 DI."""
        self._get_focused_item = getter

    def _ensure_uia(self) -> Any:
        """UIA 클라이언트 lazy 초기화"""
        if self._uia is None:
            self._uia = _create_uia_client()
            log.debug("UIA 클라이언트 초기화 완료")
        return self._uia

    def extract_from_item(self, item) -> str | None:
        """UIA 요소에서 직접 텍스트 추출."""
        try:
            name = item.Name
            if name:
                log.debug(f"아이템 Name 추출: {len(name)}자")
            return name
        except Exception as e:
            log.debug(f"아이템 접근 실패 (stale?): {e}")
            return None

    def extract_from_current_focus(self) -> str | None:
        """current_focused_item 우선 → GetFocusedElement 폴백."""
        # 1. current_focused_item에서 추출 시도
        if self._get_focused_item:
            item = self._get_focused_item()
            if item is not None:
                text = self.extract_from_item(item)
                if text:
                    return text
                log.debug("current_focused_item stale, GetFocusedElement 폴백")

        # 2. 폴백: OS 포커스 쿼리
        try:
            uia = self._ensure_uia()
            focused = uia.GetFocusedElement()
            if not focused:
                log.debug("포커스 요소 없음")
                return None

            name = focused.CurrentName
            log.debug(f"UIA Name 추출 (폴백): {len(name) if name else 0}자")
            return name
        except Exception as e:
            log.error(f"UIA 접근 실패: {e}")
            return None
