"""디버그 도구 통합 스크립트

기존 스크립트 통합:
- track_focus.py
- debug_focus.py
- debug_nav.py
- debug_nav_keyboard.py

사용법:
  python scripts/debug_tools.py --mode focus     # 포커스 추적
  python scripts/debug_tools.py --mode nav       # 네비게이션 디버그
  python scripts/debug_tools.py --mode keyboard  # 키보드 네비게이션 디버그
"""

import sys
import io
import argparse
import threading
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)

import keyboard
import win32gui
import uiautomation as auto
import pythoncom


def safe_print(text):
    """인코딩 안전 출력"""
    clean = ''.join(c if ord(c) < 0x10000 else '?' for c in text)
    try:
        print(clean)
    except UnicodeEncodeError:
        print(clean.encode('ascii', errors='replace').decode('ascii'))


# ========== 포커스 추적 모드 ==========

def run_focus_tracker():
    """포커스 추적 모드"""
    pythoncom.CoInitialize()

    log_file = open('focus_log.txt', 'w', encoding='utf-8')

    def log(msg):
        log_file.write(msg + '\n')
        log_file.flush()
        safe_print(msg)

    log("포커스 추적 시작")
    log("- 방향키/Tab으로 이동하면 포커스 정보 출력")
    log("- Q: 종료")
    log("=" * 60)

    last_info = None

    try:
        while True:
            if keyboard.is_pressed('q'):
                log("\n종료")
                break

            try:
                focused = auto.GetFocusedControl()
                if focused:
                    info = {
                        'name': focused.Name or '',
                        'type': focused.ControlTypeName,
                        'class': focused.ClassName or '',
                    }

                    if info != last_info:
                        last_info = info
                        name = info['name'][:50] if info['name'] else '(없음)'
                        log(f"[{info['type']}] \"{name}\" Class={info['class']}")

                        # 부모 정보
                        try:
                            parent = focused.GetParentControl()
                            if parent:
                                pname = (parent.Name or '')[:30]
                                log(f"  부모: [{parent.ControlTypeName}] \"{pname}\"")
                        except:
                            pass

            except Exception as e:
                log(f"[오류] {e}")

            time.sleep(0.1)
    finally:
        log_file.close()


# ========== 네비게이션 디버그 모드 ==========

def run_nav_debug():
    """네비게이션 디버그 모드 (Alt+방향키)"""
    from kakaotalk_a11y_client.window_finder import is_kakaotalk_chat_window, get_active_chat_windows
    from kakaotalk_a11y_client.navigation import ChatRoomNavigator
    from kakaotalk_a11y_client.accessibility import speak
    import ctypes
    from ctypes import wintypes
    import win32con

    user32 = ctypes.windll.user32

    navigator = ChatRoomNavigator()
    state = {'active': False, 'hwnd': None}

    # 핫키 ID
    HOTKEY_UP = 100
    HOTKEY_DOWN = 101

    def check_focus():
        hwnd = win32gui.GetForegroundWindow()
        is_chat = is_kakaotalk_chat_window(hwnd) if hwnd else False

        if is_chat and not state['active']:
            print(f"[DEBUG] 채팅방 감지: hwnd={hwnd}")
            if navigator.enter_chat_room(hwnd):
                state['active'] = True
                state['hwnd'] = hwnd
                print(f"[DEBUG] 네비게이션 진입, 메시지 {len(navigator.messages)}개")

        elif not is_chat and state['active']:
            print("[DEBUG] 채팅방 벗어남")
            navigator.exit_chat_room()
            state['active'] = False
            state['hwnd'] = None

    def focus_monitor():
        while True:
            check_focus()
            time.sleep(0.5)

    def on_hotkey(hotkey_id):
        if not state['active']:
            return
        if hotkey_id == HOTKEY_UP:
            print("[DEBUG] 위로 이동")
            navigator.move_up()
        elif hotkey_id == HOTKEY_DOWN:
            print("[DEBUG] 아래로 이동")
            navigator.move_down()

    def hotkey_thread():
        user32.RegisterHotKey(None, HOTKEY_UP, win32con.MOD_ALT, win32con.VK_UP)
        user32.RegisterHotKey(None, HOTKEY_DOWN, win32con.MOD_ALT, win32con.VK_DOWN)
        print("[DEBUG] Alt+Up/Down 등록됨")

        msg = wintypes.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            if msg.message == win32con.WM_HOTKEY:
                threading.Thread(target=on_hotkey, args=(msg.wParam,), daemon=True).start()

    print("=" * 50)
    print("네비게이션 디버그 (Alt+Up/Down)")
    print("Ctrl+C로 종료")
    print("=" * 50)

    windows = get_active_chat_windows()
    if windows:
        print(f"열린 채팅방: {[w.title for w in windows]}")

    threading.Thread(target=focus_monitor, daemon=True).start()
    threading.Thread(target=hotkey_thread, daemon=True).start()

    speak("디버그 모드 시작")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n종료")


