# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""이벤트 Coalescer. NVDA 스타일 이벤트 병합.

같은 요소의 같은 이벤트는 최신 것만 유지하여 처리량 감소.
빠른 포커스 이동 시 50-80% 이벤트 감소 효과.
"""

import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Optional, Tuple

from .debug import get_logger

log = get_logger("EventCoalescer")


class EventCoalescer:
    """NVDA 스타일 이벤트 병합.

    - 같은 키의 이벤트는 최신 것으로 덮어씀 (coalescing)
    - flush_interval마다 배치 처리
    - 순서 유지 (OrderedDict)
    - Condition 패턴으로 이벤트 없을 때 CPU 0% (NVDA 패턴)
    """

    def __init__(
        self,
        flush_callback: Callable[[Any], None],
        flush_interval: float = 0.02,  # 20ms
    ):
        """
        Args:
            flush_callback: 이벤트 처리 콜백. 각 이벤트마다 호출됨.
            flush_interval: flush 주기 (초). 기본 20ms.
        """
        self._pending: OrderedDict[Tuple, Any] = OrderedDict()
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)  # NVDA condition_variable 패턴
        self._needs_flush = False
        self._callback = flush_callback
        self._interval = flush_interval
        self._running = True
        self._thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="EventCoalescer-Flush"
        )
        self._thread.start()
        log.trace(f"EventCoalescer started (interval={flush_interval*1000:.0f}ms)")

    def add(self, key: Tuple, event: Any, immediate: bool = False) -> None:
        """이벤트 추가. immediate=True면 배치 우회하고 즉시 콜백.

        Args:
            key: coalescing 키 (예: (runtime_id, "focus"))
            event: 이벤트 데이터
            immediate: True면 배치 큐 우회, 직접 콜백 호출 (NVDA gainFocus 패턴)
        """
        if immediate:
            # 배치 큐 우회, 직접 콜백 (0ms 지연)
            try:
                self._callback(event)
            except Exception as e:
                log.error(f"immediate callback error: {e}")
            return

        with self._condition:
            # 기존 키 있으면 삭제 후 끝에 추가 (순서 갱신)
            if key in self._pending:
                del self._pending[key]
            self._pending[key] = event
            # 플러셔 스레드 깨우기 (NVDA condition_variable 패턴)
            if not self._needs_flush:
                self._needs_flush = True
                self._condition.notify()

    def _flush_loop(self) -> None:
        """이벤트 있을 때만 깨어나서 flush. NVDA condition_variable 패턴."""
        while self._running:
            events = []
            with self._condition:
                # 이벤트 있거나 종료 요청 시까지 대기 (CPU 0%)
                self._condition.wait_for(
                    lambda: self._needs_flush or not self._running,
                    timeout=self._interval
                )

                if not self._pending:
                    self._needs_flush = False
                    continue

                events = list(self._pending.values())
                self._pending.clear()
                self._needs_flush = False

            # 락 해제 후 콜백 호출
            for event in events:
                try:
                    self._callback(event)
                except Exception as e:
                    log.error(f"event callback error: {e}")

    def _flush(self) -> None:
        """대기 중인 이벤트 일괄 처리. stop() 시 마지막 flush용."""
        events = []
        with self._condition:
            if not self._pending:
                return
            events = list(self._pending.values())
            self._pending.clear()
            self._needs_flush = False

        # 락 해제 후 콜백 호출
        for event in events:
            try:
                self._callback(event)
            except Exception as e:
                log.error(f"event callback error: {e}")

    def stop(self) -> None:
        """coalescer 중지. 남은 이벤트 flush 후 종료."""
        self._running = False
        # 스레드 깨우기 (wait_for에서 바로 종료)
        with self._condition:
            self._condition.notify()
        # 마지막 flush
        self._flush()
        if self._thread.is_alive():
            self._thread.join(timeout=0.5)
        log.trace("EventCoalescer stopped")

    @property
    def pending_count(self) -> int:
        """대기 중인 이벤트 수."""
        with self._condition:
            return len(self._pending)
