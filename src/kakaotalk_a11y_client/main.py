# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""메인 진입점 - 전체 플로우 조율"""

import argparse
import atexit
import signal
import sys
import time
from typing import Optional

from .window_finder import (
    find_chat_window,
    get_client_rect,
    check_kakaotalk_running,
    check_uia_available,
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
from .mouse_hook import MouseHook
from .navigation import ChatRoomNavigator
from .navigation.message_monitor import MessageMonitor
from .mode_manager import ModeManager
from .focus_monitor import FocusMonitorService
from .utils.debug import get_logger, is_debug_enabled, get_log_file_path, set_global_level, LogLevel
from .utils.profiler import profiler, profile_logger, init_profiler

log = get_logger("Main")


class EmojiClicker:
    """카카오톡 이모지 클리커 메인 클래스"""

    def __init__(self):
        self.hotkey_manager = HotkeyManager()
        self.templates = None
        self.current_detections: list[dict] = []
        self.current_window_offset: tuple[int, int] = (0, 0)

        # 네비게이션 관련
        self.chat_navigator = ChatRoomNavigator()
        self.message_monitor = MessageMonitor(self.chat_navigator)

        # 모드 관리자
        self.mode_manager = ModeManager()

        # 포커스 모니터
        self.focus_monitor = FocusMonitorService(
            mode_manager=self.mode_manager,
            message_monitor=self.message_monitor,
            chat_navigator=self.chat_navigator,
            hotkey_manager=self.hotkey_manager,
        )

        # 마우스 훅 (비메시지 항목 우클릭 차단)
        self.mouse_hook = MouseHook(lambda: self.focus_monitor.last_focused_name)

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
        if self.mode_manager.in_selection_mode:
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
            self.mode_manager.enter_selection_mode(self.hotkey_manager)

    def on_number_key(self, number: int) -> None:
        """숫자키 핸들러 (1~4)"""
        if not self.mode_manager.in_selection_mode:
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
        self._exit_selection_mode_internal()

    def on_cancel(self) -> None:
        """취소 핸들러 (ESC)"""
        if self.mode_manager.in_selection_mode:
            announce_cancel()
            self._exit_selection_mode_internal()

    def _exit_selection_mode_internal(self) -> None:
        """선택 모드 종료 (내부용)"""
        self.current_detections = []
        self.mode_manager.exit_selection_mode(self.hotkey_manager)

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

        # 마우스 훅 설치 (비메시지 항목 우클릭 차단)
        self.mouse_hook.install()

        self.hotkey_manager.start()
        self.focus_monitor.start()

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
        self.focus_monitor.stop()

        # 3. hotkey_manager 정리
        self.hotkey_manager.cleanup()

        # 4. 마우스 훅 해제
        self.mouse_hook.uninstall()

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
        init_profiler(enabled=True)
        init_debug_mode(
            enabled=True,
            enable_event_monitor=args.debug_events,
        )
    elif args.debug_profile:
        init_profiler(enabled=True)
        init_debug_mode(
            enabled=True,
            enable_inspector=False,
            enable_event_monitor=False,
        )
        print("[DEBUG] 프로파일러 전용 모드")
    else:
        # 환경변수 기반 초기화 (하위 호환)
        init_profiler()

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
