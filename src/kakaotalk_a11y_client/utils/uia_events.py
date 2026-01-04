# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""UIA 이벤트 핸들링 (NVDA 패턴)

NVDA는 FocusChanged, PropertyChanged 등 이벤트 핸들러 사용.
불안정할 경우 폴링으로 폴백.

사용법:
    monitor = HybridFocusMonitor()
    monitor.start(on_focus_changed=my_callback)
    # ...
    monitor.stop()
"""

import threading
import time
from typing import Callable, Optional
from dataclasses import dataclass

import uiautomation as auto

from ..config import TIMING_RESUME_DEBOUNCE

try:
    from comtypes import COMError, COMObject
    from comtypes.client import CreateObject, GetModule
    # UIA COM 인터페이스 로드 시도
    try:
        GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import (
            CUIAutomation,
            IUIAutomationFocusChangedEventHandler,
            IUIAutomationStructureChangedEventHandler,
            TreeScope_Subtree,
        )
        HAS_COMTYPES = True
    except Exception:
        HAS_COMTYPES = False
        COMObject = object  # 폴백
except ImportError:
    HAS_COMTYPES = False
    COMError = Exception
    COMObject = object  # 폴백

from .debug import get_logger
from .profiler import profile_logger
from ..accessibility import speak

log = get_logger("UIA_Events")


@dataclass
class FocusEvent:
    """포커스 변경 이벤트"""
    control: auto.Control
    timestamp: float
    source: str  # "event" or "polling"


class HybridFocusMonitor:
    """하이브리드 포커스 모니터 (NVDA 패턴)

    이벤트 기반으로 시작하고, 실패 시 폴링으로 폴백.
    """

    def __init__(
        self,
        polling_interval: float = 0.1,
        max_event_failures: int = 3,
        prefer_events: bool = True
    ):
        """
        Args:
            polling_interval: 폴링 간격 (초)
            max_event_failures: 이벤트 실패 허용 횟수
            prefer_events: True면 이벤트 기반 시도, False면 폴링만
        """
        self.polling_interval = polling_interval
        self.max_event_failures = max_event_failures
        self.prefer_events = prefer_events

        self._use_events = prefer_events and HAS_COMTYPES
        self._event_failure_count = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[FocusEvent], None]] = None
        self._last_focus: Optional[auto.Control] = None
        self._lock = threading.Lock()

        # COM 객체 (이벤트 모드)
        self._uia = None
        self._event_handler = None

        log.trace(f"HybridFocusMonitor 초기화: events={self._use_events}, comtypes={HAS_COMTYPES}")

    def start(self, on_focus_changed: Callable[[FocusEvent], None]) -> bool:
        """모니터링 시작

        Args:
            on_focus_changed: 포커스 변경 시 호출될 콜백

        Returns:
            True면 성공
        """
        if self._running:
            log.warning("이미 실행 중")
            return False

        self._callback = on_focus_changed
        self._running = True

        if self._use_events:
            success = self._start_event_based()
            if not success:
                log.warning("이벤트 모드 실패, 폴링으로 전환")
                self._use_events = False

        if not self._use_events:
            self._start_polling()

        return True

    def stop(self) -> None:
        """모니터링 중지"""
        self._running = False

        if self._use_events:
            self._stop_event_based()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        log.debug("HybridFocusMonitor 중지됨")

    def _start_event_based(self) -> bool:
        """이벤트 기반 모니터링 시작"""
        if not HAS_COMTYPES:
            return False

        try:
            # UIA 클라이언트 생성
            self._uia = CreateObject(CUIAutomation)

            # 이벤트 핸들러 생성 및 등록
            # 참고: comtypes로 이벤트 핸들러를 직접 구현하는 것은 복잡함
            # 여기서는 폴링 모드와 동일하게 처리하되, 이벤트 시도 플래그만 설정
            # 실제 COM 이벤트 핸들러는 별도 구현 필요

            log.info("UIA 이벤트 모드 활성화 (제한적)")

            # 현재는 폴링 스레드 시작하되 이벤트 플래그 유지
            self._start_polling()
            return True

        except Exception as e:
            log.error(f"이벤트 모드 초기화 실패: {e}")
            return False

    def _stop_event_based(self) -> None:
        """이벤트 기반 모니터링 중지"""
        try:
            if self._event_handler and self._uia:
                # 이벤트 핸들러 제거
                pass
            self._uia = None
            self._event_handler = None
        except Exception as e:
            log.warning(f"이벤트 정리 중 오류: {e}")

    def _start_polling(self) -> None:
        """폴링 기반 모니터링 시작"""
        self._thread = threading.Thread(
            target=self._polling_loop,
            daemon=True,
            name="FocusMonitor"
        )
        self._thread.start()
        log.info(f"폴링 모드 시작 (interval={self.polling_interval}s)")

    def _polling_loop(self) -> None:
        """폴링 루프"""
        while self._running:
            try:
                focused = auto.GetFocusedControl()

                if focused and self._is_focus_changed(focused):
                    with self._lock:
                        self._last_focus = focused

                    event = FocusEvent(
                        control=focused,
                        timestamp=time.time(),
                        source="polling" if not self._use_events else "event"
                    )

                    if self._callback:
                        try:
                            self._callback(event)
                        except Exception as e:
                            log.error(f"콜백 오류: {e}")

            except Exception as e:
                self._on_error(e)

            time.sleep(self.polling_interval)

    def _is_focus_changed(self, current: auto.Control) -> bool:
        """포커스가 변경되었는지 확인 (CompareElements API 사용)"""
        if not self._last_focus:
            return True

        try:
            # IUIAutomation.CompareElements()로 정확한 요소 비교
            # RuntimeId 기반으로 같은 속성의 다른 요소도 정확히 구분
            return not auto.ControlsAreSame(current, self._last_focus)
        except Exception:
            return True

    def _on_error(self, error: Exception) -> None:
        """에러 처리"""
        if self._use_events:
            self._event_failure_count += 1
            log.warning(f"이벤트 오류 ({self._event_failure_count}/{self.max_event_failures}): {error}")

            if self._event_failure_count >= self.max_event_failures:
                log.warning("이벤트 모드 불안정, 폴링으로 전환")
                self._use_events = False
                self._stop_event_based()
        else:
            log.trace(f"폴링 오류: {error}")

    @property
    def is_event_mode(self) -> bool:
        """현재 이벤트 모드인지 확인"""
        return self._use_events

    @property
    def is_running(self) -> bool:
        """실행 중인지 확인"""
        return self._running

    def get_stats(self) -> dict:
        """모니터 통계"""
        return {
            "mode": "event" if self._use_events else "polling",
            "running": self._running,
            "event_failures": self._event_failure_count,
            "polling_interval": self.polling_interval,
        }


# =============================================================================
# 글로벌 모니터 인스턴스
# =============================================================================

# 싱글톤 인스턴스 (필요 시 생성)
_focus_monitor: Optional[HybridFocusMonitor] = None


def get_focus_monitor() -> HybridFocusMonitor:
    """글로벌 포커스 모니터 가져오기"""
    global _focus_monitor
    if _focus_monitor is None:
        _focus_monitor = HybridFocusMonitor()
    return _focus_monitor


def start_focus_monitoring(callback: Callable[[FocusEvent], None]) -> bool:
    """포커스 모니터링 시작 (편의 함수)"""
    return get_focus_monitor().start(callback)


def stop_focus_monitoring() -> None:
    """포커스 모니터링 중지 (편의 함수)"""
    if _focus_monitor:
        _focus_monitor.stop()


# =============================================================================
# 메시지 목록 모니터 (Phase 2)
# =============================================================================


class FocusChangedHandler(COMObject):
    """FocusChanged 이벤트 핸들러 (COM 콜백)

    방향키 탐색 시 포커스 변경 감지.
    """

    if HAS_COMTYPES:
        _com_interfaces_ = [IUIAutomationFocusChangedEventHandler]

    def __init__(self, callback):
        """
        Args:
            callback: 이벤트 발생 시 호출할 콜백 (sender)
        """
        super().__init__()
        self._callback = callback

    def HandleFocusChangedEvent(self, sender):
        """FocusChanged 이벤트 핸들러

        Args:
            sender: 포커스를 받은 요소
        """
        if self._callback and sender:
            try:
                self._callback(sender)
            except Exception as e:
                log.trace(f"FocusChanged 콜백 오류: {e}")


class StructureChangedHandler(COMObject):
    """StructureChanged 이벤트 핸들러 (COM 콜백)

    메시지 목록에서 ChildAdded, ChildrenInvalidated 이벤트 감지.
    """

    if HAS_COMTYPES:
        _com_interfaces_ = [IUIAutomationStructureChangedEventHandler]

    def __init__(self, callback):
        """
        Args:
            callback: 이벤트 발생 시 호출할 콜백 (change_type: int)
        """
        super().__init__()
        self._callback = callback

    def HandleStructureChangedEvent(self, sender, changeType, runtimeId):
        """StructureChanged 이벤트 핸들러

        Args:
            sender: 이벤트 발생 요소
            changeType: 변경 유형
                0 = ChildAdded
                1 = ChildRemoved
                2 = ChildrenInvalidated
                3 = ChildrenBulkAdded
                4 = ChildrenBulkRemoved
                5 = ChildrenReordered
            runtimeId: 런타임 ID
        """
        # 새 메시지 관련 이벤트만 처리 (ChildAdded, ChildrenInvalidated)
        if changeType in (0, 2, 3):  # ChildAdded, ChildrenInvalidated, ChildrenBulkAdded
            if self._callback:
                try:
                    self._callback(changeType)
                except Exception as e:
                    log.trace(f"StructureChanged 콜백 오류: {e}")


@dataclass
class MessageEvent:
    """메시지 변경 이벤트"""
    new_count: int
    timestamp: float
    source: str  # "event" or "polling"
    children: list = None  # GetChildren() 결과 (이중 호출 방지)


class MessageListMonitor:
    """메시지 목록 변화 감지 (StructureChanged 이벤트 기반)

    StructureChanged 이벤트로 메시지 추가 감지.
    comtypes 필수.

    pause/resume 패턴:
    - pause(): 이벤트 수신 유지, 콜백만 무시 (COM 재등록 오버헤드 없음)
    - resume(): 콜백 처리 재개
    - 팝업메뉴 열림/닫힘 시 stop/start 대신 사용하여 CPU 스파이크 방지

    메뉴 읽기는 NVDA에 위임 (메뉴 모드에서 pause만 수행).
    """

    def __init__(self, list_control: auto.Control):
        """
        Args:
            list_control: 메시지 목록 ListControl
        """
        self.list_control = list_control

        self._running = False
        self._paused = False  # pause 상태 (이벤트 수신은 유지, 콜백만 무시)
        self._pause_time = 0.0  # 마지막 pause 시각 (debounce용)
        self._pause_complete = threading.Event()  # 동기식 pause용
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[MessageEvent], None]] = None
        self._last_count = 0
        self._lock = threading.Lock()

        # COM 객체
        self._uia = None
        self._event_handler = None  # StructureChanged 핸들러
        self._focus_handler = None  # FocusChanged 핸들러
        self._root_element = None

        # 핸들러 해제/재등록 요청 플래그 (스레드 안전)
        self._pending_unregister = False
        self._pending_register = False

        log.trace(f"MessageListMonitor 초기화: comtypes={HAS_COMTYPES}")

    def start(self, on_message_changed: Callable[[MessageEvent], None]) -> bool:
        """모니터링 시작

        Args:
            on_message_changed: 메시지 변경 시 호출될 콜백

        Returns:
            True면 성공
        """
        if self._running:
            log.warning("MessageListMonitor 이미 실행 중")
            return False

        self._callback = on_message_changed
        self._running = True

        # 초기 메시지 개수 저장
        try:
            children = self.list_control.GetChildren()
            self._last_count = len(children) if children else 0
        except Exception:
            self._last_count = 0

        # 이벤트 스레드 시작
        self._start_event_thread()

        return True

    def stop(self) -> None:
        """모니터링 중지"""
        self._running = False
        self._paused = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        log.debug("MessageListMonitor 중지됨")

    def pause(self, wait: bool = True) -> None:
        """이벤트 처리 일시 중지 + 이벤트 핸들러 해제 요청

        팝업메뉴 열릴 때 호출. 이벤트 핸들러 해제로 COM 충돌 방지.
        실제 해제는 이벤트 루프 스레드에서 수행 (COM 스레드 규칙).

        Args:
            wait: True면 이벤트 루프가 안전 상태가 될 때까지 대기
        """
        if not self._paused:
            self._pause_complete.clear()
            self._paused = True
            self._pause_time = time.time()

            # 이벤트 핸들러 해제 요청 (이벤트 루프에서 실제 해제)
            self._pending_unregister = True

            if wait:
                # 이벤트 루프가 해제 완료할 때까지 대기 (최대 200ms)
                self._pause_complete.wait(timeout=0.2)

            log.debug("MessageListMonitor 일시 중지 (핸들러 해제)")

    def resume(self) -> None:
        """이벤트 처리 재개 + 이벤트 핸들러 재등록 요청

        팝업메뉴 닫힐 때 호출. 이벤트 핸들러 재등록.
        실제 재등록은 이벤트 루프 스레드에서 수행 (COM 스레드 규칙).
        debounce: pause 후 0.3초 이내 resume 무시 (메뉴 감지 플리커 방지)
        """
        if self._paused:
            # debounce: 너무 빠른 resume 방지
            elapsed = time.time() - self._pause_time
            if elapsed < TIMING_RESUME_DEBOUNCE:
                log.trace(f"resume 무시 (debounce: {elapsed:.2f}s < {TIMING_RESUME_DEBOUNCE}s)")
                return
            self._paused = False

            # 이벤트 핸들러 재등록 요청 (이벤트 루프에서 실제 등록)
            if self._running:
                self._pending_register = True

            log.debug("MessageListMonitor 재개 (핸들러 재등록)")

    @property
    def is_paused(self) -> bool:
        """일시 중지 상태인지 확인"""
        return self._paused

    def _start_event_thread(self) -> None:
        """이벤트 처리 전용 스레드 시작

        COM 이벤트는 등록한 스레드에서만 수신 가능하므로,
        이벤트 등록과 메시지 펌프를 같은 스레드에서 실행.
        """
        self._thread = threading.Thread(
            target=self._event_loop,
            daemon=True,
            name="MessageListMonitor-Event"
        )
        self._thread.start()
        log.info("MessageListMonitor: 이벤트 스레드 시작")

    def _event_loop(self) -> None:
        """이벤트 등록 + 메시지 펌프 루프 (같은 스레드에서 실행)"""
        import pythoncom
        pythoncom.CoInitialize()

        try:
            # 이 스레드에서 이벤트 등록
            success = self._try_register_event()
            if not success:
                log.error("이벤트 등록 실패 - 메시지 모니터링 불가")
                return

            log.info("MessageListMonitor: 메시지 펌프 시작")

            # 메시지 펌프 루프
            while self._running:
                # 핸들러 해제 요청 처리 (같은 스레드에서 해제 - COM 규칙)
                if self._pending_unregister:
                    self._pending_unregister = False
                    self._unregister_event()
                    self._pause_complete.set()  # pause 완료 신호

                # 핸들러 재등록 요청 처리
                if self._pending_register:
                    self._pending_register = False
                    self._try_register_event()

                # pause 상태: 이벤트 펌프 스킵 (NVDA가 메뉴 읽기)
                if self._paused:
                    time.sleep(0.05)
                    continue

                # 이벤트 펌프 (StructureChanged 콜백 처리)
                pythoncom.PumpWaitingMessages()

                time.sleep(0.1)  # 100ms 간격

        except Exception as e:
            log.error(f"이벤트 루프 오류: {e}")
        finally:
            self._unregister_event()
            pythoncom.CoUninitialize()
            log.debug("이벤트 루프 종료")

    def _try_register_event(self) -> bool:
        """StructureChanged 이벤트 등록"""
        if not HAS_COMTYPES:
            return False

        try:
            # UIA 클라이언트 생성
            self._uia = CreateObject(CUIAutomation)

            # 메시지 목록의 IUIAutomationElement 가져오기
            hwnd = self.list_control.NativeWindowHandle
            if not hwnd:
                log.debug("list_control에 NativeWindowHandle 없음")
                return False

            self._root_element = self._uia.ElementFromHandle(hwnd)
            if not self._root_element:
                log.debug("ElementFromHandle 실패")
                return False

            # StructureChanged 이벤트 핸들러 생성 및 등록
            self._event_handler = StructureChangedHandler(
                callback=self._on_structure_changed
            )

            self._uia.AddStructureChangedEventHandler(
                self._root_element,
                TreeScope_Subtree,
                None,  # cacheRequest
                self._event_handler
            )

            log.info("MessageListMonitor: StructureChanged 이벤트 등록 성공")

            # NOTE: FocusChanged 이벤트는 비활성화됨
            # 전역 이벤트로 모든 포커스 변경을 수신해서 CPU 스파이크 유발
            # 메시지 탐색은 NVDA 네이티브에 위임

            return True

        except Exception as e:
            log.debug(f"이벤트 등록 실패: {e}")
            self._uia = None
            self._event_handler = None
            self._root_element = None
            return False

    def _unregister_event(self) -> None:
        """이벤트 핸들러 해제"""
        try:
            # StructureChanged 핸들러 해제
            if self._event_handler and self._uia and self._root_element:
                self._uia.RemoveStructureChangedEventHandler(
                    self._root_element,
                    self._event_handler
                )
                log.debug("StructureChanged 이벤트 해제 완료")
        except Exception as e:
            log.trace(f"이벤트 해제 오류: {e}")
        finally:
            self._uia = None
            self._event_handler = None
            self._focus_handler = None
            self._root_element = None

    def _on_structure_changed(self, change_type: int) -> None:
        """StructureChanged 이벤트 콜백

        Args:
            change_type: 변경 유형 (0=ChildAdded, 2=ChildrenInvalidated, etc.)
        """
        if not self._running or self._paused:
            return

        try:
            children = self.list_control.GetChildren()
            current_count = len(children) if children else 0

            with self._lock:
                if current_count > self._last_count:
                    new_count = current_count - self._last_count
                    self._last_count = current_count

                    # children을 이벤트에 포함 (GetChildren 이중 호출 방지)
                    event = MessageEvent(
                        new_count=new_count,
                        timestamp=time.time(),
                        source="event",
                        children=children  # 이미 가져온 children 전달
                    )

                    log.debug(f"StructureChanged 이벤트: type={change_type}, new={new_count}")

                    if self._callback:
                        try:
                            self._callback(event)
                        except Exception as e:
                            log.error(f"이벤트 콜백 오류: {e}")
                elif current_count < self._last_count:
                    # 메시지 삭제/스크롤 등
                    self._last_count = current_count

        except Exception as e:
            log.trace(f"이벤트 처리 오류: {e}")

    def _on_focus_changed(self, sender) -> None:
        """FocusChanged 이벤트 콜백

        Name이 빈 경우에만 직접 읽기 (NVDA 보완).
        Name이 있으면 NVDA에 위임 (이중 발화 방지).
        """
        if not self._running:
            return

        try:
            name = sender.CurrentName or ""

            # Name이 있으면 NVDA에 위임 (이중 발화 방지)
            if name.strip():
                return

            # Name이 비어있음 → 자식에서 텍스트 추출 시도
            try:
                true_condition = self._uia.CreateTrueCondition()
                children = sender.FindAll(TreeScope_Subtree, true_condition)

                texts = []
                if children:
                    for i in range(children.Length):
                        child = children.GetElement(i)
                        child_name = child.CurrentName
                        if child_name and child_name.strip():
                            texts.append(child_name)

                if texts:
                    combined = " ".join(texts)
                    speak(combined, interrupt=False)
                    log.debug(f"FocusChanged 발화 (빈 Name 보완): {combined[:30]}...")

            except Exception as e:
                log.trace(f"자식 텍스트 추출 실패: {e}")

        except Exception as e:
            log.trace(f"FocusChanged 처리 오류: {e}")

    @property
    def is_running(self) -> bool:
        """실행 중인지 확인"""
        return self._running

    def get_stats(self) -> dict:
        """모니터 통계"""
        return {
            "running": self._running,
            "paused": self._paused,
            "last_count": self._last_count,
        }
