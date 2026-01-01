# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""
실행 중 디버그 명령어

키보드 단축키로 디버그 도구 즉시 실행:
- Ctrl+Shift+D: 현재 상태 덤프
- Ctrl+Shift+P: 프로파일러 리포트
- Ctrl+Shift+R: 이벤트 모니터 토글
"""

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    keyboard = None
    HAS_KEYBOARD = False

from ..accessibility import speak
from .debug_config import debug_config
from .debug_tools import debug_tools, KakaoNotFoundError
from .profiler import profiler
from .uia_events import HybridFocusMonitor, FocusEvent


_event_monitor_active = False
_focus_monitor = None


def _on_dump_now():
    """Ctrl+Shift+D: 즉시 덤프"""
    print("[DEBUG] 덤프 시작...")
    speak("덤프 시작")
    try:
        path = debug_tools.dump_to_file(filename_prefix='manual')
        print(f"[DEBUG] 덤프 완료: {path}")
        speak("덤프 완료")
    except KakaoNotFoundError:
        print("[DEBUG] 덤프 실패: 카카오톡 창 없음")
        speak("덤프 실패, 카카오톡 창 없음")
    except Exception as e:
        print(f"[DEBUG] 덤프 실패: {e}")
        speak("덤프 실패")


def _on_show_profile():
    """Ctrl+Shift+P: 프로파일 요약"""
    print("[DEBUG] 프로파일 리포트 생성 중...")
    speak("프로파일 리포트 생성 중")
    print("\n" + "=" * 50)
    print(profiler.get_report())
    print("=" * 50)
    print("[DEBUG] 프로파일 리포트 완료\n")
    speak("프로파일 리포트 완료")


def _on_focus_changed(event: FocusEvent):
    """포커스 변경 이벤트 콜백"""
    try:
        ctrl = event.control
        name = ctrl.Name or "(이름 없음)"
        ctrl_type = ctrl.ControlTypeName
        class_name = ctrl.ClassName or ""
        print(f"[FOCUS] {ctrl_type}: {name[:50]} ({class_name})")
    except Exception as e:
        print(f"[FOCUS] 오류: {e}")


def _on_toggle_event_monitor():
    """Ctrl+Shift+R: 이벤트 모니터 토글"""
    global _event_monitor_active, _focus_monitor

    _event_monitor_active = not _event_monitor_active

    if _event_monitor_active:
        if _focus_monitor is None:
            _focus_monitor = HybridFocusMonitor(polling_interval=0.2)
        _focus_monitor.start(on_focus_changed=_on_focus_changed)
        print("[DEBUG] 이벤트 모니터 활성화 - 포커스 변경이 콘솔에 출력됩니다")
        speak("이벤트 모니터 활성화")
    else:
        if _focus_monitor:
            _focus_monitor.stop()
        print("[DEBUG] 이벤트 모니터 비활성화")
        speak("이벤트 모니터 비활성화")


def register_debug_hotkeys():
    """디버그 단축키 등록 (디버그 모드에서만)"""

    if not debug_config.enabled:
        return

    if not HAS_KEYBOARD:
        print("[DEBUG] keyboard 패키지 미설치 - 디버그 단축키 비활성화")
        return

    # suppress=False로 변경: 키 이벤트 처리 오버헤드 감소
    keyboard.add_hotkey('ctrl+shift+d', _on_dump_now, suppress=False)
    keyboard.add_hotkey('ctrl+shift+p', _on_show_profile, suppress=False)
    keyboard.add_hotkey('ctrl+shift+r', _on_toggle_event_monitor, suppress=False)

    print("[DEBUG] 디버그 단축키 활성화:")
    print("  Ctrl+Shift+D: 즉시 덤프")
    print("  Ctrl+Shift+P: 프로파일 요약")
    print("  Ctrl+Shift+R: 이벤트 모니터 토글")


def unregister_debug_hotkeys():
    """디버그 단축키 해제"""
    if not HAS_KEYBOARD:
        return

    try:
        keyboard.remove_hotkey('ctrl+shift+d')
        keyboard.remove_hotkey('ctrl+shift+p')
        keyboard.remove_hotkey('ctrl+shift+r')
    except KeyError:
        pass  # 이미 해제됨
