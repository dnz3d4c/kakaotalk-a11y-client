# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""포커스 모니터링 서비스

별도 스레드에서 실행되며:
- 카카오톡 창 활성화 감지
- 채팅방/메뉴 전환 감지
- ListItem/MenuItem 포커스 시 읽어줌
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
)
from .accessibility import speak
from .utils.uia_cache_request import get_focused_with_cache
from .utils.debug import get_logger

if TYPE_CHECKING:
    from .mode_manager import ModeManager
    from .navigation.message_monitor import MessageMonitor
    from .navigation import ChatRoomNavigator
    from .hotkeys import HotkeyManager

log = get_logger("FocusMonitor")


class FocusMonitorService:
    """포커스 모니터링 서비스"""

    def __init__(
        self,
        mode_manager: "ModeManager",
        message_monitor: "MessageMonitor",
        chat_navigator: "ChatRoomNavigator",
        hotkey_manager: "HotkeyManager",
    ):
        self._mode_manager = mode_manager
        self._message_monitor = message_monitor
        self._chat_navigator = chat_navigator
        self._hotkey_manager = hotkey_manager

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_focused_name: Optional[str] = None

    @property
    def is_running(self) -> bool:
        """모니터링 실행 중 여부"""
        return self._running

    @property
    def last_focused_name(self) -> Optional[str]:
        """마지막 포커스된 항목 이름 (MouseHook에서 사용)"""
        return self._last_focused_name

    def start(self) -> None:
        """모니터링 스레드 시작"""
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self._thread.start()
        log.debug("포커스 모니터 시작")

    def stop(self) -> None:
        """모니터링 스레드 종료"""
        self._running = False

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
        """포커스 모니터링 루프 - 목록/메뉴 항목 포커스 시 읽어줌

        최적화:
        1. 조건부 polling - 카카오톡 창 활성화 시에만 UIA 호출
        2. 동적 웜업 - UIA 초기화 완료 시 바로 시작 (시스템 속도에 따라 자동 조정)
        3. 적응형 polling - 상태에 따라 간격 조절
        """
        import uiautomation as auto
        import pythoncom

        pythoncom.CoInitialize()
        try:
            last_focused_type = None
            start_time = time.time()
            max_warmup = 5.0  # 최대 대기 시간 (안전장치)
            last_cleanup = start_time  # 캐시 정리 시각
            last_trace_state = (None, None, None)  # (hwnd, is_chat, nav_mode) - 중복 로깅 방지

            # UIA 비동기 초기화 (CPU 스파이크를 웜업 기간에 소화)
            uia_ready = threading.Event()

            def _warmup_uia():
                try:
                    # 별도 스레드에서 COM 초기화 필요
                    pythoncom.CoInitialize()
                    try:
                        _ = auto.GetFocusedControl()
                        log.debug("UIA 캐시 워밍업 완료")
                    finally:
                        pythoncom.CoUninitialize()
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
                    if not self._mode_manager.in_context_menu_mode:
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
                                speak(name)
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
                    last_focused_type = None
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
                else:
                    # 메인 창이면 네비게이션 모드 종료
                    # grace period: 메뉴 닫힌 후 1초간은 MessageMonitor 중지 방지
                    if self._mode_manager.in_navigation_mode and not self._mode_manager.in_context_menu_mode:
                        grace_period = 1.0
                        if self._mode_manager.should_exit_navigation_by_grace_period(grace_period):
                            self._mode_manager.exit_navigation_mode(
                                self._message_monitor,
                                self._chat_navigator,
                            )
                        else:
                            log.trace("메뉴 닫힘 grace period - MessageMonitor 유지")

                # 4. ListItemControl/TabItemControl 읽기 (CacheRequest 최적화)
                try:
                    cached = get_focused_with_cache()
                    if cached:
                        control_type = cached.control_type_name
                        name = cached.name

                        if control_type == 'ListItemControl':
                            if name and name != self._last_focused_name:
                                self._last_focused_name = name
                                last_focused_type = control_type
                                self._speak_item(name, control_type)
                        elif control_type == 'TabItemControl':
                            # 탭 항목: 선택 상태는 폴백 필요 (CacheRequest 미지원)
                            if name and name != self._last_focused_name:
                                self._last_focused_name = name
                                last_focused_type = control_type
                                # SelectionItemPattern은 기존 방식으로 조회
                                try:
                                    focused = auto.GetFocusedControl()
                                    is_selected = focused.GetSelectionItemPattern().IsSelected
                                    status = "선택됨" if is_selected else ""
                                    speak_text = f"{name} 탭 {status}".strip()
                                except Exception:
                                    speak_text = f"{name} 탭"
                                self._speak_item(speak_text, control_type)
                        else:
                            # 디버그: 다른 타입도 로깅 (최초 1회)
                            if control_type != last_focused_type:
                                log.trace(f"[기타] {control_type}: {name[:30] if name else '(no name)'}...")
                            self._last_focused_name = None
                            last_focused_type = control_type
                    else:
                        # 폴백: CacheRequest 실패 시 기존 방식
                        focused = auto.GetFocusedControl()
                        if focused:
                            control_type = focused.ControlTypeName
                            name = focused.Name or ""

                            if control_type == 'ListItemControl':
                                if name and name != self._last_focused_name:
                                    self._last_focused_name = name
                                    last_focused_type = control_type
                                    self._speak_item(name, control_type)
                            elif control_type == 'TabItemControl':
                                if name and name != self._last_focused_name:
                                    self._last_focused_name = name
                                    last_focused_type = control_type
                                    try:
                                        is_selected = focused.GetSelectionItemPattern().IsSelected
                                        status = "선택됨" if is_selected else ""
                                        speak_text = f"{name} 탭 {status}".strip()
                                    except Exception:
                                        speak_text = f"{name} 탭"
                                    self._speak_item(speak_text, control_type)
                            else:
                                if control_type != last_focused_type:
                                    log.trace(f"[기타] {control_type}: {name[:30] if name else '(no name)'}...")
                                self._last_focused_name = None
                                last_focused_type = control_type

                except Exception:
                    pass

                # 60초마다 캐시 정리 (백업)
                now = time.time()
                if now - last_cleanup > 60:
                    from .utils.uia_cache import message_list_cache
                    message_list_cache.cleanup_expired()
                    last_cleanup = now

                time.sleep(TIMING_NORMAL_POLL_INTERVAL)
        finally:
            pythoncom.CoUninitialize()

    def _speak_item(self, name: str, control_type: str = "") -> None:
        """목록/메뉴 항목 읽기"""
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

        # interrupt=False: NVDA 자동 발화와 충돌 방지
        speak(clean_name)
