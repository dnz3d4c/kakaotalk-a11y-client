# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""FocusChanged 이벤트 모니터. 카카오톡 창만 처리."""

import threading
import time
from typing import Callable, Optional
from dataclasses import dataclass

import uiautomation as auto

from ..config import TIMING_EVENT_PUMP_INTERVAL
from .debug import get_logger
from ..window_finder import is_kakaotalk_window, is_kakaotalk_menu_window

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
    """FocusChanged COM 콜백. 카카오톡 창 외 이벤트 무시."""

    if HAS_COMTYPES:
        _com_interfaces_ = [IUIAutomationFocusChangedEventHandler]

    def __init__(self, callback, uia_client=None, last_element_ref=None):
        super().__init__()
        self._callback = callback
        self._uia = uia_client
        self._last_element_ref = last_element_ref

    def HandleFocusChangedEvent(self, sender):
        if self._callback and sender:
            try:
                self._callback(sender)
            except Exception as e:
                log.trace(f"FocusChanged 콜백 오류: {e}")


class FocusMonitor:
    """FocusChanged 이벤트 모니터. 카카오톡 창만 처리."""

    def __init__(self):
        if not HAS_COMTYPES:
            raise RuntimeError("comtypes 모듈 필요 (pip install comtypes)")

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[FocusEvent], None]] = None
        self._last_focus: Optional[auto.Control] = None
        self._last_focus_element = None  # COM 요소 (compareElements용)
        self._lock = threading.Lock()

        # COM 객체
        self._uia = None
        self._event_handler = None

        log.trace(f"FocusMonitor 초기화: comtypes={HAS_COMTYPES}")

    def start(self, on_focus_changed: Callable[[FocusEvent], None]) -> bool:
        """모니터링 시작. 성공 시 True."""
        if self._running:
            log.warning("이미 실행 중")
            return False

        self._callback = on_focus_changed
        self._running = True

        success = self._start_event_based()
        if not success:
            self._running = False
            raise RuntimeError("FocusChanged 이벤트 등록 실패")

        return True

    def stop(self) -> None:
        """모니터링 중지"""
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        log.debug("FocusMonitor 중지됨")

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
            log.info("FocusChanged 이벤트 모드 시작")
            return True

        except Exception as e:
            log.error(f"이벤트 모드 초기화 실패: {e}")
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
                callback=self._on_focus_event,
                uia_client=self._uia,
                last_element_ref=lambda: self._last_focus_element
            )

            self._uia.AddFocusChangedEventHandler(
                None,  # cacheRequest (선택적)
                self._event_handler
            )

            log.info("AddFocusChangedEventHandler 등록 완료")

            # 메시지 펌프 루프
            while self._running:
                pythoncom.PumpWaitingMessages()
                time.sleep(TIMING_EVENT_PUMP_INTERVAL)

        except Exception as e:
            log.error(f"이벤트 루프 오류: {e}")
        finally:
            self._cleanup_event_handler()
            pythoncom.CoUninitialize()
            log.debug("이벤트 루프 종료")

    def _cleanup_event_handler(self) -> None:
        try:
            if self._event_handler and self._uia:
                self._uia.RemoveFocusChangedEventHandler(self._event_handler)
                log.debug("FocusChanged 핸들러 해제 완료")
        except Exception as e:
            log.trace(f"핸들러 해제 오류: {e}")
        finally:
            self._uia = None
            self._event_handler = None

    def _on_focus_event(self, sender) -> None:
        """카카오톡 창만 처리. compareElements로 중복 필터링."""
        if not self._running:
            return

        try:
            import win32gui
            # 창 핸들 확인 - 카카오톡 창 외 즉시 무시
            # 자식 요소는 hwnd=0일 수 있으므로 포그라운드 창 확인
            hwnd = sender.CurrentNativeWindowHandle
            if not hwnd:
                # 현재 포그라운드 창이 카카오톡인지 확인
                fg_hwnd = win32gui.GetForegroundWindow()
                if not fg_hwnd or not (is_kakaotalk_window(fg_hwnd) or is_kakaotalk_menu_window(fg_hwnd)):
                    return
                # 포그라운드가 카카오톡이면 처리 계속
                hwnd = fg_hwnd
            elif not (is_kakaotalk_window(hwnd) or is_kakaotalk_menu_window(hwnd)):
                log.trace(f"FocusChanged 스킵: hwnd={hwnd} (비카카오톡)")
                return

            # compareElements로 중복 필터링 (NVDA 패턴)
            with self._lock:
                if self._last_focus_element:
                    try:
                        is_same = self._uia.CompareElements(sender, self._last_focus_element)
                        if is_same:
                            return  # 중복 무시
                    except Exception:
                        pass

                self._last_focus_element = sender

            # uiautomation Control로 변환
            focused = auto.Control(element=sender)
            if not focused:
                return

            with self._lock:
                self._last_focus = focused

            event = FocusEvent(
                control=focused,
                timestamp=time.time(),
                source="event"
            )

            if self._callback:
                try:
                    self._callback(event)
                except Exception as e:
                    log.error(f"콜백 오류: {e}")

        except Exception as e:
            log.error(f"포커스 이벤트 처리 오류: {e}")

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


def get_focus_monitor() -> FocusMonitor:
    global _focus_monitor
    if _focus_monitor is None:
        _focus_monitor = FocusMonitor()
    return _focus_monitor


def start_focus_monitoring(callback: Callable[[FocusEvent], None]) -> bool:
    return get_focus_monitor().start(callback)


def stop_focus_monitoring() -> None:
    if _focus_monitor:
        _focus_monitor.stop()
