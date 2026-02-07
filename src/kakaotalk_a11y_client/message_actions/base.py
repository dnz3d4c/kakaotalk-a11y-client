# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""메시지 액션 추상 베이스"""

from abc import ABC, abstractmethod


class MessageAction(ABC):
    """메시지 액션 베이스 클래스"""

    @abstractmethod
    def execute(self) -> None:
        """액션 실행 - 실시간으로 현재 포커스에서 추출"""
        pass
