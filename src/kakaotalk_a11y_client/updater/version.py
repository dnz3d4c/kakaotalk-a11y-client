# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""버전 비교."""

import re
from typing import Tuple


def parse_version(version: str) -> Tuple[int, ...]:
    """'v0.2.1' 또는 '0.2.1' -> (0, 2, 1)"""
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", version)
    if match:
        return tuple(int(x) for x in match.groups())
    return (0, 0, 0)


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)