# ========== 키보드 네비게이션 디버그 모드 ==========

def run_keyboard_nav_debug():
    """키보드 네비게이션 디버그 (방향키 직접 후킹)"""
    from kakaotalk_a11y_client.window_finder import is_kakaotalk_chat_window, get_active_chat_windows
    from kakaotalk_a11y_client.navigation import ChatRoomNavigator
    from kakaotalk_a11y_client.accessibility import speak

    navigator = ChatRoomNavigator()
    state = {'active': False, 'hwnd': None}

    def is_chat_focused():
        hwnd = win32gui.GetForegroundWindow()
        return is_kakaotalk_chat_window(hwnd) if hwnd else False

    def check_focus():
        hwnd = win32gui.GetForegroundWindow()
        is_chat = is_kakaotalk_chat_window(hwnd) if hwnd else False

        if is_chat and not state['active']:
            print(f"[DEBUG] 채팅방 감지: hwnd={hwnd}")
            if navigator.enter_chat_room(hwnd):
                state['active'] = True
                state['hwnd'] = hwnd
                print(f"[DEBUG] 네비게이션 진입, 메시지 {len(navigator.messages)}개")

        elif not is_chat and state['active']:
            print("[DEBUG] 채팅방 벗어남")
            navigator.exit_chat_room()
            state['active'] = False
            state['hwnd'] = None

    def focus_monitor():
        while True:
            check_focus()
            time.sleep(0.5)

    def on_up():
        if state['active'] and is_chat_focused():
            print("[DEBUG] 위로 이동")
            navigator.move_up()

    def on_down():
        if state['active'] and is_chat_focused():
            print("[DEBUG] 아래로 이동")
            navigator.move_down()

    print("=" * 50)
    print("키보드 네비게이션 디버그 (방향키)")
    print("Ctrl+C로 종료")
    print("=" * 50)

    windows = get_active_chat_windows()
    if windows:
        print(f"열린 채팅방: {[w.title for w in windows]}")

    threading.Thread(target=focus_monitor, daemon=True).start()

    keyboard.on_press_key('up', lambda e: on_up(), suppress=True)
    keyboard.on_press_key('down', lambda e: on_down(), suppress=True)

    print("[DEBUG] 키보드 후킹 완료")
    speak("디버그 모드 시작")

    try:
        keyboard.wait()
    except KeyboardInterrupt:
        print("\n종료")


# ========== 메인 ==========

def main():
    parser = argparse.ArgumentParser(description="카카오톡 디버그 도구")
    parser.add_argument(
        "--mode", "-m",
        choices=["focus", "nav", "keyboard"],
        default="focus",
        help="디버그 모드 (focus: 포커스 추적, nav: Alt+방향키 네비게이션, keyboard: 방향키 후킹)"
    )

    args = parser.parse_args()

    pythoncom.CoInitialize()

    if args.mode == "focus":
        run_focus_tracker()
    elif args.mode == "nav":
        run_nav_debug()
    elif args.mode == "keyboard":
        run_keyboard_nav_debug()


if __name__ == "__main__":
    main()
