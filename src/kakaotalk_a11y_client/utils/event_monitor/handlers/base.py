# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""이벤트 핸들러 베이스 클래스."""

from abc import ABC, abstractmethod
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import EventLog, EventType
    from ..config import EventMonitorConfig


class BaseHandler(ABC):
    """이벤트 핸들러 베이스 클래스."""

    def __init__(
        self,
        callback: Callable[["EventLog"], None],
        config: "EventMonitorConfig",
    ):
        self._callback = callback
        self._config = config
        self._uia = None
        self._com_handler = None

    @property
    @abstractmethod
    def event_type(self) -> "EventType":
        """이 핸들러가 처리하는 이벤트 타입."""
        ...

    @abstractmethod
    def register(self, uia_client) -> bool:
        """UIA 클라이언트에 이벤트 핸들러 등록.

        Args:
            uia_client: IUIAutomation 인터페이스

        Returns:
            성공 여부
        """
        ...

    @abstractmethod
    def unregister(self) -> None:
        """이벤트 핸들러 등록 해제."""
        ...

    def _emit(self, event: "EventLog") -> None:
        """이벤트 발생. 필터링 후 콜백 호출."""
        # 컨트롤 필터링
        if not self._config.should_log_control(
            event.control_type,
            event.class_name,
            event.name,
        ):
            return

        if self._callback:
            try:
                self._callback(event)
            except Exception:
                pass  # 콜백 오류 무시
