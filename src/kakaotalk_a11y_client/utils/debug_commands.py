# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""디버그 단축키 명령어 (Ctrl+Shift+D/P/R/1/2)"""

import time
import threading

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    keyboard = None
    HAS_KEYBOARD = False

import pyautogui

from ..accessibility import speak
from .debug_config import debug_config
from .debug_tools import debug_tools, KakaoNotFoundError
from .profiler import profiler
from .event_monitor import EventMonitor, EventLog


_event_monitor_active = False
_event_monitor = None
_test_cancelled = False

# 등록된 핫키 추적 {name: hotkey_string}
_registered_hotkeys: dict[str, str] = {}


def _format_hotkey_for_keyboard(config: dict) -> str:
    """{"modifiers": ["ctrl", "shift"], "key": "D"} -> "ctrl+shift+d" """
    parts = config.get("modifiers", []).copy()
    parts.append(config.get("key", "").lower())
    return "+".join(parts)


def _on_dump_now():
    print("[DEBUG] 덤프 시작...")
    speak("덤프 시작")
    try:
        path = debug_tools.dump_to_file(filename_prefix='manual')
        print(f"[DEBUG] 덤프 완료: {path}")
        speak(f"덤프 완료, {path.name}")
    except KakaoNotFoundError:
        print("[DEBUG] 덤프 실패: 카카오톡 창 없음")
        speak("덤프 실패, 카카오톡 창 없음")
    except Exception as e:
        print(f"[DEBUG] 덤프 실패: {e}")
        speak("덤프 실패")


def _on_show_profile():
    print("[DEBUG] 프로파일 리포트 생성 중...")
    speak("프로파일 리포트 생성 중")
    print("\n" + "=" * 50)
    print(profiler.get_report())
    print("=" * 50)

    # 파일 저장 + 경로 발화
    report_path = profiler.save_report()
    if report_path:
        print(f"[DEBUG] 프로파일 리포트 저장: {report_path}")
        speak(f"프로파일 완료, {report_path.name}")
    else:
        print("[DEBUG] 프로파일 리포트 완료 (저장 실패)")
        speak("프로파일 완료")


def _on_event_log(event: EventLog):
    """새 이벤트 모니터의 기본 콜백. 콘솔 출력은 EventMonitor 내부에서 처리."""
    # EventMonitor가 ConsoleFormatter로 자동 출력하므로 여기선 추가 작업 없음
    pass


def _on_show_status():
    """현재 디버그 상태 요약 발화 (Ctrl+Shift+S)."""
    status_parts = []

    # 이벤트 모니터 상태
    status_parts.append("이벤트 모니터 " + ("켜짐" if _event_monitor_active else "꺼짐"))

    # 프로파일러 상태
    metrics_count = len(profiler.metrics)
    if metrics_count > 0:
        status_parts.append(f"프로파일러 {metrics_count}개 측정 중")
    else:
        status_parts.append("프로파일러 측정 없음")

    status_text = ", ".join(status_parts)
    print(f"[DEBUG] 상태: {status_text}")
    speak(f"디버그 상태, {status_text}")


def _on_toggle_event_monitor():
    global _event_monitor_active, _event_monitor

    _event_monitor_active = not _event_monitor_active

    if _event_monitor_active:
        if _event_monitor is None:
            # debug_config에서 설정 가져오기
            config = debug_config.event_monitor_config
            _event_monitor = EventMonitor(config=config)
        _event_monitor.start()  # 기본 콘솔 출력 사용
        active = _event_monitor.active_events
        event_names = ", ".join(e.name for e in active)
        print(f"[DEBUG] 이벤트 모니터 활성화 - {event_names}")
        speak("이벤트 모니터 활성화")
    else:
        if _event_monitor:
            _event_monitor.stop()
        print("[DEBUG] 이벤트 모니터 비활성화")
        speak("이벤트 모니터 비활성화")


