# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""메인 진입점 - 전체 플로우 조율"""

import argparse
import atexit
import signal
import sys
import time
from typing import Optional

from .config import APP_DISPLAY_NAME, TIMING_TTS_READ_DELAY, TIMING_PROCESS_TERMINATION_WAIT
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
from .navigation import ChatRoomNavigator
from .navigation.message_monitor import MessageMonitor
from .mode_manager import ModeManager
from .focus_monitor import FocusMonitorService
from .message_actions import (
    MessageActionManager,
    MessageTextExtractor,
    CopyMessageAction,
)
from .utils.debug import get_logger, get_log_file_path

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

        # 메시지 액션 관리자 (C: 복사)
        self.message_actions = self._create_message_actions()

        # 포커스 모니터
        self.focus_monitor = FocusMonitorService(
            mode_manager=self.mode_manager,
            message_monitor=self.message_monitor,
            chat_navigator=self.chat_navigator,
            hotkey_manager=self.hotkey_manager,
            message_actions=self.message_actions,
        )

    def _create_message_actions(self) -> MessageActionManager:
        """메시지 액션 관리자 생성 및 액션 등록."""
        manager = MessageActionManager()
        extractor = MessageTextExtractor()

        # current_focused_item을 포커스 제공자로 연결
        focus_getter = lambda: self.chat_navigator.current_focused_item
        extractor.set_focus_provider(focus_getter)
        manager.set_focus_provider(focus_getter)

        # C 키: 메시지 복사
        manager.register("c", CopyMessageAction(extractor))

        return manager

    def initialize(self) -> bool:
        """템플릿 로드 및 핫키 등록. 실패 시 False."""
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
        """이모지 스캔 시작. 선택 모드 중이면 무시."""
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
        """이모지 선택. 선택 모드 아니면 무시."""
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
        """선택 모드 취소. 선택 모드 아니면 무시."""
        if self.mode_manager.in_selection_mode:
            announce_cancel()
            self._exit_selection_mode_internal()

    def _exit_selection_mode_internal(self) -> None:
        """탐지 결과 초기화 후 선택 모드 종료."""
        self.current_detections = []
        self.mode_manager.exit_selection_mode(self.hotkey_manager)

    def run(self, use_gui: bool = True) -> None:
        """메인 루프 실행. use_gui=False면 콘솔 모드."""
        log_path = get_log_file_path()
        if log_path:
            log.info(f"log file: {log_path}")
        speak(f"{APP_DISPLAY_NAME} 시작")

        # UIA 체크 (카카오톡 유무와 무관)
        uia_result = check_uia_available()
        if not uia_result["available"]:
            speak(uia_result["message"])
            log.warning(f"UIA check failed: {uia_result['message']}")
            if uia_result["error_detail"]:
                log.debug(f"detail: {uia_result['error_detail']}")
        else:
            log.debug("UIA check passed")

        self.hotkey_manager.start()
        self.focus_monitor.start()

        if use_gui:
            self._run_gui_mode()
        else:
            self._run_console_mode()

    def _run_console_mode(self) -> None:
        """콘솔 모드. Ctrl+C 또는 종료 핫키로 종료."""
        try:
            wait_for_exit()
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

    def _run_gui_mode(self) -> None:
        """GUI 모드. cleanup은 MainFrame.on_close에서 호출."""
        from .gui.app import KakaoA11yApp

        app = KakaoA11yApp(self)
        app.MainLoop()
        # cleanup은 MainFrame.on_close에서 호출됨

    def cleanup(self) -> None:
        """모든 리소스 해제. 중복 호출 안전."""
        if hasattr(self, '_cleaned_up') and self._cleaned_up:
            return
        self._cleaned_up = True

        log.debug("cleanup started")

        # 1. 메시지 모니터 중지
        self.message_monitor.stop()

        # 2. 포커스 모니터 중지 (join 포함)
        self.focus_monitor.stop()

        # 3. hotkey_manager 정리
        self.hotkey_manager.cleanup()

        speak("종료")
        time.sleep(TIMING_TTS_READ_DELAY)  # 스크린 리더가 읽을 시간 확보
        log.debug("cleanup completed")


# 전역 인스턴스 (atexit에서 접근용)
_clicker_instance: Optional[EmojiClicker] = None


def _cleanup_handler():
    """atexit 핸들러. 예외 발생해도 강제 진행."""
    global _clicker_instance
    if _clicker_instance:
        try:
            _clicker_instance.cleanup()
        except Exception as e:
            log.debug(f"cleanup error: {e}")
        finally:
            _clicker_instance = None


def _signal_handler(signum, frame):
    """SIGINT/SIGTERM 수신 시 종료."""
    log.debug(f"signal received: {signum}")
    sys.exit(0)


def parse_args():
    """CLI 인자 파싱. --debug, --trace 등."""
    parser = argparse.ArgumentParser(
        description=APP_DISPLAY_NAME
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
        nargs='?',
        const='default',
        default=None,
        metavar='EVENTS',
        help='이벤트 모니터 활성화. 값: all, focus, structure, property (콤마 조합 가능)'
    )

    parser.add_argument(
        '--debug-events-filter',
        default=None,
        metavar='TYPES',
        help='이벤트 필터: ControlType 콤마 구분 (예: ListItemControl,MenuItemControl)'
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


def _setup_process(args) -> int:
    """프로세스 락 + 시그널 핸들러 설정. 실패 시 1 반환, 성공 시 0."""
    from .utils.process_lock import get_process_lock
    lock = get_process_lock()

    # atexit 먼저 등록 (초기화 실패 시에도 정리 보장)
    atexit.register(lock.release)

    if not lock.acquire():
        # 이미 실행 중 - 기존 프로세스 종료 후 재시도
        speak("이미 실행 중입니다. 기존 프로세스를 종료합니다.")
        log.debug("existing process detected, attempting termination")

        if lock.terminate_existing():
            time.sleep(TIMING_PROCESS_TERMINATION_WAIT)  # 종료 대기
            if not lock.acquire():
                speak("프로세스 시작 실패")
                log.debug("failed to acquire process lock")
                return 1
        else:
            speak("기존 프로세스 종료 실패. 작업관리자에서 python.exe를 종료해주세요.")
            log.debug("failed to terminate existing process")
            return 1

    # 시그널 핸들러 등록 (GUI 모드에서는 wx와 충돌 방지)
    if args.console:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
    else:
        # GUI 모드: 기본 핸들러 사용 (wx가 처리)
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    return 0


def main() -> int:
    """진입점. 0=정상, 1=오류."""
    global _clicker_instance

    args = parse_args()

    from .utils.debug_setup import setup_debug
    setup_debug(args)

    if _setup_process(args) != 0:
        return 1

    atexit.register(_cleanup_handler)

    _clicker_instance = EmojiClicker()
    if not _clicker_instance.initialize():
        return 1

    use_console = args.console and args.debug
    _clicker_instance.run(use_gui=not use_console)
    return 0


if __name__ == "__main__":
    sys.exit(main())
