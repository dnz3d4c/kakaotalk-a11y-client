# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""메시지 컨텍스트 액션 관리"""

import keyboard
from typing import Optional

from ..utils.debug import get_logger
from .base import MessageAction

log = get_logger("MessageActions")


class MessageActionManager:
    """메시지 ListItem 포커스 시 활성화되는 액션 관리"""

    def __init__(self):
        self._active = False
        self._actions: dict[str, MessageAction] = {}
        self._get_focused_item: Optional[callable] = None

    def set_focus_provider(self, getter: callable) -> None:
        """current_focused_item getter 연결."""
        self._get_focused_item = getter

    def register(self, key: str, action: MessageAction) -> None:
        """키와 액션 등록"""
        self._actions[key] = action
        log.debug(f"액션 등록: {key} -> {action.__class__.__name__}")

    def activate(self) -> None:
        """메시지 포커스 시 호출 - 핫키만 활성화"""
        if self._active:
            return
        for key, action in self._actions.items():
            keyboard.add_hotkey(key, lambda a=action: self._execute(a), suppress=False)
        self._active = True
        log.debug(f"컨텍스트 활성화: {len(self._actions)}개 액션")

    def deactivate(self) -> None:
        """포커스 벗어날 시 호출"""
        if not self._active:
            return
        for key in self._actions:
            try:
                keyboard.remove_hotkey(key)
            except KeyError:
                pass
        self._active = False
        log.debug("컨텍스트 비활성화")

    def _execute(self, action: MessageAction) -> None:
        """액션 실행을 메인 GUI 스레드로 전달 (COM 초기화 문제 방지)"""
        import wx
        wx.CallAfter(self._execute_on_main_thread, action)

    def _execute_on_main_thread(self, action: MessageAction) -> None:
        """메인 스레드에서 액션 실행. 실행 시점 컨텍스트 검증."""
        # current_focused_item이 있으면 유효한 것으로 판단 (stale 검증은 getter에서 처리)
        if self._get_focused_item:
            item = self._get_focused_item()
            if item is not None:
                log.debug(f"액션 실행 (아이템 포커스): {action.__class__.__name__}")
                try:
                    action.execute()
                    log.debug(f"액션 완료: {action.__class__.__name__}")
                except Exception as e:
                    log.error(f"액션 실패: {action.__class__.__name__} - {e}")
                return

        # 폴백: OS 포커스 기반 검증
        from ..utils.uia_utils import is_focus_in_message_list

        if not is_focus_in_message_list():
            log.debug(f"액션 무시: 메시지 목록 외부 ({action.__class__.__name__})")
            self.deactivate()
            return

        log.debug(f"액션 실행: {action.__class__.__name__}")
        try:
            action.execute()
            log.debug(f"액션 완료: {action.__class__.__name__}")
        except Exception as e:
            log.error(f"액션 실패: {action.__class__.__name__} - {e}")
