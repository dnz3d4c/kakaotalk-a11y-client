# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""메인 진입점 - 전체 플로우 조율"""

import argparse
import atexit
import signal
import sys
import threading
import time
from typing import Optional

import win32gui

from .window_finder import (
    find_chat_window,
    get_client_rect,
    check_kakaotalk_running,
    check_uia_available,
    is_kakaotalk_chat_window,
    is_kakaotalk_window,
)
from .detector import capture_region, detect_emojis, load_templates, format_detection_result
from .clicker import click_emoji
from .accessibility import (
    speak,
    announce_scan_start,
    announce_scan_result,
    announce_cancel,
    announce_error,
    announce_selection,
)
from .hotkeys import HotkeyManager, wait_for_exit
from .navigation import ChatRoomNavigator
from .navigation.message_monitor import MessageMonitor
from .utils.debug import get_logger, is_debug_enabled, get_log_file_path, set_global_level, LogLevel
from .utils.profiler import profiler, profile_logger

log = get_logger("Main")


class EmojiClicker:
    """카카오톡 이모지 클리커 메인 클래스"""

    def __init__(self):
        self.hotkey_manager = HotkeyManager()
        self.templates = None
        self.current_detections: list[dict] = []
        self.current_window_offset: tuple[int, int] = (0, 0)
        self._in_selection_mode = False

        # 네비게이션 관련
        self.chat_navigator = ChatRoomNavigator()
        self.message_monitor = MessageMonitor(self.chat_navigator)
        self._in_navigation_mode = False
        self._in_context_menu_mode = False
        self._current_chat_hwnd: Optional[int] = None
        self._focus_monitor_running = False
        self._focus_thread: Optional[threading.Thread] = None

    def initialize(self) -> bool:
        """초기화 - 템플릿 로드 및 핫키 등록"""
        # 1. 템플릿 이미지 로드
        self.templates = load_templates()
        if not self.templates:
            announce_error("템플릿 이미지를 찾을 수 없습니다")
            return False

        # 3. 핫키 등록
        self.hotkey_manager.register_scan_hotkey(self.on_scan)
        self.hotkey_manager.register_cancel_hotkey(self.on_cancel)
        self.hotkey_manager.register_number_keys(self.on_number_key)

        return True

    def on_scan(self) -> None:
        """스캔 단축키 핸들러 (Ctrl+Shift+E)"""
        # 이미 선택 모드면 무시
        if self._in_selection_mode:
            return

        announce_scan_start()

        # 카카오톡 채팅방 창 찾기 (채팅방 우선)
        hwnd = find_chat_window()
        if not hwnd:
            # 채팅방이 없으면 메인 창이라도 확인
            if check_kakaotalk_running():
                announce_error("열린 채팅방이 없습니다")
            else:
                announce_error("카카오톡이 실행되지 않았습니다")
            return

        # 창 영역 가져오기
        try:
            rect = get_client_rect(hwnd)
        except Exception:
            announce_error("창 정보를 가져올 수 없습니다")
            return

        self.current_window_offset = (rect[0], rect[1])

        # 화면 캡처
        try:
            image = capture_region(rect)
        except Exception:
            announce_error("화면 캡처 실패")
            return

        # 이모지 탐지
        self.current_detections = detect_emojis(image, self.templates)

        # 결과 알림
        result_text = format_detection_result(self.current_detections)
        announce_scan_result(result_text)

        # 탐지된 이모지가 있으면 선택 모드 진입
        if self.current_detections:
            self._in_selection_mode = True
            self.hotkey_manager.enable_selection_mode()

    def on_number_key(self, number: int) -> None:
        """숫자키 핸들러 (1~4)"""
        if not self._in_selection_mode:
            return

        # 인덱스 범위 체크
        index = number - 1
        if index < 0 or index >= len(self.current_detections):
            announce_error(f"{number}번 없음")
            return

        # 이모지 클릭
        detection = self.current_detections[index]
        announce_selection(detection["name"])

        success = click_emoji(detection, self.current_window_offset)
        if not success:
            announce_error("클릭 실패")

        # 선택 모드 종료
        self._exit_selection_mode()

    def on_cancel(self) -> None:
        """취소 핸들러 (ESC)"""
        if self._in_selection_mode:
            announce_cancel()
            self._exit_selection_mode()

    def _exit_selection_mode(self) -> None:
        """선택 모드 종료"""
        self._in_selection_mode = False
        self.current_detections = []
        self.hotkey_manager.disable_selection_mode()

    def _enter_navigation_mode(self, hwnd: int) -> None:
        """네비게이션 모드 진입"""
        if self._in_navigation_mode and self._current_chat_hwnd == hwnd:
            return  # 이미 같은 채팅방에서 활성화됨

        # 이전 모드 종료
        if self._in_selection_mode:
            self._exit_selection_mode()

        # 채팅방 진입
        if self.chat_navigator.enter_chat_room(hwnd):
            self._current_chat_hwnd = hwnd
            self._in_navigation_mode = True
            # 메시지 자동 읽기 시작
            self.message_monitor.start(hwnd)

    def _exit_navigation_mode(self) -> None:
        """네비게이션 모드 종료"""
        if not self._in_navigation_mode:
            return

        # 메시지 자동 읽기 중지
        self.message_monitor.stop()

        self.chat_navigator.exit_chat_room()
        self._in_navigation_mode = False
        self._current_chat_hwnd = None

    def _start_focus_monitor(self) -> None:
        """포커스 모니터링 스레드 시작"""
        self._focus_monitor_running = True
        self._focus_thread = threading.Thread(
            target=self._focus_monitor_loop,
            daemon=True
        )
        self._focus_thread.start()

    def _stop_focus_monitor(self) -> None:
        """포커스 모니터링 스레드 종료"""
        self._focus_monitor_running = False

        if self._focus_thread and self._focus_thread.is_alive():
            # 1차 대기 (1초)
            self._focus_thread.join(timeout=1.0)

            if self._focus_thread.is_alive():
                log.debug("focus monitor 스레드 1차 대기 타임아웃, 재시도")
                # 플래그 다시 설정 (혹시 놓쳤을 경우)
                self._focus_monitor_running = False

                # 2차 대기 (1초)
                self._focus_thread.join(timeout=1.0)

                if self._focus_thread.is_alive():
                    log.debug("focus monitor 스레드 종료 실패 - 강제 진행")

        self._focus_thread = None

    def _focus_monitor_loop(self) -> None:
        """포커스 모니터링 루프 - 목록/메뉴 항목 포커스 시 읽어줌

        최적화:
        1. 조건부 polling - 카카오톡 창 활성화 시에만 UIA 호출
        2. 웜업 기간 - 초기 3초간 느린 polling으로 CPU 부하 방지
        3. 적응형 polling - 상태에 따라 간격 조절
        """
        import uiautomation as auto
        import pythoncom

        pythoncom.CoInitialize()
        try:
            last_focused_name = None
            last_focused_type = None
            start_time = time.time()
            warmup_duration = 3.0  # 웜업 기간 3초

            while self._focus_monitor_running:
                current_time = time.time()
                elapsed = current_time - start_time

                # 웜업 기간 중에는 느리게 (500ms)
                if elapsed < warmup_duration:
                    time.sleep(0.5)
                    continue

                # 카카오톡 창이 아니면 UIA 호출 안 함 (CPU 절약)
                fg_hwnd = win32gui.GetForegroundWindow()
                if not fg_hwnd or not is_kakaotalk_window(fg_hwnd):
                    # 비활성 상태: 네비게이션 모드 종료 (컨텍스트 메뉴 모드가 아닐 때만)
                    if self._in_navigation_mode and not self._in_context_menu_mode:
                        self._exit_navigation_mode()
                    # 탭 모드는 유지 (다른 창 갔다 와도 복원)
                    last_focused_name = None
                    last_focused_type = None
                    time.sleep(0.5)
                    continue

                # 채팅방 창이면 자동으로 네비게이션 모드 진입
                is_chat = is_kakaotalk_chat_window(fg_hwnd)
                log.trace(f"포커스 모니터: hwnd={fg_hwnd}, is_chat={is_chat}, nav_mode={self._in_navigation_mode}")
                if is_chat:
                    if not self._in_navigation_mode or self._current_chat_hwnd != fg_hwnd:
                        log.debug(f"채팅방 진입 시도: hwnd={fg_hwnd}")
                        self._enter_navigation_mode(fg_hwnd)
                        log.debug(f"채팅방 진입 결과: nav_mode={self._in_navigation_mode}")
                else:
                    # 메인 창이면 네비게이션 모드 종료 (컨텍스트 메뉴 모드가 아닐 때만)
                    if self._in_navigation_mode and not self._in_context_menu_mode:
                        self._exit_navigation_mode()

                try:
                    # 카카오톡 창일 때만 UIA 호출
                    focused = auto.GetFocusedControl()
                    if focused:
                        control_type = focused.ControlTypeName
                        name = focused.Name or ""

                        # MenuItemControl은 읽기 (메뉴는 별도 창)
                        # 카카오톡 기본 메뉴 동작 사용, 포커스된 항목 이름만 읽어줌
                        if control_type == 'MenuItemControl':
                            # 메뉴 모드 자동 진입
                            if not self._in_context_menu_mode:
                                self._in_context_menu_mode = True
                                log.trace("메뉴 모드 자동 진입")

                            # 메뉴 항목 직접 발화 (NVDA가 카카오톡 메뉴 못 읽음)
                            if name and name != last_focused_name:
                                last_focused_name = name
                                last_focused_type = control_type
                                speak(name)

                        # ListItemControl도 읽기 (이미 카카오톡 창 확인됨)
                        elif control_type == 'ListItemControl':
                            # 메뉴 모드 자동 종료
                            if self._in_context_menu_mode:
                                self._in_context_menu_mode = False
                                log.trace("메뉴 모드 자동 종료")

                            if name and name != last_focused_name:
                                last_focused_name = name
                                last_focused_type = control_type
                                self._speak_item(name, control_type)
                        else:
                            # 메뉴 모드 자동 종료
                            if self._in_context_menu_mode:
                                self._in_context_menu_mode = False
                                log.trace("메뉴 모드 자동 종료")
                            last_focused_name = None
                            last_focused_type = None

                except Exception:
                    pass

                # 적응형 polling 간격 (CPU 부하 감소)
                if self._in_context_menu_mode:
                    interval = 0.25  # 메뉴 모드: 250ms (150ms→250ms)
                else:
                    interval = 0.3   # 평상시: 300ms

                time.sleep(interval)
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

        # interrupt=False: 이전 발화 중단 안 함 (발화 잘림 방지)
        speak(clean_name, interrupt=False)

    def run(self, use_gui: bool = True) -> None:
        """메인 루프 실행

        Args:
            use_gui: GUI 모드 사용 여부 (기본값: True)
        """
        log_path = get_log_file_path()
        if log_path:
            log.info(f"로그 파일: {log_path}")
        speak("카카오톡 접근성 클라이언트 시작")

        # UIA 체크 (카카오톡 유무와 무관)
        uia_result = check_uia_available()
        if not uia_result["available"]:
            speak(uia_result["message"])
            log.warning(f"UIA 체크 실패: {uia_result['message']}")
            if uia_result["error_detail"]:
                log.debug(f"상세: {uia_result['error_detail']}")
        else:
            log.debug("UIA 체크 통과")

        self.hotkey_manager.start()
        self._start_focus_monitor()

        if use_gui:
            self._run_gui_mode()
        else:
            self._run_console_mode()

    def _run_console_mode(self) -> None:
        """콘솔 모드 (기존 방식)"""
        try:
            wait_for_exit()
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

    def _run_gui_mode(self) -> None:
        """GUI 모드 (wxPython 트레이 앱)"""
        from .gui.app import KakaoA11yApp

        app = KakaoA11yApp(self)
        app.MainLoop()
        # cleanup은 MainFrame.on_close에서 호출됨

    def cleanup(self) -> None:
        """정리 - 모든 리소스 해제"""
        if hasattr(self, '_cleaned_up') and self._cleaned_up:
            return
        self._cleaned_up = True

        log.debug("정리 시작")

        # 1. 메시지 모니터 중지
        self.message_monitor.stop()

        # 2. 포커스 모니터 중지 (join 포함)
        self._stop_focus_monitor()

        # 3. hotkey_manager 정리
        self.hotkey_manager.cleanup()

        speak("종료")
        time.sleep(0.3)  # 스크린 리더가 읽을 시간 확보
        log.debug("정리 완료")


