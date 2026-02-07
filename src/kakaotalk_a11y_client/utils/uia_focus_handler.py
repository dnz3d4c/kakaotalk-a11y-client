# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""FocusChanged 이벤트 모니터. 카카오톡 창만 처리."""

import threading
import time
from typing import Callable, Optional, Tuple
from dataclasses import dataclass

import uiautomation as auto

from ..config import (
    TIMING_EVENT_PUMP_INTERVAL,
    TIMING_FOCUS_DEBOUNCE_SECS,
    TIMING_COALESCER_FLUSH_SECS,
    TIMING_THREAD_JOIN_TIMEOUT,
    KAKAO_MENU_ITEM_PLACEHOLDER,
    CHROME_CLASS_PREFIX,
)
from .debug import get_logger
from ..window_finder import filter_kakaotalk_hwnd, is_kakaotalk_hwnd_cached
from .event_coalescer import EventCoalescer
from .com_utils import com_thread

# COM 인터페이스 import (uia_events에서)
from .uia_events import (
    HAS_COMTYPES,
    COMError,
    _create_uia_client,
    FocusChangedHandler,
)

# CacheRequest 속성 ID (NVDA 패턴)
try:
    from comtypes.gen.UIAutomationClient import (
        UIA_ControlTypePropertyId,
        UIA_NamePropertyId,
        UIA_ClassNamePropertyId,
        UIA_RuntimeIdPropertyId,
        UIA_NativeWindowHandlePropertyId,
    )
    HAS_CACHE_PROPS = True
except ImportError:
    HAS_CACHE_PROPS = False
    UIA_ControlTypePropertyId = None
    UIA_NamePropertyId = None
    UIA_ClassNamePropertyId = None
    UIA_RuntimeIdPropertyId = None
    UIA_NativeWindowHandlePropertyId = None

log = get_logger("UIA_Focus")

# 컨테이너 타입: 개별 아이템(ListItem, MenuItem)만 통과시키고 부모 컨테이너는 차단
_CONTAINER_CONTROL_TYPES = frozenset({
    'ListControl',
    'MenuControl',
    'MenuBarControl',
})


@dataclass
class FocusEvent:
    control: auto.Control
    timestamp: float
    source: str  # "event", "polling", or "selection" (ElementSelected)


# FocusChangedHandler는 uia_events.py에서 import


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

        # Phase 2: EventCoalescer 시작
        self._coalescer = EventCoalescer(
            flush_callback=self._process_focus_event,
            flush_interval=TIMING_COALESCER_FLUSH_SECS
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
            self._thread.join(timeout=TIMING_THREAD_JOIN_TIMEOUT)

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

        with com_thread():
            try:
                # UIA 클라이언트 생성 (이 스레드에서)
                self._uia = _create_uia_client()

                # CacheRequest 생성 (NVDA 패턴: COM 왕복 감소)
                cache_request = None
                if HAS_CACHE_PROPS:
                    try:
                        cache_request = self._uia.CreateCacheRequest()
                        cache_request.AddProperty(UIA_ControlTypePropertyId)
                        cache_request.AddProperty(UIA_NamePropertyId)
                        cache_request.AddProperty(UIA_ClassNamePropertyId)
                        cache_request.AddProperty(UIA_RuntimeIdPropertyId)
                        cache_request.AddProperty(UIA_NativeWindowHandlePropertyId)
                        log.debug("FocusChanged CacheRequest created (5 properties)")
                    except Exception as e:
                        log.debug(f"CacheRequest creation failed: {e}")
                        cache_request = None

                # FocusChanged 이벤트 핸들러 생성 및 등록
                self._event_handler = FocusChangedHandler(
                    callback=self._on_focus_event,
                    logger=log
                )

                self._uia.AddFocusChangedEventHandler(
                    cache_request,  # CacheRequest (NVDA 패턴)
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
            # 1. 시간 기반 디바운싱 - Phase 1에서 효과 입증
            now = time.time()
            if now - self._last_event_time < TIMING_FOCUS_DEBOUNCE_SECS:
                return
            self._last_event_time = now

            # 2. hwnd 필터 - CachedNativeWindowHandle + dict lookup
            # 79%의 외부 앱 이벤트를 COM 왕복 없이 즉시 버림
            native_hwnd = self._get_native_hwnd(sender)
            if native_hwnd:
                # 빠른 경로: hwnd 있으면 캐시로 카카오톡 판별
                if not is_kakaotalk_hwnd_cached(native_hwnd):
                    log.trace(f"[SKIP] hwnd filter: native={native_hwnd}")
                    return
            else:
                # 느린 경로: hwnd 없으면 기존 폴백 (포그라운드 → 캐시)
                hwnd = filter_kakaotalk_hwnd(sender)
                if not hwnd:
                    log.trace("[SKIP] hwnd filter: native=None")
                    return

            # 3. RuntimeID 기반 중복 체크 (CompareElements 대체)
            try:
                runtime_id = tuple(sender.GetRuntimeId())
            except Exception:
                runtime_id = (id(sender),)  # 폴백

            if runtime_id == self._last_runtime_id:
                log.trace("[SKIP] duplicate RuntimeId")
                return
            self._last_runtime_id = runtime_id

            # 4. Control 변환
            focused = auto.Control(element=sender)
            if not focused:
                log.trace("[SKIP] Control conversion failed")
                return

            # 5. Chrome_* 요소 무시 (광고 웹뷰)
            if (focused.ClassName or "").startswith(CHROME_CLASS_PREFIX):
                log.trace("[SKIP] Chrome_* element")
                return

            # 6. 컨테이너 타입 무시 (개별 아이템만 통과)
            control_type = focused.ControlTypeName
            if control_type in _CONTAINER_CONTROL_TYPES:
                log.trace(f"[SKIP] container: {control_type}: {(focused.Name or '')[:20]}")
                return

            # 7. MenuItemControl + placeholder 무시 (아직 안 그려진 메뉴)
            # 콜백 호출 자체를 줄여서 CPU 절약
            name = focused.Name or ""
            if control_type == "MenuItemControl" and (not name or name == KAKAO_MENU_ITEM_PLACEHOLDER):
                return  # 로그도 안 찍고 완전 무시

            log.trace(f"[PASS] {control_type}: {name[:20]}")

            # 8. FocusEvent 생성 + 즉시 처리 (NVDA gainFocus 패턴)
            event = FocusEvent(
                control=focused,
                timestamp=now,
                source="event",
            )

            # 포커스 이벤트는 즉시 처리 (NVDA gainFocus 패턴)
            # immediate=True로 20ms 배치 지연 없이 바로 콜백 호출
            key = (runtime_id, "focus")
            self._coalescer.add(key, event, immediate=True)

        except COMError:
            # COM 에러는 예상 가능 (요소 사라짐, 창 닫힘 등) - 무시
            pass
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

    def _get_native_hwnd(self, sender) -> Optional[int]:
        """CachedNativeWindowHandle 우선, CurrentNativeWindowHandle 폴백."""
        try:
            hwnd = sender.CachedNativeWindowHandle
            if hwnd:
                return hwnd
        except Exception:
            pass
        try:
            hwnd = sender.CurrentNativeWindowHandle
            if hwnd:
                return hwnd
        except Exception:
            pass
        return None

    def get_stats(self) -> dict:
        return {
            "mode": "event",
            "running": self._running,
        }

