# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""새 메시지 자동 읽기. UIA StructureChanged 이벤트 기반."""

from typing import Optional, TYPE_CHECKING

from ..accessibility import speak
from ..config import (
    SEARCH_DEPTH_MESSAGE_LIST,
    SEARCH_MAX_SECONDS_LIST,
    SEARCH_MAX_SECONDS_FALLBACK,
)
from ..utils.debug import get_logger
from ..utils.uia_utils import get_children_recursive
from ..utils.uia_events import MessageListMonitor, MessageEvent

if TYPE_CHECKING:
    from .chat_room import ChatRoomNavigator

log = get_logger("MessageMonitor")


class MessageMonitor:
    """새 메시지 모니터링. UIA 이벤트 핸들러 기반."""

    def __init__(self, chat_navigator: "ChatRoomNavigator"):
        self.chat_navigator = chat_navigator

        # 실행 상태
        self._running = False
        self._hwnd: int = 0

        # 이벤트 모니터
        self._list_monitor: Optional[MessageListMonitor] = None

        log.debug("MessageMonitor initialized")

    def start(self, hwnd: int) -> bool:
        """이벤트 모니터 시작. 이미 실행 중이면 True 반환."""
        if self._running:
            log.trace("MessageMonitor already running")
            return True

        self._hwnd = hwnd
        self._running = True

        log.info(f"MessageMonitor started: hwnd={hwnd}")

        # 이벤트 모드 시작
        success = self._start_event_mode()
        if success:
            log.info("MessageMonitor: event mode activated")
            return True

        log.error("MessageMonitor: failed to start event mode")
        self._running = False
        return False

    def stop(self):
        log.debug("MessageMonitor stop requested")
        self._running = False

        # 이벤트 모니터 중지
        if self._list_monitor:
            self._list_monitor.stop()
            self._list_monitor = None
            log.debug("MessageListMonitor stopped")

        log.info("MessageMonitor stopped")

    def pause(self):
        """팝업메뉴 열릴 때 호출. COM 재등록 없이 이벤트만 무시."""
        if self._list_monitor:
            self._list_monitor.pause()
            log.debug("MessageMonitor paused")

    def resume(self):
        """팝업메뉴 닫힐 때 호출. 이벤트 처리 재개."""
        if self._list_monitor:
            self._list_monitor.resume()
            log.debug("MessageMonitor resumed")

    def is_running(self) -> bool:
        return self._running

    def is_paused(self) -> bool:
        if self._list_monitor:
            return self._list_monitor.is_paused
        return False

    def _start_event_mode(self) -> bool:
        """MessageListMonitor 생성 및 시작."""
        if not self.chat_navigator.chat_control:
            log.warning("chat_control not found, event mode failed")
            return False

        try:
            # 메시지 목록 찾기
            msg_list = self.chat_navigator.chat_control.ListControl(
                Name="메시지",
                searchDepth=SEARCH_DEPTH_MESSAGE_LIST
            )

            if not msg_list.Exists(maxSearchSeconds=SEARCH_MAX_SECONDS_LIST):
                log.warning("message list not found, event mode failed")
                return False

            # MessageListMonitor 생성 및 시작
            self._list_monitor = MessageListMonitor(list_control=msg_list)
            self._list_monitor.start(on_message_changed=self._on_message_event)
            log.info("MessageListMonitor started")
            return True

        except Exception as e:
            log.error(f"failed to start event mode: {e}")
            return False

    def _on_message_event(self, event: MessageEvent):
        """새 메시지 감지 시 호출. 로드 후 TTS 발화."""
        log.debug(f"message event: new_count={event.new_count}, source={event.source}")

        if not self.chat_navigator.is_active:
            log.trace("chat room inactive, ignoring event")
            return

        # 새 메시지 로드 (event.children 활용으로 GetChildren 이중 호출 방지)
        new_messages = self._load_new_messages(event.new_count, event.children)
        if new_messages:
            log.debug(f"{len(new_messages)} new message(s) loaded")
            self._announce_new_messages(new_messages)

    def _load_new_messages(self, count: int, children: list = None) -> list:
        """children 전달 시 직접 사용, 없으면 UIA 조회 (폴백)."""
        if not self.chat_navigator.chat_control:
            return []

        try:
            # children이 전달되면 직접 사용 (GetChildren 이중 호출 방지)
            if children:
                # children에서 마지막 count개 반환
                if count > 0:
                    return children[-count:]
                return []

            # children이 없으면 기존 방식 (폴백)
            msg_list = self.chat_navigator.chat_control.ListControl(
                Name="메시지",
                searchDepth=SEARCH_DEPTH_MESSAGE_LIST
            )

            if not msg_list.Exists(maxSearchSeconds=SEARCH_MAX_SECONDS_FALLBACK):
                return []

            messages = get_children_recursive(msg_list, max_depth=2, filter_empty=True)

            # 마지막 count개 반환
            if messages and count > 0:
                return messages[-count:]

            return []

        except Exception as e:
            log.trace(f"message load error: {e}")
            return []

    def _announce_new_messages(self, new_messages: list):
        """새 메시지 TTS 발화. interrupt=False로 큐 누적."""
        if not new_messages:
            return

        announced_count = 0

        # 모든 새 메시지 읽기
        for i, msg in enumerate(new_messages):
            name = getattr(msg, 'Name', '') or ''
            if not name.strip():
                continue

            # 새 메시지는 interrupt=False (TTS 큐에 누적, 발화 끊김 방지)
            speak(name, interrupt=False)
            announced_count += 1

            # 메시지 내용 로깅 (30자 제한)
            preview = name[:30] + "..." if len(name) > 30 else name
            log.trace(f"speak: {preview}")

        if announced_count > 0:
            log.debug(f"{announced_count} message(s) announced")

    def get_stats(self) -> dict:
        stats = {
            "running": self._running,
            "mode": "event",
        }

        if self._list_monitor:
            stats["list_monitor"] = self._list_monitor.get_stats()

        return stats
