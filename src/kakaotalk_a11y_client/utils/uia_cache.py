# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""UIA 요소 캐싱 (NVDA 패턴)

NVDA는 Window Handle을 0.5초 TTL로 캐싱.
자주 접근하는 요소/속성을 캐싱하여 반복 UIA 호출 제거.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable

from .profiler import profile_logger


@dataclass
class CacheEntry:
    """캐시 항목"""
    value: Any
    timestamp: float
    ttl_seconds: float = 0.5
    last_access: float = field(default_factory=time.time)

    @property
    def is_valid(self) -> bool:
        """TTL 내 유효한지 확인 (마지막 접근 기준)"""
        return time.time() - self.last_access < self.ttl_seconds

    @property
    def age_ms(self) -> float:
        """캐시 나이 (밀리초)"""
        return (time.time() - self.timestamp) * 1000


class UIACache:
    """UIA 요소 TTL 캐시 (NVDA 패턴)

    사용법:
        cache = UIACache(default_ttl=0.5)

        # 직접 사용
        value = cache.get("key")
        if value is None:
            value = expensive_operation()
            cache.set("key", value)

        # 또는 get_or_set 사용
        value = cache.get_or_set("key", expensive_operation)

    특징:
        - Touch: get() 시 last_access 갱신 → 자주 접근하면 만료 안 됨
        - LRU: 최대 크기 초과 시 가장 오래된 항목 제거
    """

    MAX_SIZE = 50  # 최대 캐시 항목 수

    def __init__(self, default_ttl: float = 0.5):
        """
        Args:
            default_ttl: 기본 TTL (초). NVDA는 0.5초 사용.
        """
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._hit_count = 0
        self._miss_count = 0

    def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 가져오기

        Args:
            key: 캐시 키

        Returns:
            캐시된 값 또는 None (만료/없음)
        """
        entry = self._cache.get(key)
        if entry and entry.is_valid:
            entry.last_access = time.time()  # Touch: 접근 시간 갱신
            self._hit_count += 1
            return entry.value
        self._miss_count += 1
        return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """캐시에 값 저장

        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: TTL (초). None이면 기본값 사용.
        """
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
        """캐시에서 가져오거나 없으면 생성하여 저장

        Args:
            key: 캐시 키
            factory: 값 생성 함수
            ttl: TTL (초)

        Returns:
            캐시된 값 또는 새로 생성된 값
        """
        value = self.get(key)
        if value is not None:
            return value

        value = factory()
        self.set(key, value, ttl)
        return value

    def invalidate(self, key: str) -> bool:
        """특정 키 무효화

        Args:
            key: 캐시 키

        Returns:
            True면 삭제됨
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def invalidate_prefix(self, prefix: str) -> int:
        """특정 prefix로 시작하는 모든 키 무효화

        Args:
            prefix: 키 prefix

        Returns:
            삭제된 항목 수
        """
        keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        for key in keys_to_delete:
            del self._cache[key]
        return len(keys_to_delete)

    def clear(self) -> None:
        """전체 캐시 비우기"""
        self._cache.clear()
        profile_logger.debug("UIACache cleared")

    def cleanup_expired(self) -> int:
        """만료된 항목 정리

        Returns:
            정리된 항목 수
        """
        expired = [k for k, v in self._cache.items() if not v.is_valid]
        for key in expired:
            del self._cache[key]
        return len(expired)

    @property
    def hit_rate(self) -> float:
        """캐시 히트율 (0.0 ~ 1.0)"""
        total = self._hit_count + self._miss_count
        return self._hit_count / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        """현재 캐시 항목 수"""
        return len(self._cache)

    def get_stats(self) -> dict:
        """캐시 통계 반환"""
        return {
            "size": self.size,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": f"{self.hit_rate:.1%}",
            "default_ttl": self.default_ttl,
        }

    def log_stats(self) -> None:
        """캐시 통계 로깅"""
        stats = self.get_stats()
        profile_logger.info(
            f"UIACache 통계: size={stats['size']}, "
            f"hits={stats['hit_count']}, misses={stats['miss_count']}, "
            f"hit_rate={stats['hit_rate']}"
        )


# =============================================================================
# 글로벌 캐시 인스턴스
# =============================================================================

# 메시지 목록 캐시 (폴링 간격과 동기화: 1.0초)
message_list_cache = UIACache(default_ttl=1.0)

# 메뉴 컨트롤 캐시 (중간 TTL)
menu_cache = UIACache(default_ttl=0.5)

# 윈도우 핸들 캐시 (긴 TTL - 잘 안 변함)
window_cache = UIACache(default_ttl=1.0)


def clear_all_caches() -> None:
    """모든 글로벌 캐시 비우기"""
    message_list_cache.clear()
    menu_cache.clear()
    window_cache.clear()
    profile_logger.info("모든 UIA 캐시 초기화됨")


def log_all_cache_stats() -> None:
    """모든 글로벌 캐시 통계 로깅"""
    profile_logger.info("=== UIA 캐시 통계 ===")
    profile_logger.info(f"message_list_cache: {message_list_cache.get_stats()}")
    profile_logger.info(f"menu_cache: {menu_cache.get_stats()}")
    profile_logger.info(f"window_cache: {window_cache.get_stats()}")
