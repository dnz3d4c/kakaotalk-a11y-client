# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""UIA 요소 TTL 캐싱. NVDA 패턴 (0.5초 기본 TTL)."""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable

from ..config import CACHE_MESSAGE_LIST_TTL
from .profiler import profile_logger


@dataclass
class CacheEntry:
    value: Any
    timestamp: float
    ttl_seconds: float = 0.5
    last_access: float = field(default_factory=time.time)

    @property
    def is_valid(self) -> bool:
        return time.time() - self.last_access < self.ttl_seconds

    @property
    def age_ms(self) -> float:
        return (time.time() - self.timestamp) * 1000


class UIACache:
    """TTL 캐시. get() 시 접근시간 갱신, LRU로 50개 제한."""

    MAX_SIZE = 50  # 최대 캐시 항목 수

    def __init__(self, default_ttl: float = 0.5):
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._hit_count = 0
        self._miss_count = 0

    def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry and entry.is_valid:
            entry.last_access = time.time()  # Touch: 접근 시간 갱신
            self._hit_count += 1
            return entry.value
        self._miss_count += 1
        return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        # LRU: 크기 초과 시 가장 오래된 항목 제거
        if key not in self._cache and len(self._cache) >= self.MAX_SIZE:
            oldest_key = min(self._cache, key=lambda k: self._cache[k].last_access)
            del self._cache[oldest_key]

        now = time.time()
        self._cache[key] = CacheEntry(
            value=value,
            timestamp=now,
            ttl_seconds=ttl if ttl is not None else self.default_ttl,
            last_access=now
        )

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[float] = None
    ) -> Any:
        """캐시에서 가져오거나 없으면 factory로 생성하여 저장."""
        value = self.get(key)
        if value is not None:
            return value

        value = factory()
        self.set(key, value, ttl)
        return value

    def invalidate(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def invalidate_prefix(self, prefix: str) -> int:
        """prefix로 시작하는 모든 키 무효화. 삭제 개수 반환."""
        keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        for key in keys_to_delete:
            del self._cache[key]
        return len(keys_to_delete)

    def clear(self) -> None:
        self._cache.clear()
        profile_logger.debug("UIACache cleared")

    def cleanup_expired(self) -> int:
        """만료된 항목 정리. 삭제 개수 반환."""
        expired = [k for k, v in self._cache.items() if not v.is_valid]
        for key in expired:
            del self._cache[key]
        return len(expired)

    @property
    def hit_rate(self) -> float:
        total = self._hit_count + self._miss_count
        return self._hit_count / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        return len(self._cache)

    def get_stats(self) -> dict:
        return {
            "size": self.size,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": f"{self.hit_rate:.1%}",
            "default_ttl": self.default_ttl,
        }

    def log_stats(self) -> None:
        stats = self.get_stats()
        profile_logger.info(
            f"UIACache 통계: size={stats['size']}, "
            f"hits={stats['hit_count']}, misses={stats['miss_count']}, "
            f"hit_rate={stats['hit_rate']}"
        )


# =============================================================================
# 글로벌 캐시 인스턴스
# =============================================================================

# 메시지 목록 캐시 (폴링 간격과 동기화)
message_list_cache = UIACache(default_ttl=CACHE_MESSAGE_LIST_TTL)


def clear_all_caches() -> None:
    message_list_cache.clear()
    profile_logger.info("모든 UIA 캐시 초기화됨")


def log_all_cache_stats() -> None:
    profile_logger.info("=== UIA 캐시 통계 ===")
    profile_logger.info(f"message_list_cache: {message_list_cache.get_stats()}")