def _on_test_navigation():
    """방향키/PageUp/PageDown 자동 입력 테스트."""
    print("[TEST] 탐색 테스트 시작")
    speak("탐색 테스트 시작")

    interval = 0.3  # 키 입력 간격

    # pyautogui 설정
    pyautogui.PAUSE = 0.05

    try:
        # 1. 방향키 테스트
        print("[TEST] 1단계: 방향키 ↓ 5회")
        for _ in range(5):
            pyautogui.press('down')
            time.sleep(interval)

        print("[TEST] 1단계: 방향키 ↑ 5회")
        for _ in range(5):
            pyautogui.press('up')
            time.sleep(interval)

        # 2. 페이지 업/다운 테스트
        print("[TEST] 2단계: PageDown")
        pyautogui.press('pagedown')
        time.sleep(interval)

        print("[TEST] 2단계: PageUp")
        pyautogui.press('pageup')
        time.sleep(interval)

        # 3. 방향키 테스트 (페이지 이동 후 병목 감지)
        print("[TEST] 3단계: PageDown 후 방향키")
        pyautogui.press('pagedown')
        time.sleep(interval)

        for _ in range(3):
            pyautogui.press('down')
            time.sleep(interval)
        for _ in range(3):
            pyautogui.press('up')
            time.sleep(interval)

        print("[TEST] 3단계: PageUp 후 방향키")
        pyautogui.press('pageup')
        time.sleep(interval)

        for _ in range(3):
            pyautogui.press('down')
            time.sleep(interval)
        for _ in range(3):
            pyautogui.press('up')
            time.sleep(interval)

        print("[TEST] 탐색 테스트 완료")
        speak("탐색 테스트 완료")

    except Exception as e:
        print(f"[TEST] 탐색 테스트 오류: {e}")
        speak("탐색 테스트 오류")


def _on_test_message():
    """3초 후 테스트 메시지 5회 전송. 입력창에 포커스 필요."""
    import pyperclip

    global _test_cancelled
    _test_cancelled = False

    print("[TEST] 메시지 테스트 - 3초 후 시작 (Esc로 취소)")
    speak("메시지 테스트, 3초 후 시작")

    # Esc 감지용 핸들러
    def on_esc():
        global _test_cancelled
        _test_cancelled = True
        print("[TEST] 취소됨")
        speak("취소됨")

    if HAS_KEYBOARD:
        keyboard.on_press_key('esc', lambda _: on_esc(), suppress=False)

    try:
        # 3초 카운트다운
        for i in range(3, 0, -1):
            if _test_cancelled:
                return
            print(f"[TEST] {i}...")
            time.sleep(1)

        if _test_cancelled:
            return

        # pyautogui 설정
        pyautogui.PAUSE = 0.05

        # 메시지 5개 전송 (클립보드 + Ctrl+V + Enter)
        for i in range(1, 6):
            if _test_cancelled:
                return

            msg = f"테스트 메시지 {i}"
            pyperclip.copy(msg)
            print(f"[TEST] 전송: {msg}")

            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)
            pyautogui.press('enter')
            time.sleep(0.5)  # 밴 방지용 간격

        print("[TEST] 메시지 테스트 완료")
        speak("메시지 테스트 완료")

    except Exception as e:
        print(f"[TEST] 메시지 테스트 오류: {e}")
        speak("메시지 테스트 오류")
    finally:
        if HAS_KEYBOARD:
            try:
                keyboard.unhook_key('esc')
            except Exception:
                pass


def register_debug_hotkeys():
    """설정에서 디버그 단축키 로드 후 등록."""
    global _registered_hotkeys

    if not debug_config.enabled:
        return

    if not HAS_KEYBOARD:
        print("[DEBUG] keyboard 패키지 미설치 - 디버그 단축키 비활성화")
        return

    from ..settings import get_settings, DEBUG_HOTKEY_NAMES

    # 콜백 매핑
    callbacks = {
        "dump": _on_dump_now,
        "profile": _on_show_profile,
        "event_monitor": _on_toggle_event_monitor,
        "status": _on_show_status,
        "test_navigation": _on_test_navigation,
        "test_message": _on_test_message,
    }

    settings = get_settings()
    debug_hotkeys = settings.get_all_debug_hotkeys()

    print("[DEBUG] 디버그 단축키 활성화:")
    for name, callback in callbacks.items():
        config = debug_hotkeys.get(name)
        if not config:
            continue

        hotkey_str = _format_hotkey_for_keyboard(config)
        keyboard.add_hotkey(hotkey_str, callback, suppress=False)
        _registered_hotkeys[name] = hotkey_str

        display_name = DEBUG_HOTKEY_NAMES.get(name, name)
        print(f"  {hotkey_str.upper()}: {display_name}")


def unregister_debug_hotkeys():
    """등록된 모든 디버그 단축키 해제."""
    global _registered_hotkeys

    if not HAS_KEYBOARD:
        return

    for name, hotkey_str in _registered_hotkeys.items():
        try:
            keyboard.remove_hotkey(hotkey_str)
        except KeyError:
            pass  # 이미 해제됨

    _registered_hotkeys.clear()


def reload_debug_hotkeys():
    """단축키 재등록 (설정 변경 후 호출)."""
    unregister_debug_hotkeys()
    register_debug_hotkeys()
