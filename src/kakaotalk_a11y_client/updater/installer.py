# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""업데이트 설치. zip 추출 + batch 스크립트로 파일 교체."""

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from ..utils.debug import get_logger

log = get_logger("Installer")

# 임시 폴더 경로
TEMP_DIR = Path(tempfile.gettempdir()) / "kakaotalk_a11y_update"
EXTRACT_DIR = Path(tempfile.gettempdir()) / "kakaotalk_a11y_extract"


def extract_update(zip_path: Path) -> Optional[Path]:
    """zip 압축 해제. KakaotalkA11y.exe 포함 폴더 경로 반환."""
    try:
        # 기존 압축 해제 폴더 정리
        if EXTRACT_DIR.exists():
            shutil.rmtree(EXTRACT_DIR)

        EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(EXTRACT_DIR)

        # Case 1: KakaotalkA11y 하위 폴더가 있는 경우
        extracted = EXTRACT_DIR / "KakaotalkA11y"
        if extracted.exists() and (extracted / "KakaotalkA11y.exe").exists():
            log.info(f"extraction completed: {extracted}")
            return extracted

        # Case 2: exe가 루트에 바로 있는 경우 (현재 배포 구조)
        if (EXTRACT_DIR / "KakaotalkA11y.exe").exists():
            log.info(f"extraction completed: {EXTRACT_DIR}")
            return EXTRACT_DIR

        # Case 3: 첫 번째 하위 폴더에 exe가 있는 경우
        for item in EXTRACT_DIR.iterdir():
            if item.is_dir() and (item / "KakaotalkA11y.exe").exists():
                log.info(f"extraction completed: {item}")
                return item

        log.error("KakaotalkA11y.exe not found")
        return None

    except zipfile.BadZipFile:
        log.error("corrupted zip file")
        return None
    except Exception as e:
        log.error(f"extraction failed: {e}")
        return None


def get_install_dir() -> Optional[Path]:
    """설치 디렉토리. PyInstaller 빌드 아니면 None."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return None


def generate_batch_script(source_dir: Path, install_dir: Path, pid: int) -> str:
    """프로세스 종료 대기 -> 파일 복사 -> 재시작 batch 스크립트."""
    log_file = TEMP_DIR / "update_log.txt"
    return f"""@echo off
chcp 65001 > nul
set LOGFILE="{log_file}"

:: 로그 함수
call :log "=== 업데이트 시작 ==="
call :log "PID: {pid}"
call :log "소스: {source_dir}"
call :log "대상: {install_dir}"

:: 1. 기존 프로세스 종료 대기
call :log "1단계: 프로세스 종료 대기"
set /a WAIT_COUNT=0
:wait_loop
tasklist /FI "PID eq {pid}" 2>NUL | find /I "{pid}" >NUL
if not errorlevel 1 (
    set /a WAIT_COUNT+=1
    if %WAIT_COUNT% GEQ 30 (
        call :log "ERROR: 프로세스 종료 대기 타임아웃 (30초)"
        pause
        exit /b 1
    )
    timeout /t 1 /nobreak >NUL
    goto wait_loop
)
call :log "1단계 완료: 프로세스 종료됨"

:: 2. 파일 복사 (robocopy 사용 - xcopy보다 안정적)
call :log "2단계: 파일 복사 시작"
robocopy "{source_dir}" "{install_dir}" /E /NFL /NDL /NJH /NJS /R:3 /W:1 > nul 2>&1
set ROBO_EXIT=%errorlevel%
:: robocopy 종료 코드: 0-7은 성공, 8 이상은 실패
if %ROBO_EXIT% GEQ 8 (
    call :log "ERROR: 파일 복사 실패 (robocopy exit=%ROBO_EXIT%)"
    pause
    exit /b 1
)
call :log "2단계 완료: 파일 복사 성공 (robocopy exit=%ROBO_EXIT%)"

:: 3. 새 버전 실행
call :log "3단계: 새 버전 실행"
start "" "{install_dir}\\KakaotalkA11y.exe"
:: start 명령은 errorlevel을 변경 안 함 - 프로세스 시작 여부만 확인
call :log "3단계 완료: 새 버전 실행 요청됨"

:: 4. 임시 파일 정리 (로그 파일 제외)
call :log "4단계: 임시 파일 정리"
rd /S /Q "{EXTRACT_DIR}" 2>nul
call :log "=== 업데이트 완료 ==="

:: 5. 자기 자신 삭제
del "%~f0"
exit /b 0

:log
echo %date% %time% %~1 >> %LOGFILE%
echo %~1
goto :eof
"""


def apply_update(extracted_dir: Path) -> bool:
    """batch 스크립트 실행. 성공 시 프로그램 종료됨."""
    install_dir = get_install_dir()
    if not install_dir:
        log.error("cannot update in development environment")
        return False

    log.debug(f"apply_update: source={extracted_dir}, target={install_dir}")

    try:
        # 임시 폴더 생성
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        # batch 스크립트 생성
        bat_path = TEMP_DIR / "update.bat"
        bat_content = generate_batch_script(
            source_dir=extracted_dir,
            install_dir=install_dir,
            pid=os.getpid(),
        )
        bat_path.write_text(bat_content, encoding="cp949")

        # 파일 생성 확인
        if not bat_path.exists():
            log.error(f"batch script not created: {bat_path}")
            return False

        log.info(f"update script created: {bat_path} ({bat_path.stat().st_size} bytes)")

        # batch 실행 (분리된 프로세스)
        # start 명령어로 새 콘솔에서 실행
        ret = os.system(f'start "Updater" cmd /c "{bat_path}"')
        if ret != 0:
            log.warning(f"os.system returned {ret}, but batch may still run")

        log.info("update script executed")
        return True

    except Exception as e:
        log.error(f"update apply failed: {e}")
        return False


def cleanup_temp() -> None:
    try:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        if EXTRACT_DIR.exists():
            shutil.rmtree(EXTRACT_DIR)
        log.debug("temp files cleaned up")
    except Exception as e:
        log.warning(f"temp cleanup failed: {e}")


def get_download_path() -> Path:
    return TEMP_DIR / "update.zip"
