# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""JSON 출력 포맷터."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import EventLog


class JsonFormatter:
    """JSON 출력 포맷터."""

    def __init__(
        self,
        file_path: Optional[Path] = None,
        pretty: bool = False,
        include_timestamp_iso: bool = True,
    ):
        """
        Args:
            file_path: 로그 파일 경로. None이면 콘솔 출력만.
            pretty: True면 들여쓰기된 JSON 출력
            include_timestamp_iso: True면 ISO 형식 타임스탬프 추가
        """
        self.file_path = file_path
        self.pretty = pretty
        self.include_timestamp_iso = include_timestamp_iso
        self._file: Optional[TextIO] = None

    def open(self) -> None:
        """파일 열기 (파일 로깅 시)."""
        if self.file_path:
            self._file = open(self.file_path, "a", encoding="utf-8")

    def close(self) -> None:
        """파일 닫기."""
        if self._file:
            self._file.close()
            self._file = None

    def format(self, event: "EventLog") -> str:
        """이벤트를 JSON 문자열로 변환."""
        data = event.to_dict()

        # ISO 타임스탬프 추가
        if self.include_timestamp_iso:
            dt = datetime.fromtimestamp(event.timestamp)
            data["timestamp_iso"] = dt.isoformat()

        if self.pretty:
            return json.dumps(data, ensure_ascii=False, indent=2)
        else:
            return json.dumps(data, ensure_ascii=False)

    def print(self, event: "EventLog") -> None:
        """이벤트를 출력."""
        line = self.format(event)
        print(line)

        # 파일에도 기록
        if self._file:
            self._file.write(line + "\n")
            self._file.flush()

    def __enter__(self) -> "JsonFormatter":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
