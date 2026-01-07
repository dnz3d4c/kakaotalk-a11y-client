# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""포커스 모니터링 서비스

별도 스레드에서 실행되며:
- 카카오톡 창 활성화 감지
- 채팅방/메뉴 전환 감지
- ListItem/MenuItem 포커스 시 읽어줌

UIAAdapter + SpeakCallback으로 테스트 가능한 구조.
"""

import threading
import time
from typing import Optional, TYPE_CHECKING

import win32gui

from .window_finder import (
    find_kakaotalk_menu_window,
    is_kakaotalk_window,
    is_kakaotalk_chat_window,
)
from .config import (
    TIMING_MENU_MODE_POLL_INTERVAL,
    TIMING_MENU_GRACE_PERIOD,
    TIMING_GRACE_POLL_INTERVAL,
    TIMING_INACTIVE_POLL_INTERVAL,
    TIMING_NORMAL_POLL_INTERVAL,
    TIMING_MAX_WARMUP,
    TIMING_NAVIGATION_GRACE,
)
from .utils.uia_cache_request import get_focused_with_cache
from .utils.uia_events import FocusMonitor, FocusEvent
from .utils.debug import get_logger

if TYPE_CHECKING:
    from .mode_manager import ModeManager
    from .navigation.message_monitor import MessageMonitor
    from .navigation import ChatRoomNavigator
    from .hotkeys import HotkeyManager
    from .infrastructure.uia_adapter import UIAAdapter
    from .infrastructure.speak_callback import SpeakCallback

log = get_logger("FocusMonitor")


class FocusMonitorService:
    """포커스 모니터링 서비스. UIAAdapter + SpeakCallback 의존성 주입."""

    def __init__(
        self,
        mode_manager: "ModeManager",
        message_monitor: "MessageMonitor",
        chat_navigator: "ChatRoomNavigator",
        hotkey_manager: "HotkeyManager",
        uia_adapter: Optional["UIAAdapter"] = None,
        speak_callback: Optional["SpeakCallback"] = None,
    ):
        self._mode_manager = mode_manager
        self._message_monitor = message_monitor
        self._chat_navigator = chat_navigator
        self._hotkey_manager = hotkey_manager

        # 의존성 주입 (테스트 시 mock 가능)
        from .infrastructure.uia_adapter import get_default_uia_adapter
        from .infrastructure.speak_callback import get_default_speak_callback
        self._uia = uia_adapter or get_default_uia_adapter()
        self._speak = speak_callback or get_default_speak_callback()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_focused_name: Optional[str] = None
        self._focus_monitor: Optional[FocusMonitor] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def last_focused_name(self) -> Optional[str]:
        """MouseHook에서 비메시지 항목 판단용으로 사용."""
        return self._last_focused_name

    def start(self) -> None:
        """FocusMonitor + 폴링 스레드 시작."""
        self._running = True

        # FocusMonitor 시작 (이벤트 기반 ListItem/TabItem 읽기)
        self._focus_monitor = FocusMonitor()
        self._focus_monitor.start(on_focus_changed=self._on_focus_event)
        log.debug(f"FocusMonitor 시작 (mode={self._focus_monitor.get_stats()['mode']})")

        # 폴링 스레드 시작 (메뉴/채팅방 감지)
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self._thread.start()
        log.debug("포커스 모니터 시작")

    def stop(self) -> None:
        """스레드 종료. 최대 2초 대기 후 강제 진행."""
        self._running = False

        # FocusMonitor 종료
        if self._focus_monitor:
            self._focus_monitor.stop()
            self._focus_monitor = None
            log.debug("FocusMonitor 종료")

        if self._thread and self._thread.is_alive():
            # 1차 대기 (1초)
            self._thread.join(timeout=1.0)

            if self._thread.is_alive():
                log.debug("focus monitor 스레드 1차 대기 타임아웃, 재시도")
                self._running = False
                # 2차 대기 (1초)
                self._thread.join(timeout=1.0)

                if self._thread.is_alive():
                    log.debug("focus monitor 스레드 종료 실패 - 강제 진행")

        self._thread = None
        log.debug("포커스 모니터 종료")

    def _monitor_loop(self) -> None:
        """메뉴/채팅방 감지 + 모드 전환. 카카오톡 비활성 시 CPU 절약."""
        # COM 초기화 (UIAAdapter가 스레드별 관리)
        self._uia.init_com()

        try:
            start_time = time.time()
            max_warmup = TIMING_MAX_WARMUP
            last_cleanup = start_time  # 캐시 정리 시각
            last_trace_state = (None, None, None)  # (hwnd, is_chat, nav_mode) - 중복 로깅 방지

            # UIA 비동기 초기화 (CPU 스파이크를 웜업 기간에 소화)
            uia_ready = threading.Event()

            def _warmup_uia():
                try:
                    # 별도 스레드에서 COM 초기화 필요
                    self._uia.init_com()
                    try:
                        _ = self._uia.get_focused_control()
                        log.debug("UIA 캐시 워밍업 완료")
                    finally:
                        self._uia.uninit_com()
                except Exception as e:
                    log.warning(f"UIA 워밍업 실패: {e}")
                finally:
                    uia_ready.set()

            warmup_thread = threading.Thread(target=_warmup_uia, daemon=True)
            warmup_thread.start()

            # 초기화 완료 또는 최대 시간까지 대기
            while self._running:
                elapsed = time.time() - start_time
                if uia_ready.is_set():
                    log.debug(f"UIA 워밍업 완료, {elapsed:.2f}초 소요")
                    break
                if elapsed >= max_warmup:
                    log.warning(f"UIA 워밍업 타임아웃 ({max_warmup}초)")
                    break
                time.sleep(0.1)

            # 이후 정상 포커스 모니터링
            while self._running:

                # 1. 메뉴 창 존재 여부 확인 (포그라운드와 무관하게 visible한 EVA_Menu 찾기)
                menu_hwnd = find_kakaotalk_menu_window()
                fg_hwnd = win32gui.GetForegroundWindow()

                if menu_hwnd:
                    # 메뉴 창 존재 → 메뉴 모드
                    first_entry = not self._mode_manager.in_context_menu_mode
                    if first_entry:
                        self._mode_manager.enter_context_menu_mode(self._message_monitor)
                        log.trace(f"메뉴 모드 자동 진입 (menu_hwnd={menu_hwnd})")

                    # grace period 갱신
                    self._mode_manager.update_menu_closed_time()

                    # 메뉴 항목 읽기 (CacheRequest 사용, 위임 없이 직접 처리)
                    try:
                        cached = get_focused_with_cache()
                        if cached and cached.control_type_name == 'MenuItemControl':
                            name = cached.name
                            if name and name != self._last_focused_name:
                                self._last_focused_name = name
                                self._speak(name)
                        elif first_entry:
                            # 포커스 리다이렉트: 메뉴 컨테이너 포커스 시 첫 번째 메뉴 항목 읽기
                            first_item_name = self._get_first_menu_item_name(menu_hwnd)
                            if first_item_name:
                                self._last_focused_name = first_item_name
                                self._speak(first_item_name)
                                log.trace(f"메뉴 첫 항목 리다이렉트: {first_item_name}")
                    except Exception:
                        # COMError 등 발생 시 폴백: 첫 메뉴 항목 읽기 시도
                        if first_entry:
                            try:
                                first_item_name = self._get_first_menu_item_name(menu_hwnd)
                                if first_item_name:
                                    self._last_focused_name = first_item_name
                                    self._speak(first_item_name)
                                    log.trace(f"메뉴 첫 항목 폴백: {first_item_name}")
                            except Exception:
                                pass

                    time.sleep(TIMING_MENU_MODE_POLL_INTERVAL)
                    continue
                else:
                    # 메뉴 창 없음 → 메뉴 모드 종료 (grace period 적용)
                    if self._mode_manager.in_context_menu_mode:
                        # grace period: 마지막 메뉴 감지 후 일정 시간 동안 resume 지연
                        # (하위 메뉴 전환 시 잠깐 창 없어지는 현상 대응)
                        menu_grace = TIMING_MENU_GRACE_PERIOD
                        if self._mode_manager.should_exit_navigation_by_grace_period(menu_grace):
                            self._mode_manager.exit_context_menu_mode(self._message_monitor)
                            self._last_focused_name = None  # 메뉴 종료 후 리셋 (중복 체크 방지)
                            log.trace("메뉴 모드 자동 종료")
                        else:
                            # grace period 동안은 나머지 코드 스킵 (_last_focused_name 리셋 방지)
                            time.sleep(TIMING_GRACE_POLL_INTERVAL)
                            continue

                # 2. 카카오톡 창이 아니면 UIA 호출 안 함 (CPU 절약)
                if not fg_hwnd or not is_kakaotalk_window(fg_hwnd):
                    # 비활성 상태: 네비게이션 모드 종료 (컨텍스트 메뉴 모드가 아닐 때만)
                    if self._mode_manager.in_navigation_mode and not self._mode_manager.in_context_menu_mode:
                        self._mode_manager.exit_navigation_mode(
                            self._message_monitor,
                            self._chat_navigator,
                        )
                    # 메뉴 모드 종료
                    if self._mode_manager.in_context_menu_mode:
                        self._mode_manager.exit_context_menu_mode(self._message_monitor)
                        log.trace("메뉴 모드 자동 종료 (비카카오톡 창)")
                    self._last_focused_name = None
                    time.sleep(TIMING_INACTIVE_POLL_INTERVAL)
                    continue

                # 3. 채팅방 창이면 자동으로 네비게이션 모드 진입
                is_chat = is_kakaotalk_chat_window(fg_hwnd)
                current_trace_state = (fg_hwnd, is_chat, self._mode_manager.in_navigation_mode)
                if current_trace_state != last_trace_state:
                    log.trace(f"포커스 모니터: hwnd={fg_hwnd}, is_chat={is_chat}, nav_mode={self._mode_manager.in_navigation_mode}")
                    last_trace_state = current_trace_state
                if is_chat:
                    # 메뉴 모드일 때는 채팅방 진입 로직 스킵 (CPU 스파이크 방지)
                    if self._mode_manager.in_context_menu_mode:
                        pass  # 메뉴 탐색 중에는 재진입 불필요
                    elif not self._mode_manager.in_navigation_mode or self._mode_manager.current_chat_hwnd != fg_hwnd:
                        log.debug(f"채팅방 진입 시도: hwnd={fg_hwnd}")
                        self._mode_manager.enter_navigation_mode(
                            fg_hwnd,
                            self._chat_navigator,
                            self._message_monitor,
                            self._hotkey_manager,
                        )
                        log.debug(f"채팅방 진입 결과: nav_mode={self._mode_manager.in_navigation_mode}")

                        # 채팅방 진입 성공 시 현재 포커스된 항목 읽기
                        if self._mode_manager.in_navigation_mode:
                            self._speak_current_focus()
                else:
                    # 메인 창이면 네비게이션 모드 종료
                    # grace period: 메뉴 닫힌 후 일정 시간 MessageMonitor 중지 방지
                    if self._mode_manager.in_navigation_mode and not self._mode_manager.in_context_menu_mode:
                        if self._mode_manager.should_exit_navigation_by_grace_period(TIMING_NAVIGATION_GRACE):
                            self._mode_manager.exit_navigation_mode(
                                self._message_monitor,
                                self._chat_navigator,
                            )
                        else:
                            log.trace("메뉴 닫힘 grace period - MessageMonitor 유지")

                # 4. ListItem/TabItem 읽기는 FocusMonitor에서 이벤트 기반으로 처리

                # 60초마다 캐시 정리 (백업)
                now = time.time()
                if now - last_cleanup > 60:
                    from .utils.uia_cache import message_list_cache
                    message_list_cache.cleanup_expired()
                    last_cleanup = now

                time.sleep(TIMING_NORMAL_POLL_INTERVAL)
        finally:
            # COM 해제
            self._uia.uninit_com()

    def _on_focus_event(self, event: FocusEvent) -> None:
        """ListItem/TabItem/ListControl 포커스 시 읽기."""
        if not self._running:
            return

        try:
            control = event.control
            control_type = control.ControlTypeName
            name = control.Name or ""

            if control_type == 'ListItemControl':
                if name and name != self._last_focused_name:
                    self._last_focused_name = name
                    self._speak_item(name, control_type)
                    # chat_navigator에 현재 항목 저장 (컨텍스트 메뉴용)
                    self._chat_navigator.current_focused_item = control
                    log.trace(f"[이벤트] ListItem: {name[:30]}...")
            elif control_type == 'TabItemControl':
                if name and name != self._last_focused_name:
                    self._last_focused_name = name
                    # SelectionItemPattern으로 선택 상태 조회
                    try:
                        is_selected = control.GetSelectionItemPattern().IsSelected
                        status = "선택됨" if is_selected else ""
                        speak_text = f"{name} 탭 {status}".strip()
                    except Exception:
                        speak_text = f"{name} 탭"
                    self._speak_item(speak_text, control_type)
                    log.trace(f"[이벤트] TabItem: {name}")
            elif control_type == 'ListControl' and name == "메시지":
                # 메시지 목록상자 포커스 시 마지막 메시지 읽기
                self._speak_last_message(control)
        except Exception as e:
            log.trace(f"포커스 이벤트 처리 오류: {e}")

    def _speak_current_focus(self) -> None:
        """채팅방 진입 시 현재 포커스 강제 조회. 이벤트 누락 보완용."""
        try:
            cached = get_focused_with_cache()
            if not cached:
                log.trace("현재 포커스 없음")
                return

            if cached.control_type_name != 'ListItemControl':
                log.trace(f"포커스가 ListItem 아님: {cached.control_type_name}")
                return

            name = cached.name or ""
            if not name.strip():
                log.trace("포커스 항목 이름 없음")
                return

            # 중복 방지
            if name == self._last_focused_name:
                return

            self._last_focused_name = name
            self._speak(name)

            # chat_navigator에 현재 항목 저장 (컨텍스트 메뉴용)
            self._chat_navigator.current_focused_item = cached

            log.debug(f"채팅방 진입 시 현재 항목: {name[:30]}...")

        except Exception as e:
            log.trace(f"현재 포커스 항목 읽기 실패: {e}")

    def _speak_last_message(self, list_control) -> None:
        """메시지 목록상자 포커스 시 마지막 메시지 읽기."""
        try:
            children = self._uia.get_direct_children(list_control)
            if not children:
                log.trace("메시지 목록 비어있음")
                return

            last_msg = children[-1]
            name = last_msg.Name or ""
            if not name.strip():
                log.trace("마지막 메시지 이름 없음")
                return

            # 중복 방지
            if name == self._last_focused_name:
                return

            self._last_focused_name = name
            self._speak(name)
            log.trace(f"[이벤트] 마지막 메시지: {name[:30]}...")

        except Exception as e:
            log.trace(f"마지막 메시지 읽기 실패: {e}")

    def _get_first_menu_item_name(self, menu_hwnd: int) -> Optional[str]:
        """메뉴 창의 첫 번째 항목 이름. 포커스 리다이렉트용."""
        try:
            menu_control = self._uia.get_control_from_handle(menu_hwnd)
            if not menu_control:
                return None

            # 첫 번째 MenuItem 찾기
            first_item = self._uia.find_menu_item_control(menu_control, search_depth=3)
            if first_item and self._uia.control_exists(first_item, max_seconds=0):
                return first_item.Name
        except Exception as e:
            log.trace(f"첫 메뉴 항목 조회 실패: {e}")
        return None

    def _speak_item(self, name: str, control_type: str = "") -> None:
        """AccessKey 제거 후 읽기. MenuItemControl은 앞글자 제거."""
        try:
            log.trace(f"[{control_type}] {name[:50]}...")
        except UnicodeEncodeError:
            log.trace("(encoding error)")

        # 이모지 등 특수문자 제거 후 읽기
        clean_name = name.replace('\u2022', '').replace('\u00a0', ' ')

        # MenuItemControl AccessKey 제거 (예: 'k채팅방' → '채팅방')
        if control_type == 'MenuItemControl' and len(clean_name) > 1:
            if clean_name[0].isalpha() and ord(clean_name[1]) >= 0xAC00:
                clean_name = clean_name[1:]

        # SpeakCallback으로 음성 출력
        self._speak(clean_name)