# 전역 인스턴스 (atexit에서 접근용)
_clicker_instance: Optional[EmojiClicker] = None


def _cleanup_handler():
    """atexit 핸들러 - 방어적 정리"""
    global _clicker_instance
    if _clicker_instance:
        try:
            _clicker_instance.cleanup()
        except Exception as e:
            log.debug(f"cleanup 오류: {e}")
        finally:
            _clicker_instance = None


def _signal_handler(signum, frame):
    """시그널 핸들러"""
    log.debug(f"시그널 수신: {signum}")
    sys.exit(0)


def parse_args():
    """CLI 인자 파싱"""
    parser = argparse.ArgumentParser(
        description='카카오톡 접근성 클라이언트'
    )

    # 디버그 옵션
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='디버그 모드 활성화 (상세 로깅, 자동 분석)'
    )

    parser.add_argument(
        '--debug-profile',
        action='store_true',
        help='프로파일러만 활성화'
    )

    parser.add_argument(
        '--debug-events',
        action='store_true',
        help='이벤트 모니터 활성화 (오버헤드 주의)'
    )

    parser.add_argument(
        '--debug-dump-on-start',
        action='store_true',
        help='시작 시 카카오톡 트리 덤프'
    )

    parser.add_argument(
        '--trace',
        action='store_true',
        help='TRACE 레벨 활성화 (고빈도 루프 로그 포함)'
    )

    parser.add_argument(
        '--console',
        action='store_true',
        help='콘솔 모드 실행 (--debug 필요, GUI 없이)'
    )

    return parser.parse_args()


