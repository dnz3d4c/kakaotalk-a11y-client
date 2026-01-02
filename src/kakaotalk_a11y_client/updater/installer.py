# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""업데이트 설치 모듈"""

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
    """zip 파일 압축 해제.

    Args:
        zip_path: 다운로드된 zip 파일 경로

    Returns:
        압축 해제된 폴더 경로 또는 None
    """
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
            log.info(f"압축 해제 완료: {extracted}")
            return extracted

        # Case 2: exe가 루트에 바로 있는 경우 (현재 배포 구조)
        if (EXTRACT_DIR / "KakaotalkA11y.exe").exists():
            log.info(f"압축 해제 완료: {EXTRACT_DIR}")
            return EXTRACT_DIR

        # Case 3: 첫 번째 하위 폴더에 exe가 있는 경우
        for item in EXTRACT_DIR.iterdir():
            if item.is_dir() and (item / "KakaotalkA11y.exe").exists():
                log.info(f"압축 해제 완료: {item}")
                return item

        log.error("KakaotalkA11y.exe를 찾을 수 없음")
        return None

    except zipfile.BadZipFile:
        log.error("손상된 zip 파일")
        return None
    except Exception as e:
        log.error(f"압축 해제 실패: {e}")
        return None


def get_install_dir() -> Optional[Path]:
    """현재 설치 디렉토리 반환.

    Returns:
        설치 디렉토리 경로 또는 None (개발 환경)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return None


def generate_batch_script(source_dir: Path, install_dir: Path, pid: int) -> str:
    """업데이트 batch 스크립트 생성.

    Args:
        source_dir: 새 버전 파일 경로
        install_dir: 설치 경로
        pid: 현재 프로세스 ID

    Returns:
        batch 스크립트 내용
    """
    return f"""@echo off
chcp 65001 > nul
echo 업데이트 적용 중...

:: 1. 기존 프로세스 종료 대기
:wait_loop
tasklist /FI "PID eq {pid}" 2>NUL | find /I "{pid}" >NUL
if not errorlevel 1 (
    echo 프로세스 종료 대기 중...
    timeout /t 1 /nobreak >NUL
    goto wait_loop
)

:: 2. 파일 복사
echo 파일 복사 중...
xcopy /E /Y /Q "{source_dir}\\*" "{install_dir}\\"
if errorlevel 1 (
    echo 파일 복사 실패
    pause
    exit /b 1
)

:: 3. 임시 파일 정리
echo 임시 파일 정리 중...
rd /S /Q "{TEMP_DIR}"
rd /S /Q "{EXTRACT_DIR}"

:: 4. 새 버전 실행
echo 새 버전 시작...
start "" "{install_dir}\\KakaotalkA11y.exe"

:: 5. 자기 자신 삭제
del "%~f0"
"""


def apply_update(extracted_dir: Path) -> bool:
    """업데이트 적용 (batch 스크립트 생성 및 실행).

    Args:
        extracted_dir: 압축 해제된 새 버전 폴더

    Returns:
        성공 여부
    """
    install_dir = get_install_dir()
    if not install_dir:
        log.error("개발 환경에서는 업데이트 불가")
        return False

    try:
        # batch 스크립트 생성
        bat_path = TEMP_DIR / "update.bat"
        bat_content = generate_batch_script(
            source_dir=extracted_dir,
            install_dir=install_dir,
            pid=os.getpid(),
        )
        bat_path.write_text(bat_content, encoding="cp949")

        log.info(f"업데이트 스크립트 생성: {bat_path}")

        # batch 실행 (분리된 프로세스)
        # start 명령어로 새 콘솔에서 실행
        os.system(f'start "Updater" cmd /c "{bat_path}"')

        log.info("업데이트 스크립트 실행됨")
        return True

    except Exception as e:
        log.error(f"업데이트 적용 실패: {e}")
        return False


def cleanup_temp() -> None:
    """임시 파일 정리."""
    try:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        if EXTRACT_DIR.exists():
            shutil.rmtree(EXTRACT_DIR)
        log.debug("임시 파일 정리 완료")
    except Exception as e:
        log.warning(f"임시 파일 정리 실패: {e}")


def get_download_path() -> Path:
    """다운로드 경로 반환."""
    return TEMP_DIR / "update.zip"
