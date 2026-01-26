# SPDX-FileCopyrightText: 2025 JEONG Ukjae <jeongukjae@gmail.com>
# SPDX-License-Identifier: Apache-2.0
"""테스트 스크립트 공통 유틸리티"""
import sys
from pathlib import Path

# src 경로 추가
_src_path = str(Path(__file__).parent.parent / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

import pythoncom
import uiautomation as auto


def setup():
    """COM 초기화. 스크립트 시작 시 호출."""
    pythoncom.CoInitialize()


def cleanup():
    """COM 해제. 스크립트 종료 시 호출."""
    pythoncom.CoUninitialize()


def find_kakao_window():
    """카카오톡 메인 창 반환. 못 찾으면 None."""
    root = auto.GetRootControl()
    for win in root.GetChildren():
        name = win.Name or ""
        cls = win.ClassName or ""
        if "EVA" in cls or "카카오톡" in name or "KakaoTalk" in name:
            return win
    return None