def main() -> int:
    """진입점

    Returns:
        0: 정상 종료
        1: 오류 종료
    """
    global _clicker_instance

    # CLI 인자 파싱
    args = parse_args()

    # 디버그 모드 초기화
    from .utils.debug_config import init_debug_mode, debug_config
    from .utils.debug_tools import debug_tools
    from .utils.debug_commands import register_debug_hotkeys

    if args.debug:
        # --trace 옵션이 있으면 TRACE 레벨, 없으면 DEBUG 레벨
        if args.trace:
            set_global_level(LogLevel.TRACE)
            print("[DEBUG] TRACE 모드 활성화 (고빈도 로그 포함)")
        else:
            set_global_level(LogLevel.DEBUG)
            print("[DEBUG] 디버그 모드 활성화")
        init_debug_mode(
            enabled=True,
            enable_event_monitor=args.debug_events,
        )
    elif args.debug_profile:
        init_debug_mode(
            enabled=True,
            enable_inspector=False,
            enable_event_monitor=False,
        )
        print("[DEBUG] 프로파일러 전용 모드")

    # 시작 시 덤프
    if args.debug_dump_on_start and debug_config.enabled:
        try:
            dump_path = debug_tools.dump_to_file(filename_prefix='startup')
            print(f"[DEBUG] 시작 덤프 저장: {dump_path}")
        except Exception as e:
            print(f"[DEBUG] 시작 덤프 실패: {e}")

    # 디버그 단축키 등록
    if debug_config.enabled:
        register_debug_hotkeys()
        # 세션 리포트 생성 등록
        atexit.register(lambda: debug_tools.generate_session_report())

    # 프로세스 잠금 확인 - 기존 프로세스 자동 종료
    from .utils.process_lock import get_process_lock
    lock = get_process_lock()

    # atexit 먼저 등록 (초기화 실패 시에도 정리 보장)
    atexit.register(lock.release)

    if not lock.acquire():
        # 이미 실행 중 - 기존 프로세스 종료 후 재시도
        speak("이미 실행 중입니다. 기존 프로세스를 종료합니다.")
        log.debug("기존 프로세스 감지, 종료 시도")

        if lock.terminate_existing():
            time.sleep(0.5)  # 종료 대기
            if not lock.acquire():
                speak("프로세스 시작 실패")
                log.debug("프로세스 잠금 획득 실패")
                return 1
        else:
            speak("기존 프로세스 종료 실패. 작업관리자에서 python.exe를 종료해주세요.")
            log.debug("기존 프로세스 종료 실패")
            return 1

    # 시그널 핸들러 등록 (GUI 모드에서는 wx와 충돌 방지)
    if args.console:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
    else:
        # GUI 모드: 기본 핸들러 사용 (wx가 처리)
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    # cleanup 핸들러 등록
    atexit.register(_cleanup_handler)

    _clicker_instance = EmojiClicker()
    if not _clicker_instance.initialize():
        return 1

    # GUI 모드가 기본 (--console은 디버그 모드에서만 유효)
    use_console = args.console and args.debug
    _clicker_instance.run(use_gui=not use_console)
    return 0


if __name__ == "__main__":
    sys.exit(main())
