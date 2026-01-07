# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""프로세스 중복 실행 방지. msvcrt 잠금 + PID 파일 병행."""

import os
import sys
import time
import ctypes
import msvcrt
import threading
from pathlib import Path
from typing import Optional

from .debug import get_logger

log = get_logger("ProcessLock")

# Windows API
kernel32 = ctypes.windll.kernel32
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_TERMINATE = 0x0001
STILL_ACTIVE = 259  # GetExitCodeProcess 반환값


class ProcessLock:

    def __init__(self, name: str = "kakaotalk-a11y"):
        self.name = name
        temp_dir = Path(os.environ.get('TEMP', '/tmp'))
        self.lock_file = temp_dir / f"{name}.lock"
        self.pid_file = temp_dir / f"{name}.pid"
        self._file_handle: Optional[object] = None
        self._locked = False

    def acquire(self) -> bool:
        """잠금 획득. 성공 시 True, 다른 인스턴스 실행 중이면 False."""
        return self._try_acquire() or self._retry_after_stale_check()

    def _try_acquire(self) -> bool:
        try:
            # 1. lock 파일 열기 (없으면 생성)
            self._file_handle = open(self.lock_file, 'w')

            # 2. 배타적 잠금 시도 (non-blocking)
            # LK_NBLCK: 잠금 실패 시 즉시 IOError 발생
            msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_NBLCK, 1)

            # 3. PID 기록 (기존 프로세스 종료용)
            self.pid_file.write_text(str(os.getpid()))
            self._locked = True
            log.debug(f"잠금 획득: {self.lock_file}, PID={os.getpid()}")
            return True

        except (IOError, OSError) as e:
            log.debug(f"잠금 시도 실패: {e}")
            if self._file_handle:
                try:
                    self._file_handle.close()
                except Exception:
                    pass
                self._file_handle = None
            return False

    def _retry_after_stale_check(self) -> bool:
        # PID 파일로 실제 프로세스 확인
        if not self.pid_file.exists():
            # PID 파일 없으면 stale lock 파일
            self._cleanup_stale_files()
            return self._try_acquire()

        try:
            old_pid = int(self.pid_file.read_text().strip())
            if self._is_process_running(old_pid):
                log.debug(f"기존 프로세스 실행 중: PID={old_pid}")
                return False
            else:
                log.debug(f"stale 파일 발견, 정리 후 재시도: PID={old_pid}")
                self._cleanup_stale_files()
                return self._try_acquire()
        except (ValueError, OSError) as e:
            log.debug(f"PID 파일 읽기 오류: {e}")
            self._cleanup_stale_files()
            return self._try_acquire()

    def release(self) -> None:
        if self._file_handle and self._locked:
            # 1. 파일 잠금 해제
            try:
                msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception as e:
                log.debug(f"잠금 해제 오류: {e}")

            # 2. 파일 핸들 닫기
            try:
                self._file_handle.close()
            except Exception:
                pass

            # 3. PID 파일 삭제
            try:
                if self.pid_file.exists():
                    current_pid = str(os.getpid())
                    if self.pid_file.read_text().strip() == current_pid:
                        self.pid_file.unlink()
            except Exception as e:
                log.debug(f"PID 파일 삭제 오류: {e}")

            # 4. lock 파일 삭제 (선택적)
            try:
                self.lock_file.unlink(missing_ok=True)
            except Exception:
                pass

            log.debug("잠금 해제 완료")

        self._file_handle = None
        self._locked = False

    def terminate_existing(self) -> bool:
        """기존 프로세스 종료 시도. 성공/없음 시 True, 실패 시 False."""
        if not self.pid_file.exists():
            return True

        try:
            old_pid = int(self.pid_file.read_text().strip())
            if not self._is_process_running(old_pid):
                # stale PID 파일 정리
                try:
                    self.pid_file.unlink()
                except OSError:
                    pass
                return True

            # 종료 시도
            log.debug(f"기존 프로세스 종료 시도: PID={old_pid}")
            return self._terminate_process(old_pid)
        except (ValueError, OSError) as e:
            log.debug(f"기존 프로세스 종료 오류: {e}")
            return False

    def _is_process_running(self, pid: int) -> bool:
        """OpenProcess + GetExitCodeProcess로 프로세스 상태 확인."""
        try:
            handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
            if not handle:
                return False

            # 프로세스 종료 코드 확인
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                kernel32.CloseHandle(handle)
                # STILL_ACTIVE(259)면 아직 실행 중
                return exit_code.value == STILL_ACTIVE
            else:
                kernel32.CloseHandle(handle)
                return False
        except Exception:
            return False

    def _terminate_process(self, pid: int) -> bool:
        """taskkill로 프로세스 강제 종료."""
        import subprocess

        try:
            # taskkill /F /PID로 강제 종료
            result = subprocess.run(
                ['taskkill', '/F', '/PID', str(pid)],
                capture_output=True,
                timeout=5
            )

            # 종료 대기
            for _ in range(20):
                time.sleep(0.1)
                if not self._is_process_running(pid):
                    self._cleanup_stale_files()
                    log.debug(f"프로세스 종료 완료: PID={pid}")
                    return True

            log.debug(f"taskkill 후 프로세스 여전히 실행 중: PID={pid}")
            return False

        except subprocess.TimeoutExpired:
            log.debug(f"taskkill 타임아웃: PID={pid}")
            return False
        except FileNotFoundError:
            # taskkill 명령어 없음 - 대체 방법 시도
            log.debug("taskkill 명령어 없음, 대체 방법 시도")
            return self._terminate_process_fallback(pid)
        except Exception as e:
            log.debug(f"프로세스 종료 오류: {e}")
            return False

    def _terminate_process_fallback(self, pid: int) -> bool:
        try:
            import signal
            os.kill(pid, signal.SIGTERM)

            for _ in range(20):
                time.sleep(0.1)
                if not self._is_process_running(pid):
                    self._cleanup_stale_files()
                    return True

            # TerminateProcess 시도
            handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if handle:
                result = kernel32.TerminateProcess(handle, 1)
                kernel32.CloseHandle(handle)
                if result:
                    time.sleep(0.5)
                    self._cleanup_stale_files()
                    return True
            return False
        except Exception:
            return False

    def _cleanup_stale_files(self) -> None:
        try:
            self.pid_file.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            self.lock_file.unlink(missing_ok=True)
        except OSError:
            pass


# 전역 인스턴스 (스레드 안전)
_lock: Optional[ProcessLock] = None
_lock_mutex = threading.Lock()


def get_process_lock() -> ProcessLock:
    """전역 싱글톤 인스턴스 반환 (스레드 안전)."""
    global _lock
    if _lock is None:
        with _lock_mutex:
            # Double-check locking
            if _lock is None:
                _lock = ProcessLock()
    return _lock
