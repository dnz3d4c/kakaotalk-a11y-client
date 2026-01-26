# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""이벤트 모니터 통합 클래스."""

import threading
import time
from typing import Callable, Optional

from .types import EventType, EventLog, OutputFormat, DEFAULT_EVENT_TYPES
from .config import EventMonitorConfig
from .handlers import FocusHandler, StructureHandler, PropertyHandler
from .handlers.base import BaseHandler
from .formatters import ConsoleFormatter, JsonFormatter, TableFormatter

from ..uia_events import HAS_COMTYPES, _create_uia_client
from ..debug import get_logger
from ..com_utils import com_thread
from ...config import TIMING_EVENT_PUMP_INTERVAL

log = get_logger("EventMonitor")


class EventMonitor:
    """디버그용 UIA 이벤트 모니터. 여러 이벤트 타입 동시 감시."""

    def __init__(self, config: Optional[EventMonitorConfig] = None):
        if not HAS_COMTYPES:
            raise RuntimeError("comtypes 모듈 필요 (pip install comtypes)")

        self._config = config or EventMonitorConfig()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._handlers: dict[EventType, BaseHandler] = {}
        self._uia = None
        self._lock = threading.Lock()

        # 출력 포맷터 (설정에 따라 선택)
        self._formatter = self._create_formatter()
        self._callback: Optional[Callable[[EventLog], None]] = None

    def _create_formatter(self):
        """설정에 따른 포맷터 생성."""
        fmt = self._config.output_format
        if fmt == OutputFormat.JSON:
            return JsonFormatter(
                file_path=self._config.log_file_path if self._config.log_to_file else None
            )
        elif fmt == OutputFormat.TABLE:
            return TableFormatter()
        else:
            return ConsoleFormatter()

    def start(
        self,
        callback: Optional[Callable[[EventLog], None]] = None,
    ) -> bool:
        """모니터링 시작.

        Args:
            callback: 커스텀 콜백. None이면 기본 콘솔 출력 사용.

        Returns:
            성공 여부
        """
        if self._running:
            log.warning("already running")
            return False

        self._callback = callback or self._default_callback
        self._running = True

        # 이벤트 스레드 시작
        self._thread = threading.Thread(
            target=self._event_loop,
            daemon=True,
            name="EventMonitor"
        )
        self._thread.start()

        log.info(f"EventMonitor started: events={[e.name for e in self._config.event_types]}")
        return True

    def stop(self) -> None:
        """모니터링 중지."""
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        log.info("EventMonitor stopped")

    def toggle_event(self, event_type: EventType) -> bool:
        """특정 이벤트 타입 토글. 런타임 변경.

        Returns:
            토글 후 활성화 여부
        """
        with self._lock:
            if event_type in self._config.event_types:
                self._config.event_types.discard(event_type)
                # 실행 중이면 핸들러 해제
                if self._running and event_type in self._handlers:
                    self._handlers[event_type].unregister()
                    del self._handlers[event_type]
                return False
            else:
                self._config.event_types.add(event_type)
                # 실행 중이면 핸들러 등록
                if self._running and self._uia:
                    handler = self._create_handler(event_type)
                    if handler and handler.register(self._uia):
                        self._handlers[event_type] = handler
                return True

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def active_events(self) -> set[EventType]:
        return self._config.event_types.copy()

    def _default_callback(self, event: EventLog) -> None:
        """기본 콜백: 콘솔 출력."""
        self._formatter.print(event)

    def _create_handler(self, event_type: EventType) -> Optional[BaseHandler]:
        """이벤트 타입별 핸들러 생성."""
        if event_type == EventType.FOCUS:
            return FocusHandler(
                callback=self._on_event,
                config=self._config,
            )
        elif event_type == EventType.STRUCTURE:
            return StructureHandler(
                callback=self._on_event,
                config=self._config,
            )
        elif event_type == EventType.PROPERTY:
            return PropertyHandler(
                callback=self._on_event,
                config=self._config,
            )
        # TODO: WINDOW_OPENED, MENU_OPENED 등 추가
        else:
            log.warning(f"unsupported event type: {event_type}")
            return None

    def _on_event(self, event: EventLog) -> None:
        """핸들러로부터 이벤트 수신. 콜백 호출."""
        if self._callback:
            try:
                self._callback(event)
            except Exception as e:
                log.trace(f"callback error: {e}")

    def _event_loop(self) -> None:
        """COM 초기화 → 핸들러 등록 → 메시지 펌프."""
        import pythoncom

        with com_thread():
            try:
                # UIA 클라이언트 생성
                self._uia = _create_uia_client()

                # 활성화된 이벤트 핸들러 등록
                for event_type in self._config.event_types:
                    handler = self._create_handler(event_type)
                    if handler and handler.register(self._uia):
                        self._handlers[event_type] = handler
                        log.debug(f"{event_type.name} handler registered")

                if not self._handlers:
                    log.warning("no handlers registered")

                # 메시지 펌프 루프
                while self._running:
                    pythoncom.PumpWaitingMessages()
                    time.sleep(TIMING_EVENT_PUMP_INTERVAL)

            except Exception as e:
                log.error(f"event loop error: {e}")
            finally:
                # 모든 핸들러 해제
                for handler in self._handlers.values():
                    handler.unregister()
                self._handlers.clear()
                self._uia = None
                log.debug("event loop terminated")

    def get_stats(self) -> dict:
        """현재 상태 반환."""
        return {
            "running": self._running,
            "active_events": [e.name for e in self._config.event_types],
            "registered_handlers": [e.name for e in self._handlers.keys()],
        }
