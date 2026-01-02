# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""새 메시지 자동 읽기 모듈

채팅방에서 새 메시지가 오면 자동으로 읽어주는 기능.
UIA StructureChanged 이벤트 기반으로 동작.
"""

from typing import Optional, TYPE_CHECKING

from ..accessibility import speak
from ..utils.debug import get_logger
from ..utils.uia_utils import get_children_recursive
from ..utils.uia_events import MessageListMonitor, MessageEvent

if TYPE_CHECKING:
    from .chat_room import ChatRoomNavigator

log = get_logger("MessageMonitor")


class MessageMonitor:
    """새 메시지 모니터링 클래스 (UIA 이벤트 기반)"""

    def __init__(self, chat_navigator: "ChatRoomNavigator"):
        """초기화

        Args:
            chat_navigator: 채팅방 탐색기 참조
        """
        self.chat_navigator = chat_navigator

        # 실행 상태
        self._running = False
        self._hwnd: int = 0

        # 이벤트 모니터
        self._list_monitor: Optional[MessageListMonitor] = None

        log.debug("MessageMonitor 초기화")

    def start(self, hwnd: int) -> bool:
        """모니터링 시작

        Args:
            hwnd: 채팅방 창 핸들

        Returns:
            시작 성공 여부
        """
        if self._running:
            log.trace("MessageMonitor 이미 실행 중")
            return True

        self._hwnd = hwnd
        self._running = True

        log.info(f"MessageMonitor 시작: hwnd={hwnd}")

        # 이벤트 모드 시작
        success = self._start_event_mode()
        if success:
            log.info("MessageMonitor: 이벤트 모드 활성화")
            return True

        log.error("MessageMonitor: 이벤트 모드 시작 실패")
        self._running = False
        return False

    def stop(self):
        """모니터링 중지"""
        log.debug("MessageMonitor 중지 요청")
        self._running = False

        # 이벤트 모니터 중지
        if self._list_monitor:
            self._list_monitor.stop()
            self._list_monitor = None
            log.debug("MessageListMonitor 중지됨")

        log.info("MessageMonitor 중지 완료")

    def pause(self):
        """이벤트 처리 일시 중지 (핸들러 유지, COM 재등록 없음)

        팝업메뉴 열릴 때 호출. stop/start 대신 사용하여 CPU 스파이크 방지.
        """
        if self._list_monitor:
            self._list_monitor.pause()
            log.debug("MessageMonitor 일시 중지")

    def resume(self):
        """이벤트 처리 재개

        팝업메뉴 닫힐 때 호출.
        """
        if self._list_monitor:
            self._list_monitor.resume()
            log.debug("MessageMonitor 재개")

    def is_running(self) -> bool:
        """실행 중인지 확인"""
        return self._running

    def is_paused(self) -> bool:
        """일시 중지 상태인지 확인"""
        if self._list_monitor:
            return self._list_monitor.is_paused
        return False

    def _start_event_mode(self) -> bool:
        """이벤트 모드 시작 (MessageListMonitor 사용)

        Returns:
            성공 여부
        """
        if not self.chat_navigator.chat_control:
            log.warning("chat_control 없음, 이벤트 모드 실패")
            return False

        try:
            # 메시지 목록 찾기 (searchDepth 4로 축소하여 탐색 비용 절감)
            msg_list = self.chat_navigator.chat_control.ListControl(
                Name="메시지",
                searchDepth=4
            )

            if not msg_list.Exists(maxSearchSeconds=0.5):
                log.warning("메시지 목록 없음, 이벤트 모드 실패")
                return False

            # MessageListMonitor 생성 및 시작
            self._list_monitor = MessageListMonitor(list_control=msg_list)
            self._list_monitor.start(on_message_changed=self._on_message_event)
            log.info("MessageListMonitor 시작")
            return True

        except Exception as e:
            log.error(f"이벤트 모드 시작 실패: {e}")
            return False

    def _on_message_event(self, event: MessageEvent):
        """MessageListMonitor 콜백: 새 메시지 감지됨

        Args:
            event: 메시지 이벤트 (new_count, timestamp, source, children)
        """
        log.debug(f"메시지 이벤트: new_count={event.new_count}, source={event.source}")

        if not self.chat_navigator.is_active:
            log.trace("채팅방 비활성, 이벤트 무시")
            return

        # 새 메시지 로드 (event.children 활용으로 GetChildren 이중 호출 방지)
        new_messages = self._load_new_messages(event.new_count, event.children)
        if new_messages:
            log.debug(f"새 메시지 {len(new_messages)}개 로드됨")
            self._announce_new_messages(new_messages)

    def _load_new_messages(self, count: int, children: list = None) -> list:
        """새 메시지 로드

        Args:
            count: 새 메시지 개수
            children: 이벤트에서 전달받은 children (GetChildren 이중 호출 방지)

        Returns:
            새 메시지 리스트
        """
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
                searchDepth=4
            )

            if not msg_list.Exists(maxSearchSeconds=0.3):
                return []

            messages = get_children_recursive(msg_list, max_depth=2, filter_empty=True)

            # 마지막 count개 반환
            if messages and count > 0:
                return messages[-count:]

            return []

        except Exception as e:
            log.trace(f"메시지 로드 오류: {e}")
            return []

    def _announce_new_messages(self, new_messages: list):
        """새 메시지 읽기

        Args:
            new_messages: 새 메시지 리스트
        """
        if not new_messages:
            return

        announced_count = 0

        # 모든 새 메시지 읽기
        for i, msg in enumerate(new_messages):
            name = getattr(msg, 'Name', '') or ''
            if not name.strip():
                continue

            # 시스템 메시지 필터링
            if self._is_system_message(name):
                log.trace(f"시스템 메시지 필터링: {name[:30]}...")
                continue

            # 첫 번째 메시지는 interrupt=True, 나머지는 False
            interrupt = (i == 0)
            speak(name, interrupt=interrupt)
            announced_count += 1

            # 메시지 내용 로깅 (30자 제한)
            preview = name[:30] + "..." if len(name) > 30 else name
            log.trace(f"발화: {preview}")

        if announced_count > 0:
            log.debug(f"총 {announced_count}개 메시지 발화 완료")

    def _is_system_message(self, text: str) -> bool:
        """시스템 메시지인지 확인

        Args:
            text: 메시지 텍스트

        Returns:
            시스템 메시지면 True
        """
        system_patterns = [
            "읽지 않은 메시지",
            "님이 들어왔습니다",
            "님이 나갔습니다",
        ]

        for pattern in system_patterns:
            if pattern in text:
                return True

        return False

    def get_stats(self) -> dict:
        """모니터 상태 반환"""
        stats = {
            "running": self._running,
            "mode": "event",
        }

        if self._list_monitor:
            stats["list_monitor"] = self._list_monitor.get_stats()

        return stats
