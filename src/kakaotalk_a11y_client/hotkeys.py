# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""글로벌 핫키 모듈 - RegisterHotKey API 사용

keyboard 라이브러리 대신 Windows RegisterHotKey API를 직접 사용.
키보드 훅을 설치하지 않아 NVDA 등 스크린 리더와 충돌 없음.
"""

import ctypes
from ctypes import wintypes
import os
import signal
import threading
from typing import Callable, Optional

import win32con

from .utils.debug import get_logger

user32 = ctypes.windll.user32
log = get_logger("Hotkeys")

# 핫키 ID 상수
HOTKEY_ID_SCAN = 1
HOTKEY_ID_CANCEL = 2
HOTKEY_ID_NUM1 = 3
HOTKEY_ID_NUM2 = 4
HOTKEY_ID_NUM3 = 5
HOTKEY_ID_NUM4 = 6
HOTKEY_ID_EXIT = 20  # Win+Ctrl+K 종료

# 핫키 ID와 설정 키 매핑
HOTKEY_CONFIG_MAP = {
    HOTKEY_ID_SCAN: "scan",
    HOTKEY_ID_EXIT: "exit",
}

# Virtual Key Codes
VK_1 = 0x31
VK_2 = 0x32
VK_3 = 0x33
VK_4 = 0x34


def _get_modifiers(mod_list: list[str]) -> int:
    """["ctrl", "shift"] -> MOD_CONTROL | MOD_SHIFT"""
    result = 0
    for mod in mod_list:
        mod_lower = mod.lower()
        if mod_lower == "ctrl":
            result |= win32con.MOD_CONTROL
        elif mod_lower == "shift":
            result |= win32con.MOD_SHIFT
        elif mod_lower == "alt":
            result |= win32con.MOD_ALT
        elif mod_lower == "win":
            result |= win32con.MOD_WIN
    return result


def _get_vk(key: str) -> int:
    """"E" -> 0x45, "F1" -> 0x70"""
    key = key.upper()
    # 단일 알파벳
    if len(key) == 1 and key.isalpha():
        return ord(key)
    # 단일 숫자
    if len(key) == 1 and key.isdigit():
        return ord(key)
    # 특수 키
    special_keys = {
        # 펑션 키
        "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
        "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
        "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
        # 기타 키
        "ESC": 0x1B, "ESCAPE": 0x1B,
        "SPACE": 0x20,
        "TAB": 0x09,
        "ENTER": 0x0D, "RETURN": 0x0D,
        "BACKSPACE": 0x08,
        # 방향키
        "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
        # 네비게이션 키
        "HOME": 0x24, "END": 0x23,
        "PAGEUP": 0x21, "PAGEDOWN": 0x22,
        "INSERT": 0x2D, "DELETE": 0x2E,
    }
    return special_keys.get(key, 0)


class HotkeyManager:
    """RegisterHotKey 기반 글로벌 핫키 관리자"""

    def __init__(self):
        self._callbacks: dict[int, Callable] = {}
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._selection_mode_active = False
        self._thread_id: Optional[int] = None
        self._cleanup_event = threading.Event()

    def register_scan_hotkey(self, callback: Callable) -> None:
        self._callbacks[HOTKEY_ID_SCAN] = callback

    def register_cancel_hotkey(self, callback: Callable) -> None:
        self._callbacks[HOTKEY_ID_CANCEL] = callback

    def register_number_keys(self, callback: Callable) -> None:
        """callback(number) 형태로 호출됨."""
        for i in range(1, 5):
            hotkey_id = HOTKEY_ID_NUM1 + (i - 1)
            self._callbacks[hotkey_id] = lambda num=i: callback(num)

    def enable_selection_mode(self) -> None:
        """숫자키 1~4 핫키 등록. PostThreadMessage로 메시지 루프에 전달."""
        if self._selection_mode_active:
            return
        if not self._thread_id:
            return

        ctypes.windll.user32.PostThreadMessageW(
            self._thread_id,
            win32con.WM_USER + 1,
            0,
            0,
        )
        self._selection_mode_active = True

    def disable_selection_mode(self) -> None:
        """숫자키 1~4 핫키 해제."""
        if not self._selection_mode_active:
            return
        if not self._thread_id:
            return

        ctypes.windll.user32.PostThreadMessageW(
            self._thread_id,
            win32con.WM_USER + 2,
            0,
            0,
        )
        self._selection_mode_active = False

    def start(self) -> None:
        """메시지 루프 스레드 시작. RegisterHotKey는 루프 내에서 실행."""
        self._running = True
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()

    def _message_loop(self) -> None:
        """핫키 등록 + WM_HOTKEY 처리. 콜백은 별도 스레드에서 실행."""
        from .settings import get_settings

        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        settings = get_settings()

        # 설정에서 핫키 로드 및 등록
        for hotkey_id, config_key in HOTKEY_CONFIG_MAP.items():
            hotkey_config = settings.get_hotkey(config_key)
            if hotkey_config:
                modifiers = _get_modifiers(hotkey_config.get("modifiers", []))
                vk = _get_vk(hotkey_config.get("key", ""))
                if vk:
                    result = user32.RegisterHotKey(None, hotkey_id, modifiers, vk)
                    if not result:
                        error_code = ctypes.GetLastError()
                        if error_code == 1409:  # ERROR_HOTKEY_ALREADY_REGISTERED
                            log.warning(f"핫키 이미 등록됨 (다른 프로그램): {config_key}")
                        else:
                            log.error(f"핫키 등록 실패: {config_key}, 오류 코드: {error_code}")
                        if hotkey_id == HOTKEY_ID_SCAN:
                            return
                    else:
                        log.debug(f"핫키 등록: {config_key} (mod={modifiers}, vk={vk})")

        msg = wintypes.MSG()
        while self._running:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break

            if msg.message == win32con.WM_HOTKEY:
                hotkey_id = msg.wParam
                if hotkey_id == HOTKEY_ID_EXIT:
                    log.info("종료 단축키 감지")
                    os.kill(os.getpid(), signal.SIGINT)
                else:
                    callback = self._callbacks.get(hotkey_id)
                    if callback:
                        threading.Thread(target=callback, daemon=True).start()

            elif msg.message == win32con.WM_USER + 1:
                self._register_selection_hotkeys()

            elif msg.message == win32con.WM_USER + 2:
                self._unregister_selection_hotkeys()

            elif msg.message == win32con.WM_USER + 10:
                self._unregister_all_hotkeys()
                self._cleanup_event.set()

        # 정리
        user32.UnregisterHotKey(None, HOTKEY_ID_SCAN)
        user32.UnregisterHotKey(None, HOTKEY_ID_EXIT)

    def _register_selection_hotkeys(self) -> None:
        user32.RegisterHotKey(None, HOTKEY_ID_NUM1, 0, VK_1)
        user32.RegisterHotKey(None, HOTKEY_ID_NUM2, 0, VK_2)
        user32.RegisterHotKey(None, HOTKEY_ID_NUM3, 0, VK_3)
        user32.RegisterHotKey(None, HOTKEY_ID_NUM4, 0, VK_4)

    def _unregister_selection_hotkeys(self) -> None:
        user32.UnregisterHotKey(None, HOTKEY_ID_NUM1)
        user32.UnregisterHotKey(None, HOTKEY_ID_NUM2)
        user32.UnregisterHotKey(None, HOTKEY_ID_NUM3)
        user32.UnregisterHotKey(None, HOTKEY_ID_NUM4)

    def _unregister_all_hotkeys(self) -> None:
        if self._selection_mode_active:
            self._unregister_selection_hotkeys()
            self._selection_mode_active = False

        user32.UnregisterHotKey(None, HOTKEY_ID_SCAN)
        user32.UnregisterHotKey(None, HOTKEY_ID_EXIT)

    def cleanup(self) -> None:
        """핫키 해제 + WM_QUIT 전송. 최대 2초 대기."""
        if not self._thread_id:
            return

        self._cleanup_event.clear()
        ctypes.windll.user32.PostThreadMessageW(
            self._thread_id,
            win32con.WM_USER + 10,
            0,
            0,
        )

        self._cleanup_event.wait(timeout=1.0)

        self._running = False
        ctypes.windll.user32.PostThreadMessageW(
            self._thread_id, win32con.WM_QUIT, 0, 0
        )

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        self._thread = None
        self._thread_id = None


def wait_for_exit() -> None:
    """무한 대기. KeyboardInterrupt 발생 시 반환."""
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
