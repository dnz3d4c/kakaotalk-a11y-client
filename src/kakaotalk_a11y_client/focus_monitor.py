# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""포커스 모니터링 서비스

별도 스레드에서 실행되며:
- 카카오톡 창 활성화 감지
- 채팅방/메뉴 전환 감지
- ListItem/MenuItem 포커스 시 읽어줌

UIAAdapter + speak 콜백으로 테스트 가능한 구조.
"""

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, TYPE_CHECKING

import win32gui

from .window_finder import (
    is_kakaotalk_window,
    is_kakaotalk_chat_window,
)
from .utils.menu_handler import get_menu_handler, MenuHandler
from .config import (
    KAKAO_MESSAGE_LIST_NAME,
    TIMING_MENU_MODE_POLL_INTERVAL,
    TIMING_INACTIVE_POLL_INTERVAL,
    TIMING_NORMAL_POLL_INTERVAL,
    TIMING_MAX_WARMUP,
    TIMING_WARMUP_POLL_INTERVAL,
    TIMING_SPEAK_DEDUPE_SECS,
    TIMING_CACHE_CLEANUP_INTERVAL,
    TIMING_THREAD_JOIN_TIMEOUT,
    ENTRY_MAX_RETRIES,
    ENTRY_COOLDOWN_SECS,
)
from .utils.uia_cache_request import get_focused_with_cache
from .utils.uia_utils import is_focus_in_message_list
from .utils.uia_events import FocusMonitor, FocusEvent
from .utils.debug import get_logger

if TYPE_CHECKING:
    from .mode_manager import ModeManager
    from .navigation.message_monitor import MessageMonitor
    from .navigation import ChatRoomNavigator
    from .hotkeys import HotkeyManager
    from .infrastructure.uia_adapter import UIAAdapter
    from .message_actions import MessageActionManager

log = get_logger("FocusMonitor")


@dataclass
class FocusContext:
    """포커스 이벤트에서 추출한 컨텍스트."""
    control: object  # auto.Control
    control_type: str
    name: str


class FocusMonitorService:
    """포커스 모니터링 서비스. UIAAdapter + speak 콜백 의존성 주입."""

    def __init__(
        self,
        mode_manager: "ModeManager",
        message_monitor: "MessageMonitor",
        chat_navigator: "ChatRoomNavigator",
        hotkey_manager: "HotkeyManager",
        uia_adapter: Optional["UIAAdapter"] = None,
        speak_callback: Optional[Callable[[str], None]] = None,
        message_actions: Optional["MessageActionManager"] = None,
    ):
        self._mode_manager = mode_manager
        self._message_monitor = message_monitor
        self._chat_navigator = chat_navigator
        self._hotkey_manager = hotkey_manager
        self._message_actions = message_actions

        # 의존성 주입 (테스트 시 mock 가능)
        from .infrastructure.uia_adapter import get_default_uia_adapter
        from .accessibility import speak
        self._uia = uia_adapter or get_default_uia_adapter()
        self._speak = speak_callback or speak

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_focused_name: Optional[str] = None  # 중복 발화 방지용
        self._last_focused_id: Optional[tuple] = None  # RuntimeId 기반 중복 체크
        self._last_focused_lock = threading.Lock()
        self._focus_monitor: Optional[FocusMonitor] = None

        # RuntimeId 없을 때 Name + 시간 기반 중복 체크
        self._last_speak_time: float = 0.0

        # 채팅방 진입 무한 재시도 방지
        self._entry_fail_counts: dict[int, int] = {}  # hwnd -> 실패 횟수
        self._entry_cooldowns: dict[int, float] = {}  # hwnd -> 쿨다운 종료 시간

        # 중복 로깅 방지 (모니터 루프용)
        self._last_trace_state: tuple = (None, None, None)  # (hwnd, is_chat, nav_mode)

        # 메뉴 핸들러 (싱글톤)
        self._menu_handler: MenuHandler = get_menu_handler()
        self._menu_handler.set_speak_callback(self._speak)

        # 포커스 디스패치 테이블 (ControlTypeName → 핸들러)
        # ListControl/MenuControl 등 컨테이너는 uia_focus_handler에서 조기 차단됨
        self._focus_handlers: dict[str, Callable[[FocusContext], None]] = {
            'ListItemControl': self._handle_list_item_focus,
            'MenuItemControl': self._handle_menu_item_focus,
        }

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def in_menu_mode(self) -> bool:
        """메뉴 모드 여부. GUI 상태 표시용."""
        return self._menu_handler.in_menu_mode

    # === 네비게이션 모드 조율 ===

    def _enter_navigation_mode(self, hwnd: int) -> bool:
        """채팅방 진입 + MessageMonitor 시작. 선택 모드면 자동 종료."""
        # 선택 모드면 먼저 종료
        if self._mode_manager.in_selection_mode:
            self._mode_manager.exit_selection_mode(self._hotkey_manager)

        # 채팅방 진입
        log.debug(f"attempting chat room entry: hwnd={hwnd}")
        if self._chat_navigator.enter_chat_room(hwnd):
            self._mode_manager.set_navigation_mode(hwnd)
            self._message_monitor.start(hwnd)
            log.debug(f"chat room entry success: hwnd={hwnd}")
            return True
        log.debug(f"chat room entry failed: hwnd={hwnd}")
        return False

    def _exit_navigation_mode(self) -> None:
        """MessageMonitor 중지 + 채팅방 종료. 개별 try-except로 전체 실행 보장."""
        if self._message_actions:
            try:
                self._message_actions.deactivate()
            except Exception as e:
                log.trace(f"message_actions deactivate failed: {e}")

        try:
            self._mode_manager.clear_navigation_mode()
        except Exception as e:
            log.trace(f"clear_navigation_mode failed: {e}")

        try:
            self._message_monitor.stop()
        except Exception as e:
            log.trace(f"message_monitor stop failed: {e}")

        try:
            self._chat_navigator.exit_chat_room()
        except Exception as e:
            log.trace(f"exit_chat_room failed: {e}")

    def start(self) -> None:
        """FocusMonitor + 폴링 스레드 시작."""
        self._running = True

        # ElementSelected → FocusEvent 콜백 설정 (NVDA gainFocus 패턴)
        self._message_monitor.set_selection_callback(self._on_focus_event)

        # FocusMonitor 시작 (이벤트 기반 ListItem/TabItem 읽기)
        self._focus_monitor = FocusMonitor()
        self._focus_monitor.start(on_focus_changed=self._on_focus_event)
        log.debug(f"FocusMonitor started (mode={self._focus_monitor.get_stats()['mode']})")

        # 폴링 스레드 시작 (메뉴/채팅방 감지)
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self._thread.start()
        log.debug("focus monitor started")

    def stop(self) -> None:
        """스레드 종료. 최대 2초 대기 후 강제 진행."""
        self._running = False

        # FocusMonitor 종료
        if self._focus_monitor:
            self._focus_monitor.stop()
            self._focus_monitor = None
            log.debug("FocusMonitor stopped")

        if self._thread and self._thread.is_alive():
            # 1차 대기
            self._thread.join(timeout=TIMING_THREAD_JOIN_TIMEOUT)

            if self._thread.is_alive():
                log.debug("focus monitor thread first wait timeout, retrying")
                self._running = False
                # 2차 대기
                self._thread.join(timeout=TIMING_THREAD_JOIN_TIMEOUT)

                if self._thread.is_alive():
                    log.debug("focus monitor thread stop failed - forcing exit")

        self._thread = None
        log.debug("focus monitor stopped")

    def _monitor_loop(self) -> None:
        """메뉴/채팅방 감지 + 모드 전환. 카카오톡 비활성 시 CPU 절약."""
        # COM 초기화 (UIAAdapter가 스레드별 관리)
        self._uia.init_com()

        try:
            start_time = time.time()
            max_warmup = TIMING_MAX_WARMUP
            last_cleanup = start_time  # 캐시 정리 시각

            # UIA 비동기 초기화 (CPU 스파이크를 웜업 기간에 소화)
            uia_ready = threading.Event()

            def _warmup_uia():
                try:
                    # 별도 스레드에서 COM 초기화 필요
                    self._uia.init_com()
                    try:
                        # 기존 워밍업
                        _ = self._uia.get_focused_control()

                        # CacheRequestManager 프리로드 추가
                        from .utils.uia_cache_request import get_cache_manager
                        get_cache_manager()  # 싱글톤 초기화

                        log.debug("UIA cache warmup completed")
                    finally:
                        self._uia.uninit_com()
                except Exception as e:
                    log.warning(f"UIA warmup failed: {e}")
                finally:
                    uia_ready.set()

            warmup_thread = threading.Thread(target=_warmup_uia, daemon=True)
            warmup_thread.start()

            # 초기화 완료 또는 최대 시간까지 대기
            while self._running:
                elapsed = time.time() - start_time
                if uia_ready.is_set():
                    log.debug(f"UIA warmup completed in {elapsed:.2f}s")
                    break
                if elapsed >= max_warmup:
                    log.warning(f"UIA warmup timeout ({max_warmup}s)")
                    break
                time.sleep(TIMING_WARMUP_POLL_INTERVAL)

            # 이후 정상 포커스 모니터링
            while self._running:
                sleep_interval = self._process_menu_state()
                if sleep_interval:
                    time.sleep(sleep_interval)
                    continue

                fg_hwnd = win32gui.GetForegroundWindow()
                sleep_interval = self._process_kakaotalk_window(fg_hwnd)
                if sleep_interval:
                    time.sleep(sleep_interval)
                    continue

                self._process_chat_navigation(fg_hwnd)
                last_cleanup = self._periodic_maintenance(last_cleanup)
                time.sleep(TIMING_NORMAL_POLL_INTERVAL)
        finally:
            # COM 해제
            self._uia.uninit_com()

    def _process_menu_state(self) -> Optional[float]:
        """메뉴 창 감지 + 모드 전환. 메뉴 모드면 폴링 간격 반환, 아니면 None."""
        menu_hwnd = self._menu_handler.find_menu_window()

        if menu_hwnd:
            # 메뉴 창 존재 → 메뉴 모드
            if not self._menu_handler.in_menu_mode:
                self._menu_handler.enter_menu_mode(menu_hwnd)
                # MessageMonitor pause
                if self._message_monitor and self._message_monitor.is_running():
                    self._message_monitor.pause()

            return TIMING_MENU_MODE_POLL_INTERVAL
        else:
            # 메뉴 창 없음 → 메뉴 모드 즉시 종료
            if self._menu_handler.in_menu_mode:
                self._menu_handler.exit_menu_mode()
                # MessageMonitor resume
                if self._message_monitor and self._message_monitor.is_running():
                    self._message_monitor.resume()
                with self._last_focused_lock:
                    self._last_focused_name = None
                    self._last_focused_id = None
                # 메뉴 종료 후 현재 포커스 즉시 읽기
                self._speak_current_focus()

        return None

    def _process_kakaotalk_window(self, fg_hwnd: int) -> Optional[float]:
        """비카카오톡 창 처리. 비활성이면 폴링 간격 반환, 아니면 None."""
        if not fg_hwnd or not is_kakaotalk_window(fg_hwnd):
            # 비활성 상태: 네비게이션 모드 종료 (메뉴 모드가 아닐 때만)
            if self._mode_manager.in_navigation_mode and not self._menu_handler.in_menu_mode:
                self._exit_navigation_mode()
            # 메뉴 모드 종료
            if self._menu_handler.in_menu_mode:
                self._menu_handler.exit_menu_mode()
                if self._message_monitor and self._message_monitor.is_running():
                    self._message_monitor.resume()
            with self._last_focused_lock:
                self._last_focused_name = None
                self._last_focused_id = None
            return TIMING_INACTIVE_POLL_INTERVAL

        return None

    def _process_chat_navigation(self, fg_hwnd: int) -> None:
        """채팅방 감지 + 네비게이션 모드 전환."""
        is_chat = is_kakaotalk_chat_window(fg_hwnd)
        current_trace_state = (fg_hwnd, is_chat, self._mode_manager.in_navigation_mode)
        if current_trace_state != self._last_trace_state:
            log.trace(f"focus monitor: hwnd={fg_hwnd}, is_chat={is_chat}, nav_mode={self._mode_manager.in_navigation_mode}")
            self._last_trace_state = current_trace_state
        if is_chat:
            # 메뉴 모드일 때는 채팅방 진입 로직 스킵 (CPU 스파이크 방지)
            if self._menu_handler.in_menu_mode:
                pass  # 메뉴 탐색 중에는 재진입 불필요
            elif not self._mode_manager.is_same_chat_room(fg_hwnd):
                # 쿨다운 체크 (무한 재시도 방지)
                now = time.time()
                if fg_hwnd in self._entry_cooldowns and now < self._entry_cooldowns[fg_hwnd]:
                    pass  # 쿨다운 중 - 진입 시도 스킵
                else:
                    result = self._enter_navigation_mode(fg_hwnd)
                    if not result:
                        # 실패 횟수 증가
                        self._entry_fail_counts[fg_hwnd] = self._entry_fail_counts.get(fg_hwnd, 0) + 1
                        if self._entry_fail_counts[fg_hwnd] >= ENTRY_MAX_RETRIES:
                            self._entry_cooldowns[fg_hwnd] = now + ENTRY_COOLDOWN_SECS
                            log.warning(f"chat room entry failed {ENTRY_MAX_RETRIES} times, cooldown 30s: hwnd={fg_hwnd}")
                    else:
                        # 성공 시 카운터 리셋
                        self._entry_fail_counts.pop(fg_hwnd, None)
                        self._entry_cooldowns.pop(fg_hwnd, None)

                # 채팅방 진입 성공 시 현재 포커스된 항목 읽기
                if self._mode_manager.in_navigation_mode:
                    self._speak_current_focus()
        else:
            # 메인 창이면 네비게이션 모드 종료
            if self._mode_manager.in_navigation_mode and not self._menu_handler.in_menu_mode:
                self._exit_navigation_mode()

    def _periodic_maintenance(self, last_cleanup: float) -> float:
        """60초마다 캐시 정리. 갱신된 last_cleanup 반환."""
        now = time.time()
        if now - last_cleanup > TIMING_CACHE_CLEANUP_INTERVAL:
            from .utils.uia_cache import message_list_cache
            message_list_cache.cleanup_expired()
            # hwnd 판별 캐시 정리 (닫힌 창 제거)
            from .window_finder import invalidate_hwnd_class_cache
            invalidate_hwnd_class_cache()
            return now
        return last_cleanup

    def _on_focus_event(self, event: FocusEvent) -> None:
        """ListItem/MenuItem 포커스 시 읽기. 컨테이너는 uia_focus_handler에서 차단됨."""
        if not self._running:
            return

        # 메뉴 모드 중 ListItem 이벤트 무시
        try:
            control_type = event.control.ControlTypeName
            if control_type == 'ListItemControl':
                if self._menu_handler.in_menu_mode:
                    log.trace(f"[메뉴모드] {control_type} 이벤트 무시")
                    return
        except Exception as e:
            log.trace(f"menu mode check failed: {e}")

        try:
            ctx = FocusContext(
                control=event.control,
                control_type=event.control.ControlTypeName,
                name=event.control.Name or "",
            )

            handler = self._focus_handlers.get(ctx.control_type)
            if handler:
                handler(ctx)
            else:
                self._deactivate_message_actions()
        except Exception as e:
            log.trace(f"focus event handling error: {e}")

    def _handle_list_item_focus(self, ctx: FocusContext) -> None:
        """ListItem 포커스: 브리징 체크 → 메시지 액션 → 중복 체크 → 발화."""
        if self._menu_handler.is_bridging_period():
            log.trace("[브리징 방지] 메뉴 종료 직후 ListItem 무시")
            return

        self._update_message_actions_for_list_item()

        if self._is_duplicate_focus(ctx.control, ctx.name):
            return

        if ctx.name:
            self._speak_item(ctx.name, ctx.control_type)
            self._chat_navigator.current_focused_item = ctx.control
            log.trace(f"[이벤트] ListItem: {ctx.name[:30]}...")

    def _handle_menu_item_focus(self, ctx: FocusContext) -> None:
        """MenuItem 포커스: MenuHandler에 위임."""
        self._deactivate_message_actions()
        self._menu_handler.handle_menu_item_focus(
            ctx.control, ctx.name, self._is_duplicate_focus
        )

    def _update_message_actions_for_list_item(self) -> None:
        """ListItem 포커스 시 메시지 액션 상태 결정."""
        if not self._message_actions:
            return
        if (self._mode_manager.in_navigation_mode
                and not self._menu_handler.in_menu_mode):
            self._message_actions.activate()
        else:
            self._message_actions.deactivate()

    def _deactivate_message_actions(self) -> None:
        """메시지 액션 비활성화."""
        if self._message_actions:
            self._message_actions.deactivate()

    def _speak_current_focus(self) -> None:
        """채팅방 진입 시 현재 포커스 강제 조회. 이벤트 누락 보완용."""
        try:
            cached = get_focused_with_cache()
            if not cached:
                log.trace("no current focus")
                return

            if cached.control_type_name == 'ListItemControl':
                self._speak_current_focus_item(cached)
            elif (cached.control_type_name == 'ListControl'
                  and cached.name == KAKAO_MESSAGE_LIST_NAME):
                # 컨테이너 폴백: OS 포커스가 목록 자체에 있을 때 마지막 메시지 읽기
                log.trace("container fallback: reading last message")
                self._speak_last_message(cached.raw_element)
            else:
                log.trace(f"focus is not ListItem: {cached.control_type_name}")

        except Exception as e:
            log.trace(f"failed to read current focus item: {e}")

    def _speak_current_focus_item(self, cached) -> None:
        """ListItem 포커스 발화. _speak_current_focus에서 분리."""
        name = cached.name or ""
        if not name.strip():
            log.trace("focused item has no name")
            return

        # RuntimeId로 중복 체크
        runtime_id = None
        try:
            if cached.raw_element:
                runtime_id = tuple(cached.raw_element.GetRuntimeId())
        except Exception:
            pass

        with self._last_focused_lock:
            if runtime_id and runtime_id == self._last_focused_id:
                return
            self._last_focused_id = runtime_id
            self._last_focused_name = name

        # 메시지 액션 활성화 (채팅방 복귀 시 재등록)
        if (self._message_actions
            and self._mode_manager.in_navigation_mode
            and is_focus_in_message_list()):
            self._message_actions.activate()

        self._speak(name)

        # chat_navigator에 현재 항목 저장 (컨텍스트 메뉴용)
        self._chat_navigator.current_focused_item = cached

        log.debug(f"current item on chat entry: {name[:30]}...")

    def _speak_last_message(self, list_control) -> None:
        """메시지 목록상자 포커스 시 마지막 메시지 읽기."""
        try:
            children = None

            # MessageListMonitor 캐시 활용 시도
            if (self._message_monitor and
                hasattr(self._message_monitor, '_list_monitor') and
                self._message_monitor._list_monitor):
                cached = getattr(self._message_monitor._list_monitor, 'initial_children', None)
                if cached:
                    children = cached
                    log.trace("_speak_last_message: using cached children")

            # 폴백: 동기 UIA 호출
            if not children:
                children = self._uia.get_direct_children(list_control)
                log.trace("_speak_last_message: sync query")

            if not children:
                log.trace("message list is empty")
                return

            last_msg = children[-1]
            name = last_msg.Name or ""
            if not name.strip():
                log.trace("last message has no name")
                return

            # RuntimeId로 중복 체크
            runtime_id = getattr(last_msg, 'RuntimeId', None)
            with self._last_focused_lock:
                if runtime_id and runtime_id == self._last_focused_id:
                    return
                self._last_focused_id = runtime_id
                self._last_focused_name = name

            self._speak(name)
            log.trace(f"[이벤트] 마지막 메시지: {name[:30]}...")

        except Exception as e:
            log.trace(f"failed to read last message: {e}")

    def _is_duplicate_focus(self, control, name: str) -> bool:
        """RuntimeId 또는 Name+시간 기반 중복 체크. True면 스킵.

        - RuntimeId 있으면 RuntimeId로만 체크
        - RuntimeId 없으면 Name + 시간으로 폴백 (TIMING_SPEAK_DEDUPE_SECS 이내)
        """
        runtime_id = getattr(control, 'RuntimeId', None)
        now = time.time()

        with self._last_focused_lock:
            if runtime_id:
                if runtime_id == self._last_focused_id:
                    return True
                self._last_focused_id = runtime_id
                self._last_focused_name = name
                return False
            else:
                if (name == self._last_focused_name and
                    now - self._last_speak_time < TIMING_SPEAK_DEDUPE_SECS):
                    return True
                self._last_focused_name = name
                self._last_speak_time = now
                return False

    def _speak_item(self, name: str, control_type: str = "") -> None:
        """특수문자 제거 후 음성+점자 출력."""
        try:
            log.trace(f"[{control_type}] {name[:50]}...")
        except UnicodeEncodeError:
            log.trace("(encoding error)")

        # 이모지 등 특수문자 제거 후 읽기
        clean_name = name.replace('\u2022', '').replace('\u00a0', ' ')

        # SpeakCallback으로 음성 출력
        self._speak(clean_name)

