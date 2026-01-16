# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""FocusChanged 이벤트 모니터. 카카오톡 창만 처리."""

import threading
import time
from typing import Callable, Optional, Tuple
from dataclasses import dataclass

import uiautomation as auto

from ..config import TIMING_EVENT_PUMP_INTERVAL
from .debug import get_logger
from ..window_finder import is_kakaotalk_window, is_kakaotalk_menu_window
from .event_coalescer import EventCoalescer

# COM 인터페이스 import (uia_events에서)
from .uia_events import (
    HAS_COMTYPES,
    COMObject,
    IUIAutomationFocusChangedEventHandler,
    _create_uia_client,
)

log = get_logger("UIA_Focus")


@dataclass
class FocusEvent:
    control: auto.Control
    timestamp: float
    source: str  # "event" or "polling"


class FocusChangedHandler(COMObject):
    """FocusChanged COM 콜백."""

    if HAS_COMTYPES:
        _com_interfaces_ = [IUIAutomationFocusChangedEventHandler]

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def HandleFocusChangedEvent(self, sender):
        if self._callback and sender:
            try:
                self._callback(sender)
            except Exception as e:
                log.trace(f"FocusChanged callback error: {e}")


class FocusMonitor:
    """FocusChanged 이벤트 모니터. 카카오톡 창만 처리."""

    def __init__(self):
        if not HAS_COMTYPES:
            raise RuntimeError("comtypes 모듈 필요 (pip install comtypes)")

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[FocusEvent], None]] = None
        self._last_focus: Optional[auto.Control] = None
        self._lock = threading.Lock()

        # Phase 1: CompareElements 대체
        self._last_runtime_id: Optional[Tuple[int, ...]] = None
        self._last_event_time: float = 0.0  # 30ms 디바운싱용

        # Phase 2: EventCoalescer (NVDA 스타일 이벤트 병합)
        self._coalescer: Optional[EventCoalescer] = None

        # COM 객체
        self._uia = None
        self._event_handler = None

        log.trace(f"FocusMonitor initialized: comtypes={HAS_COMTYPES}")

    def start(self, on_focus_changed: Callable[[FocusEvent], None]) -> bool:
        """모니터링 시작. 성공 시 True."""
        if self._running:
            log.warning("already running")
            return False

        self._callback = on_focus_changed
        self._running = True

        # Phase 2: EventCoalescer 시작 (20ms 배치 처리)
        self._coalescer = EventCoalescer(
            flush_callback=self._process_focus_event,
            flush_interval=0.02  # 20ms
        )

        success = self._start_event_based()
        if not success:
            self._running = False
            raise RuntimeError("FocusChanged 이벤트 등록 실패")

        return True

    def stop(self) -> None:
        """모니터링 중지"""
        self._running = False

        # Phase 2: EventCoalescer 중지
        if self._coalescer:
            self._coalescer.stop()
            self._coalescer = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        log.debug("FocusMonitor stopped")

    def _start_event_based(self) -> bool:
        """이벤트 스레드 시작 (COM 초기화 + AddFocusChangedEventHandler)."""
        if not HAS_COMTYPES:
            return False

        try:
            # 이벤트 스레드 시작 (COM 이벤트는 등록한 스레드에서만 수신)
            self._thread = threading.Thread(
                target=self._event_loop,
                daemon=True,
                name="FocusMonitor-Event"
            )
            self._thread.start()
            log.info("FocusChanged event mode started")
            return True

        except Exception as e:
            log.error(f"event mode initialization failed: {e}")
            return False

    def _event_loop(self) -> None:
        """COM 초기화 → AddFocusChangedEventHandler → 메시지 펌프."""
        import pythoncom
        pythoncom.CoInitialize()

        try:
            # UIA 클라이언트 생성 (이 스레드에서)
            self._uia = _create_uia_client()

            # FocusChanged 이벤트 핸들러 생성 및 등록
            self._event_handler = FocusChangedHandler(
                callback=self._on_focus_event
            )

            self._uia.AddFocusChangedEventHandler(
                None,  # cacheRequest (선택적)
                self._event_handler
            )

            log.info("AddFocusChangedEventHandler registered")

            # 메시지 펌프 루프
            while self._running:
                pythoncom.PumpWaitingMessages()
                time.sleep(TIMING_EVENT_PUMP_INTERVAL)

        except Exception as e:
            log.error(f"event loop error: {e}")
        finally:
            self._cleanup_event_handler()
            pythoncom.CoUninitialize()
            log.debug("event loop terminated")

    def _cleanup_event_handler(self) -> None:
        try:
            if self._event_handler and self._uia:
                self._uia.RemoveFocusChangedEventHandler(self._event_handler)
                log.debug("FocusChanged handler unregistered")
        except Exception as e:
            log.trace(f"handler unregister error: {e}")
        finally:
            self._uia = None
            self._event_handler = None

    def _on_focus_event(self, sender) -> None:
        """COM 콜백. 1차 필터링(디바운싱/중복체크) → 2차 coalescer."""
        if not self._running or not self._coalescer:
            return

        try:
            # 1. 시간 기반 디바운싱 (30ms) - Phase 1에서 효과 입증
            now = time.time()
            if now - self._last_event_time < 0.03:
                return
            self._last_event_time = now

            import win32gui
            # 2. 창 핸들 확인 - 카카오톡 창 외 즉시 무시
            hwnd = sender.CurrentNativeWindowHandle
            if not hwnd:
                fg_hwnd = win32gui.GetForegroundWindow()
                if not fg_hwnd or not (is_kakaotalk_window(fg_hwnd) or is_kakaotalk_menu_window(fg_hwnd)):
                    return
                hwnd = fg_hwnd
            elif not (is_kakaotalk_window(hwnd) or is_kakaotalk_menu_window(hwnd)):
                return

            # 3. RuntimeID 기반 중복 체크 (CompareElements 대체)
            try:
                runtime_id = tuple(sender.GetRuntimeId())
            except Exception:
                runtime_id = (id(sender),)  # 폴백

            if runtime_id == self._last_runtime_id:
                return
            self._last_runtime_id = runtime_id

            # 4. Control 변환
            focused = auto.Control(element=sender)
            if not focused:
                return

            # 5. FocusEvent 생성 + coalescer에 추가
            event = FocusEvent(
                control=focused,
                timestamp=now,
                source="event"
            )

            # Phase 2: coalescer가 배치로 처리 (같은 키는 최신만 유지)
            key = (runtime_id, "focus")
            self._coalescer.add(key, event)

        except Exception as e:
            log.error(f"focus event processing error: {e}")

    def _process_focus_event(self, event: FocusEvent) -> None:
        """coalescer가 호출. 실제 콜백 실행."""
        if not self._running:
            return

        try:
            with self._lock:
                self._last_focus = event.control

            if self._callback:
                self._callback(event)
        except Exception as e:
            log.error(f"callback error: {e}")

    @property
    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> dict:
        return {
            "mode": "event",
            "running": self._running,
        }


# =============================================================================
# 글로벌 모니터 인스턴스
# =============================================================================

# 싱글톤 인스턴스 (필요 시 생성)
_focus_monitor: Optional[FocusMonitor] = None
_focus_monitor_lock = threading.Lock()


def get_focus_monitor() -> FocusMonitor:
    global _focus_monitor
    if _focus_monitor is None:
        with _focus_monitor_lock:
            if _focus_monitor is None:  # Double-check
                _focus_monitor = FocusMonitor()
    return _focus_monitor


def start_focus_monitoring(callback: Callable[[FocusEvent], None]) -> bool:
    return get_focus_monitor().start(callback)


def stop_focus_monitoring() -> None:
    if _focus_monitor:
        _focus_monitor.stop()
