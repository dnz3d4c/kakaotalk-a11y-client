# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""버전 비교 유틸리티"""

import re
from typing import Tuple


def parse_version(version: str) -> Tuple[int, ...]:
    """버전 문자열을 튜플로 변환.

    Args:
        version: 'v0.2.1' 또는 '0.2.1' 형태

    Returns:
        (0, 2, 1) 형태의 튜플
    """
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", version)
    if match:
        return tuple(int(x) for x in match.groups())
    return (0, 0, 0)


def is_newer(remote: str, local: str) -> bool:
    """원격 버전이 로컬보다 새로운지 확인.

    Args:
        remote: 원격 버전 (예: 'v0.3.0')
        local: 로컬 버전 (예: '0.2.1')

    Returns:
        원격이 더 새로우면 True
    """
    return parse_version(remote) > parse_version(local)
