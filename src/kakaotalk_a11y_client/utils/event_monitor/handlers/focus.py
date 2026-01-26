# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""FocusChanged 이벤트 핸들러."""

import time
import threading
from typing import Callable, Optional, TYPE_CHECKING

import uiautomation as auto

from ..types import EventType, EventLog
from .base import BaseHandler

if TYPE_CHECKING:
    from ..config import EventMonitorConfig

# COM 인터페이스 import
from ...uia_events import (
    HAS_COMTYPES,
    FocusChangedHandler,
)
from ...debug import get_logger
from ....window_finder import filter_kakaotalk_hwnd

log = get_logger("EventMon_Focus")

# FocusChangedHandler는 uia_events.py에서 import (COM 콜백 통합)


class FocusHandler(BaseHandler):
    """FocusChanged 이벤트 핸들러."""

    def __init__(
        self,
        callback: Callable[[EventLog], None],
        config: "EventMonitorConfig",
    ):
        super().__init__(callback, config)
        self._last_focus_element = None
        self._lock = threading.Lock()

    @property
    def event_type(self) -> EventType:
        return EventType.FOCUS

    def register(self, uia_client) -> bool:
        """FocusChanged 이벤트 핸들러 등록."""
        if not HAS_COMTYPES:
            return False

        try:
            self._uia = uia_client
            self._com_handler = FocusChangedHandler(
                callback=self._on_focus_event,
                logger=log
            )

            self._uia.AddFocusChangedEventHandler(
                None,  # cacheRequest
                self._com_handler
            )

            log.debug("FocusChanged handler registered")
            return True

        except Exception as e:
            log.error(f"FocusChanged handler registration failed: {e}")
            self._uia = None
            self._com_handler = None
            return False

    def unregister(self) -> None:
        """FocusChanged 이벤트 핸들러 해제."""
        try:
            if self._com_handler and self._uia:
                self._uia.RemoveFocusChangedEventHandler(self._com_handler)
                log.debug("FocusChanged handler unregistered")
        except Exception as e:
            log.trace(f"FocusChanged handler unregister error: {e}")
        finally:
            self._uia = None
            self._com_handler = None
            self._last_focus_element = None

    def _on_focus_event(self, sender) -> None:
        """카카오톡 창만 처리. compareElements로 중복 필터링."""
        try:
            # 카카오톡 필터링
            if self._config.include_only_kakaotalk:
                if not filter_kakaotalk_hwnd(sender):
                    return

            # compareElements로 중복 필터링
            with self._lock:
                if self._last_focus_element and self._uia:
                    try:
                        is_same = self._uia.CompareElements(
                            sender, self._last_focus_element
                        )
                        if is_same:
                            return
                    except Exception:
                        pass
                self._last_focus_element = sender

            # uiautomation Control로 변환
            focused = auto.Control(element=sender)
            if not focused:
                return

            # EventLog 생성
            event = EventLog(
                timestamp=time.time(),
                event_type=EventType.FOCUS,
                control_type=focused.ControlTypeName or "",
                name=focused.Name or "",
                class_name=focused.ClassName or "",
                _control=focused,
            )

            self._emit(event)

        except Exception as e:
            log.trace(f"FocusChanged processing error: {e}")
