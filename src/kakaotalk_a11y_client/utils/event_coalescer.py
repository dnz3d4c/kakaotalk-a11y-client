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

    def add(self, key: Tuple, event: Any) -> None:
        """이벤트 추가. 같은 키 존재 시 덮어씀 (coalescing).

        Args:
            key: coalescing 키 (예: (runtime_id, "focus"))
            event: 이벤트 데이터
        """
        with self._lock:
            # 기존 키 있으면 삭제 후 끝에 추가 (순서 갱신)
            if key in self._pending:
                del self._pending[key]
            self._pending[key] = event

    def _flush_loop(self) -> None:
        """주기적으로 이벤트 flush."""
        while self._running:
            time.sleep(self._interval)
            self._flush()

    def _flush(self) -> None:
        """대기 중인 이벤트 일괄 처리."""
        # 락 최소화: 빠르게 복사 후 해제
        with self._lock:
            if not self._pending:
                return
            events = list(self._pending.values())
            self._pending.clear()

        # 락 해제 후 콜백 호출
        for event in events:
            try:
                self._callback(event)
            except Exception as e:
                log.error(f"event callback error: {e}")

    def stop(self) -> None:
        """coalescer 중지. 남은 이벤트 flush 후 종료."""
        self._running = False
        # 마지막 flush
        self._flush()
        if self._thread.is_alive():
            self._thread.join(timeout=0.5)
        log.trace("EventCoalescer stopped")

    @property
    def pending_count(self) -> int:
        """대기 중인 이벤트 수."""
        with self._lock:
            return len(self._pending)
