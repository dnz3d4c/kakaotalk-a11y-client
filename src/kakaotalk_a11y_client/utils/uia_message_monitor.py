# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""StructureChanged 이벤트 기반 메시지 목록 모니터."""

import threading
import time
from typing import Callable, Optional
from dataclasses import dataclass

import uiautomation as auto

from ..config import TIMING_RESUME_DEBOUNCE, TIMING_EVENT_PUMP_INTERVAL

# COM 인터페이스 import (uia_events에서)
from .uia_events import (
    HAS_COMTYPES,
    COMObject,
    IUIAutomationStructureChangedEventHandler,
    TreeScope_Subtree,
    _create_uia_client,
)

from .debug import get_logger

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..infrastructure.speak_callback import SpeakCallback

log = get_logger("UIA_MsgMon")


class StructureChangedHandler(COMObject):
    """StructureChanged COM 콜백. ChildAdded, ChildrenInvalidated 감지."""

    if HAS_COMTYPES:
        _com_interfaces_ = [IUIAutomationStructureChangedEventHandler]

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def HandleStructureChangedEvent(self, sender, changeType, runtimeId):
        """changeType: 0=ChildAdded, 2=ChildrenInvalidated, 3=ChildrenBulkAdded만 처리."""
        # 새 메시지 관련 이벤트만 처리 (ChildAdded, ChildrenInvalidated)
        if changeType in (0, 2, 3):  # ChildAdded, ChildrenInvalidated, ChildrenBulkAdded
            if self._callback:
                try:
                    self._callback(changeType)
                except Exception as e:
                    log.trace(f"StructureChanged 콜백 오류: {e}")


@dataclass
class MessageEvent:
    new_count: int
    timestamp: float
    source: str  # "event" or "polling"
    children: list = None  # GetChildren() 결과 (이중 호출 방지)


class MessageListMonitor:
    """StructureChanged 이벤트로 새 메시지 감지. 200ms 디바운싱."""

    # 이벤트 디바운싱 설정
    EVENT_DEBOUNCE_INTERVAL = 0.2  # 200ms 윈도우

    def __init__(
        self,
        list_control: auto.Control,
        speak_callback: "SpeakCallback | None" = None
    ):
        self.list_control = list_control

        # SpeakCallback 의존성 주입
        from ..infrastructure.speak_callback import get_default_speak_callback
        self._speak = speak_callback or get_default_speak_callback()

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

        # 이벤트 디바운싱 (발화 끊김 방지)
        self._debounce_timer: Optional[threading.Timer] = None
        self._pending_event_count = 0  # 버퍼링된 이벤트 개수
        self._debounce_generation = 0  # 타이머 세대 (레이스 컨디션 방지)

        # 초기 children (중복 GetChildren 방지)
        self._initial_children: Optional[list] = None

        log.trace(f"MessageListMonitor 초기화: comtypes={HAS_COMTYPES}")

    def start(self, on_message_changed: Callable[[MessageEvent], None]) -> bool:
        """모니터링 시작. 성공 시 True."""
        if self._running:
            log.warning("MessageListMonitor 이미 실행 중")
            return False

        self._callback = on_message_changed
        self._running = True

        # 초기 메시지 개수 저장 (children은 마지막 메시지 읽기용으로 보관)
        try:
            children = self.list_control.GetChildren()
            self._initial_children = children
            self._last_count = len(children) if children else 0
        except Exception:
            self._initial_children = None
            self._last_count = 0

        # 이벤트 스레드 시작
        self._start_event_thread()

        return True

    def stop(self) -> None:
        """모니터링 중지"""
        self._running = False
        self._paused = False

        # 디바운스 타이머 취소
        if self._debounce_timer:
            self._debounce_timer.cancel()
            self._debounce_timer = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        log.debug("MessageListMonitor 중지됨")

    def pause(self, wait: bool = True) -> None:
        """핸들러 해제 요청. wait=True면 완료까지 대기 (최대 200ms)."""
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
        """핸들러 재등록 요청. pause 후 0.3초 이내면 무시."""
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
        return self._paused

    def _start_event_thread(self) -> None:
        self._thread = threading.Thread(
            target=self._event_loop,
            daemon=True,
            name="MessageListMonitor-Event"
        )
        self._thread.start()
        log.info("MessageListMonitor: 이벤트 스레드 시작")

    def _event_loop(self) -> None:
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
                    time.sleep(TIMING_EVENT_PUMP_INTERVAL)
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
        if not HAS_COMTYPES:
            return False

        try:
            # UIA 클라이언트 생성
            self._uia = _create_uia_client()

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
        """200ms 디바운싱 후 _flush_pending_events 호출."""
        if not self._running or self._paused:
            return

        # 디바운싱: 이벤트 버퍼링 후 200ms 후에 일괄 처리
        with self._lock:
            self._pending_event_count += 1
            self._debounce_generation += 1
            current_gen = self._debounce_generation

            # 기존 타이머 취소
            if self._debounce_timer:
                self._debounce_timer.cancel()

            # 새 타이머 시작 (200ms 후 flush)
            # generation으로 stale 타이머 무시 (레이스 컨디션 방지)
            self._debounce_timer = threading.Timer(
                self.EVENT_DEBOUNCE_INTERVAL,
                lambda gen=current_gen: self._flush_pending_events(gen)
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

            log.trace(f"StructureChanged 버퍼링: type={change_type}, pending={self._pending_event_count}")

    def _flush_pending_events(self, generation: int) -> None:
        """stale 타이머 무시, 메시지 개수 변화 시 콜백 호출."""
        if not self._running or self._paused:
            return

        try:
            children = self.list_control.GetChildren()
            current_count = len(children) if children else 0

            with self._lock:
                # stale 타이머 무시 (레이스 컨디션 방지)
                if generation != self._debounce_generation:
                    log.trace(f"stale 타이머 무시: gen={generation}, current={self._debounce_generation}")
                    return

                pending = self._pending_event_count
                self._pending_event_count = 0
                self._debounce_timer = None

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

                    log.debug(f"StructureChanged 플러시: pending={pending}, new={new_count}")

                    if self._callback:
                        try:
                            self._callback(event)
                        except Exception as e:
                            log.error(f"이벤트 콜백 오류: {e}")
                elif current_count < self._last_count:
                    # 메시지 삭제/스크롤 등
                    self._last_count = current_count

        except Exception as e:
            log.trace(f"이벤트 플러시 오류: {e}")

    def _on_focus_changed(self, sender) -> None:
        """Name이 빈 경우에만 자식에서 텍스트 추출. 있으면 NVDA에 위임."""
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
                    self._speak(combined)
                    log.debug(f"FocusChanged 발화 (빈 Name 보완): {combined[:30]}...")

            except Exception as e:
                log.trace(f"자식 텍스트 추출 실패: {e}")

        except Exception as e:
            log.trace(f"FocusChanged 처리 오류: {e}")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def initial_children(self) -> Optional[list]:
        """시작 시 조회한 children (마지막 메시지 읽기용)."""
        return self._initial_children

    def get_stats(self) -> dict:
        return {
            "running": self._running,
            "paused": self._paused,
            "last_count": self._last_count,
        }
