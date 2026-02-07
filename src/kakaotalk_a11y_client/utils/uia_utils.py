# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""UIA 탐색 유틸리티. 필터링, 재귀 탐색."""

import time
from typing import Callable, List, Optional, Tuple

import uiautomation as auto

from ..config import FILTER_MAX_CONSECUTIVE_EMPTY, KAKAO_LIST_CONTROL_CLASS, KAKAO_MESSAGE_LIST_NAME
from .debug import get_logger
from .profiler import profiler, profile_logger

# =============================================================================
# re-export (실제 사용되는 것만)
# =============================================================================

from .uia_exceptions import safe_uia_call

from .uia_tree_dump import dump_tree_json

log = get_logger("UIA")


# =============================================================================
# SmartListFilter
# =============================================================================

class SmartListFilter:
    """빈 ListItem 필터. 캐시 활용 + 연속 빈 항목 15개 발견 시 조기 종료."""

    def __init__(self):
        # 캐싱: 마지막으로 유효했던 인덱스 범위
        self._valid_range_cache: Optional[Tuple[int, int]] = None
        self._cache_hit_count = 0
        self._cache_miss_count = 0

    def filter_list_items(
        self,
        parent: auto.Control,
        max_items: int = 100,
        use_cache: bool = True
    ) -> List[auto.Control]:
        start = time.perf_counter()

        with profiler.measure("GetChildren"):
            children = parent.GetChildren()

        total_count = len(children)
        profile_logger.debug(f"ListItems 필터링 시작: total={total_count}")

        if total_count == 0:
            return []

        valid_items: List[auto.Control] = []
        empty_count = 0
        consecutive_empty = 0
        max_consecutive_empty = FILTER_MAX_CONSECUTIVE_EMPTY

        # 캐시 활용 (이전에 유효했던 범위 먼저)
        start_idx = 0
        if use_cache and self._valid_range_cache:
            cached_start, cached_end = self._valid_range_cache
            if cached_start < total_count:
                start_idx = max(0, cached_start - 5)  # 약간의 여유
                self._cache_hit_count += 1
                profile_logger.debug(f"캐시 히트: 인덱스 {start_idx}부터 검사")
        else:
            self._cache_miss_count += 1

        # 캐시 범위 먼저 검사
        indices_to_check = list(range(start_idx, total_count))
        # 캐시 이전 범위도 추가 (뒤에)
        if start_idx > 0:
            indices_to_check.extend(range(0, start_idx))

        first_valid_idx = -1
        last_valid_idx = -1

        with profiler.measure("filter_loop"):
            for i in indices_to_check:
                if len(valid_items) >= max_items:
                    profile_logger.debug(f"최대 항목 수 도달: {max_items}")
                    break

                child = children[i]

                # 빈 항목 체크 (Name 없거나 공백만)
                name = child.Name
                is_empty = not name or not name.strip()

                if is_empty:
                    empty_count += 1
                    consecutive_empty += 1

                    # 조기 종료: 유효 항목 있고 연속 빈 항목 초과
                    if valid_items and consecutive_empty > max_consecutive_empty:
                        profile_logger.debug(
                            f"조기 종료: 연속 빈 항목 {consecutive_empty}개 "
                            f"(인덱스 {i}/{total_count})"
                        )
                        break
                else:
                    valid_items.append(child)
                    consecutive_empty = 0

                    if first_valid_idx == -1:
                        first_valid_idx = i
                    last_valid_idx = i

        # 캐시 업데이트
        if first_valid_idx >= 0:
            self._valid_range_cache = (first_valid_idx, last_valid_idx)

        elapsed_ms = (time.perf_counter() - start) * 1000

        # 상세 프로파일링
        profiler.profile_list_items(
            total=total_count,
            empty=empty_count,
            valid=len(valid_items),
            elapsed_ms=elapsed_ms
        )

        # 통계 로깅
        total_cache_checks = self._cache_hit_count + self._cache_miss_count
        cache_rate = self._cache_hit_count / total_cache_checks if total_cache_checks > 0 else 0
        profile_logger.info(
            f"ListItems 결과: {len(valid_items)}/{total_count} 유효, "
            f"캐시 히트율: {cache_rate:.0%}, {elapsed_ms:.1f}ms"
        )

        return valid_items


# 싱글톤 인스턴스
smart_filter = SmartListFilter()


# =============================================================================
# 재귀 탐색
# =============================================================================

def find_all_descendants(
    element: auto.Control,
    condition_func: Optional[Callable[[auto.Control], bool]] = None,
    max_depth: int = 10
) -> list[auto.Control]:
    """재귀 탐색. condition_func 조건 충족 요소만 반환."""
    results = []

    def _traverse(el, depth):
        if depth >= max_depth:
            return
        try:
            children = el.GetChildren()
            for child in children:
                if condition_func is None or condition_func(child):
                    results.append(child)
                _traverse(child, depth + 1)
        except Exception:
            pass

    _traverse(element, 0)
    return results


def get_children_recursive(
    element: auto.Control,
    max_depth: int = 3,
    filter_empty: bool = True
) -> list[auto.Control]:
    """재귀 자식 탐색. filter_empty=True면 빈 Name 제외."""
    start = time.perf_counter()

    with profiler.measure("find_all_descendants"):
        children = find_all_descendants(element, max_depth=max_depth)

    total_count = len(children)
    empty_count = 0

    if filter_empty:
        result = []
        for c in children:
            if c.Name and c.Name.strip():
                result.append(c)
            else:
                empty_count += 1
    else:
        result = children

    elapsed_ms = (time.perf_counter() - start) * 1000
    profiler.profile_list_items(
        total=total_count,
        empty=empty_count,
        valid=len(result),
        elapsed_ms=elapsed_ms
    )

    return result


# =============================================================================
# 메시지 목록 포커스 확인
# =============================================================================

def is_focus_in_message_list(element: Optional[auto.Control] = None) -> bool:
    """요소가 메시지 목록 내부인지 확인. element=None이면 현재 포커스 조회."""
    try:
        current = element if element else auto.GetFocusedControl()
        if not current:
            log.debug("is_focus_in_message_list: element is None")
            return False

        for i in range(12):  # 부모 12단계까지 탐색
            if not current:
                break
            # 디버그: 각 단계별 ClassName, Name 출력
            try:
                cls_name = current.ClassName
                name = current.Name
                log.trace(f"is_focus_in_message_list: depth={i}, ClassName={cls_name}, Name={name[:20] if name else None}")
            except Exception:
                pass

            if (current.ClassName == KAKAO_LIST_CONTROL_CLASS
                    and current.Name == KAKAO_MESSAGE_LIST_NAME):
                log.debug(f"is_focus_in_message_list: found at depth={i}")
                return True
            current = current.GetParentControl()

        log.debug("is_focus_in_message_list: not found in 12 levels")
        return False

    except Exception as e:
        log.debug(f"is_focus_in_message_list: exception {e}")
        return False
