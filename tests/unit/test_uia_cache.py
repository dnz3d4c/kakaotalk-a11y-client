# SPDX-License-Identifier: MIT
"""UIACache 단위 테스트."""

import time
from unittest.mock import patch
import pytest

from kakaotalk_a11y_client.utils.uia_cache import UIACache, CacheEntry


class TestCacheEntry:
    """CacheEntry 테스트."""

    def test_is_valid_fresh_entry(self):
        """새 엔트리는 유효."""
        entry = CacheEntry(value="test", timestamp=time.time(), ttl_seconds=1.0)
        assert entry.is_valid is True

    def test_is_valid_expired_entry(self):
        """TTL 지난 엔트리는 무효."""
        old_time = time.time() - 2.0
        entry = CacheEntry(value="test", timestamp=old_time, ttl_seconds=1.0, last_access=old_time)
        assert entry.is_valid is False

    def test_age_ms(self):
        """나이를 밀리초로 반환."""
        entry = CacheEntry(value="test", timestamp=time.time())
        time.sleep(0.01)
        assert entry.age_ms >= 10


class TestUIACache:
    """UIACache 테스트."""

    def test_get_set_basic(self):
        """기본 저장/조회."""
        cache = UIACache(default_ttl=1.0)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent_key(self):
        """없는 키 조회 시 None."""
        cache = UIACache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self):
        """TTL 만료 시 캐시 미스."""
        cache = UIACache(default_ttl=0.05)  # 50ms TTL
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        time.sleep(0.1)  # TTL 초과 대기
        assert cache.get("key1") is None

    def test_custom_ttl_per_entry(self):
        """엔트리별 커스텀 TTL."""
        cache = UIACache(default_ttl=1.0)
        cache.set("short", "value", ttl=0.05)
        cache.set("long", "value", ttl=2.0)

        time.sleep(0.1)
        assert cache.get("short") is None  # 만료됨
        assert cache.get("long") == "value"  # 아직 유효

    def test_lru_eviction(self):
        """MAX_SIZE 초과 시 오래된 항목 제거."""
        cache = UIACache(default_ttl=10.0)

        # MAX_SIZE개 저장
        for i in range(UIACache.MAX_SIZE):
            cache.set(f"key{i}", f"value{i}")

        # 첫 번째 항목 접근 (접근 시간 갱신)
        cache.get("key0")

        # 추가 항목 저장 (LRU 발동)
        cache.set("new_key", "new_value")

        # key1이 제거됨 (key0은 최근 접근)
        assert cache.get("key0") == "value0"
        assert cache.get("key1") is None  # 제거됨
        assert cache.get("new_key") == "new_value"

    def test_touch_updates_access_time(self):
        """get() 시 접근 시간 갱신."""
        cache = UIACache(default_ttl=0.1)
        cache.set("key1", "value1")

        # 접근하면 TTL 리셋
        time.sleep(0.05)
        assert cache.get("key1") == "value1"  # 접근 시간 갱신

        time.sleep(0.05)
        assert cache.get("key1") == "value1"  # 아직 유효

    def test_hit_miss_count(self):
        """적중/미스 카운트."""
        cache = UIACache()
        cache.set("key1", "value1")

        cache.get("key1")  # hit
        cache.get("key1")  # hit
        cache.get("nonexistent")  # miss

        assert cache._hit_count == 2
        assert cache._miss_count == 1

    def test_hit_rate(self):
        """적중률 계산."""
        cache = UIACache()
        cache.set("key1", "value1")

        cache.get("key1")  # hit
        cache.get("nonexistent")  # miss

        assert cache.hit_rate == 0.5

    def test_hit_rate_no_access(self):
        """접근 없을 때 적중률 0."""
        cache = UIACache()
        assert cache.hit_rate == 0.0

    def test_get_stats(self):
        """통계 정보 반환."""
        cache = UIACache(default_ttl=1.0)
        cache.set("key1", "value1")
        cache.get("key1")

        stats = cache.get_stats()
        assert stats["size"] == 1
        assert stats["hit_count"] == 1
        assert stats["miss_count"] == 0
        assert stats["default_ttl"] == 1.0
        assert "hit_rate" in stats

    def test_clear(self):
        """캐시 초기화."""
        cache = UIACache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert cache.size == 0
        assert cache.get("key1") is None

    def test_invalidate(self):
        """단일 키 무효화."""
        cache = UIACache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        result = cache.invalidate("key1")

        assert result is True
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_invalidate_nonexistent(self):
        """없는 키 무효화 시 False."""
        cache = UIACache()
        result = cache.invalidate("nonexistent")
        assert result is False

    def test_invalidate_prefix(self):
        """prefix로 시작하는 키 일괄 무효화."""
        cache = UIACache()
        cache.set("user:1", "value1")
        cache.set("user:2", "value2")
        cache.set("item:1", "value3")

        count = cache.invalidate_prefix("user:")

        assert count == 2
        assert cache.get("user:1") is None
        assert cache.get("user:2") is None
        assert cache.get("item:1") == "value3"

    def test_get_or_set_cache_hit(self):
        """get_or_set: 캐시 적중 시 factory 호출 안 함."""
        cache = UIACache()
        cache.set("key1", "cached_value")

        factory_called = False
        def factory():
            nonlocal factory_called
            factory_called = True
            return "new_value"

        result = cache.get_or_set("key1", factory)

        assert result == "cached_value"
        assert factory_called is False

    def test_get_or_set_cache_miss(self):
        """get_or_set: 캐시 미스 시 factory 호출."""
        cache = UIACache()

        factory_called = False
        def factory():
            nonlocal factory_called
            factory_called = True
            return "new_value"

        result = cache.get_or_set("key1", factory)

        assert result == "new_value"
        assert factory_called is True
        assert cache.get("key1") == "new_value"

    def test_cleanup_expired(self):
        """만료된 항목 정리."""
        cache = UIACache(default_ttl=0.05)
        cache.set("key1", "value1")
        cache.set("key2", "value2", ttl=10.0)  # 긴 TTL

        time.sleep(0.1)

        count = cache.cleanup_expired()

        assert count == 1  # key1만 만료
        assert cache.get("key2") == "value2"

    def test_size_property(self):
        """size 프로퍼티."""
        cache = UIACache()
        assert cache.size == 0

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert cache.size == 2
