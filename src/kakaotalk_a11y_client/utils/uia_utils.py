# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""UIA 탐색 유틸리티 - 모든 navigation 모듈에서 공통 사용

NVDA 패턴 적용:
- COMError 안전 래퍼 (safe_uia_call)
- UIA 신뢰도 판단 (is_good_uia_element, should_use_uia_for_window)
"""

import functools
import time
from typing import Any, Callable, List, Optional, Tuple

import uiautomation as auto

try:
    from comtypes import COMError
except ImportError:
    # comtypes가 없으면 기본 Exception 사용
    COMError = Exception

from ..config import FILTER_MAX_CONSECUTIVE_EMPTY
from .debug import get_logger
from .profiler import profiler, profile_logger

log = get_logger("UIA")


# =============================================================================
# NVDA 패턴 1: UIA 신뢰도 판단
# =============================================================================

# UIA가 잘 동작하는 카카오톡 클래스
KAKAO_GOOD_UIA_CLASSES = [
    "EVA_Window",
    "EVA_Window_Dblclk",
    "EVA_VH_ListControl_Dblclk",
    "EVA_Menu",
]

# UIA가 불안정한 클래스 (무시하거나 폴백)
KAKAO_BAD_UIA_CLASSES = [
    "Chrome_WidgetWin_0",      # 광고 웹뷰
    "Chrome_WidgetWin_1",      # Chromium 내부
    "Chrome_RenderWidgetHostHWND",  # 웹 콘텐츠
]

# UIA를 무시해야 하는 컨트롤 패턴
KAKAO_IGNORE_PATTERNS = [
    {"ControlTypeName": "ListItemControl", "Name": ""},  # 가상 스크롤 placeholder
]


def is_good_uia_element(control: auto.Control) -> bool:
    """이 요소의 UIA 정보를 신뢰할 수 있는지 판단 (NVDA 패턴)

    Args:
        control: UIA 컨트롤

    Returns:
        True면 UIA 정보 신뢰 가능
    """
    try:
        class_name = control.ClassName or ""

        # 명시적으로 나쁜 클래스
        if class_name in KAKAO_BAD_UIA_CLASSES:
            return False

        # 무시 패턴 체크
        for pattern in KAKAO_IGNORE_PATTERNS:
            match = True
            for key, value in pattern.items():
                if getattr(control, key, None) != value:
                    match = False
                    break
            if match:
                return False

        return True

    except (COMError, Exception):
        return False


def should_use_uia_for_window(hwnd: int) -> bool:
    """이 창에서 UIA를 사용해야 하는지 판단 (NVDA 패턴)

    Args:
        hwnd: 윈도우 핸들

    Returns:
        True면 UIA 사용, False면 MSAA 폴백
    """
    try:
        import win32gui
        class_name = win32gui.GetClassName(hwnd)
        if class_name in KAKAO_GOOD_UIA_CLASSES:
            return True
        if class_name in KAKAO_BAD_UIA_CLASSES:
            return False
    except Exception:
        pass
    return True  # 기본은 UIA 사용


# =============================================================================
# NVDA 패턴 6: COMError 에러 핸들링
# =============================================================================

def safe_uia_call(
    func: Callable,
    default: Any = None,
    log_error: bool = True,
    error_msg: str = ""
) -> Any:
    """COMError 안전 래퍼 (NVDA 패턴)

    Args:
        func: 실행할 함수 (람다 또는 callable)
        default: 에러 시 반환할 기본값
        log_error: 에러 로깅 여부
        error_msg: 추가 에러 메시지

    Returns:
        함수 실행 결과 또는 기본값
    """
    try:
        return func()
    except COMError as e:
        if log_error:
            msg = f"COMError: {e}"
            if error_msg:
                msg = f"{error_msg} - {msg}"
            profile_logger.warning(msg)
        return default
    except LookupError as e:
        # 요소 못 찾음 - 정상적인 상황일 수 있음
        if log_error:
            profile_logger.debug(f"Element not found: {e}")
        return default
    except Exception as e:
        if log_error:
            msg = f"UIA Error: {e}"
            if error_msg:
                msg = f"{error_msg} - {msg}"
            profile_logger.error(msg)
        return default


def handle_uia_errors(default_return: Any = None):
    """UIA 호출 에러 처리 데코레이터 (NVDA 패턴)

    사용법:
        @handle_uia_errors(default_return=[])
        def get_children_safe(control):
            return control.GetChildren()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return safe_uia_call(
                lambda: func(*args, **kwargs),
                default=default_return,
                error_msg=func.__name__
            )
        return wrapper
    return decorator


# 편의 함수
@handle_uia_errors(default_return=[])
def get_children_safe(control: auto.Control) -> List[auto.Control]:
    """안전하게 자식 요소 가져오기"""
    return control.GetChildren()


@handle_uia_errors(default_return=None)
def get_focused_safe() -> Optional[auto.Control]:
    """안전하게 포커스된 컨트롤 가져오기"""
    return auto.GetFocusedControl()


@handle_uia_errors(default_return=None)
def get_parent_safe(control: auto.Control) -> Optional[auto.Control]:
    """안전하게 부모 컨트롤 가져오기"""
    return control.GetParentControl()


# =============================================================================
# 기존 코드
# =============================================================================


class SmartListFilter:
    """빈 ListItem 스마트 필터"""

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
        """
        빈 ListItem 필터링 (최적화 버전)

        전략:
        1. 캐시된 유효 범위부터 검사 (빠른 경로)
        2. 연속 빈 항목 15개 발견 시 조기 종료
        3. 상세 프로파일링
        """
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


def get_children_filtered(
    parent: auto.Control,
    max_items: int = 100,
    control_type: Optional[int] = None
) -> List[auto.Control]:
    """
    필터링된 자식 요소 가져오기 (SmartListFilter 사용)

    Args:
        parent: 부모 컨트롤
        max_items: 최대 반환 개수
        control_type: 필터링할 ControlType (None이면 모든 타입)

    Returns:
        유효한 자식 컨트롤 리스트
    """
    items = smart_filter.filter_list_items(parent, max_items)

    if control_type:
        items = [item for item in items if item.ControlType == control_type]

    return items


def find_all_descendants(
    element: auto.Control,
    condition_func: Optional[Callable[[auto.Control], bool]] = None,
    max_depth: int = 10
) -> list[auto.Control]:
    """재귀적으로 모든 자손 요소 탐색

    Args:
        element: 시작 UIA 요소
        condition_func: 필터 함수 (None이면 전체 반환)
        max_depth: 최대 탐색 깊이

    Returns:
        조건에 맞는 요소 리스트
    """
    results = []

    def _traverse(el, depth):
        if depth >= max_depth:  # >= 로 변경하여 조기 종료 (불필요한 재귀 호출 방지)
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


def find_first_descendant(
    element: auto.Control,
    condition_func: Callable[[auto.Control], bool],
    max_depth: int = 10
) -> Optional[auto.Control]:
    """조건 맞는 첫 번째 자손 반환

    Args:
        element: 시작 UIA 요소
        condition_func: 조건 함수
        max_depth: 최대 탐색 깊이

    Returns:
        조건에 맞는 첫 요소 또는 None
    """
    def _traverse(el, depth):
        if depth >= max_depth:  # >= 로 변경하여 조기 종료
            return None
        try:
            for child in el.GetChildren():
                if condition_func(child):
                    return child
                result = _traverse(child, depth + 1)
                if result:
                    return result
        except Exception:
            pass
        return None

    return _traverse(element, 0)


def get_children_recursive(
    element: auto.Control,
    max_depth: int = 3,
    filter_empty: bool = True
) -> list[auto.Control]:
    """자식 요소 가져오기 (선택적 재귀)

    기존 GetChildren() 대체용.

    Args:
        element: 부모 UIA 요소
        max_depth: 최대 탐색 깊이 (기본 3)
        filter_empty: True면 빈 이름 요소 필터링

    Returns:
        자식 요소 리스트
    """
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


def dump_tree(
    element: auto.Control,
    max_depth: int = 5,
    indent: int = 0,
    file=None,
    print_output: bool = False,
    include_coords: bool = False,
    highlight_empty: bool = False,
    filter_fn: Optional[Callable[[auto.Control], bool]] = None
) -> str:
    """요소의 하위 트리를 문자열로 덤프 (디버깅용)

    Args:
        element: 덤프할 UIA 요소
        max_depth: 최대 탐색 깊이
        indent: 현재 들여쓰기 수준
        file: 파일 객체 (선택)
        print_output: True면 콘솔에도 출력
        include_coords: True면 BoundingRectangle 좌표 출력
        highlight_empty: True면 빈 Name을 '<EMPTY>'로 강조 표시
        filter_fn: 필터 함수 - True 반환 시에만 해당 요소 출력 (자식은 계속 탐색)

    Returns:
        트리 구조 문자열
    """
    lines = []
    prefix = "  " * indent

    # 필터 조건 확인 (필터가 없거나 조건 만족 시 출력)
    should_output = filter_fn is None or filter_fn(element)

    if should_output:
        raw_name = element.Name or ""
        name = raw_name[:50]
        if len(raw_name) > 50:
            name += "..."

        # 빈 Name 강조 처리
        if highlight_empty and not raw_name.strip():
            name = "<EMPTY>"

        ctype = element.ControlTypeName
        cls = element.ClassName or ""
        auto_id = element.AutomationId or ""

        line = f"{prefix}[{ctype}] Name='{name}' Class={cls}"
        if auto_id:
            line += f" AutoId={auto_id}"

        # BoundingRectangle 좌표 추가
        if include_coords:
            try:
                rect = element.BoundingRectangle
                line += f" ({rect.left},{rect.top},{rect.right},{rect.bottom})"
            except Exception:
                pass

        lines.append(line)

        if print_output:
            print(line)
        if file:
            file.write(line + "\n")

    if indent < max_depth:
        try:
            for child in element.GetChildren():
                child_result = dump_tree(
                    child, max_depth, indent + 1, file, print_output,
                    include_coords, highlight_empty, filter_fn
                )
                if child_result.strip():  # 빈 결과 제외
                    lines.append(child_result)
        except Exception as e:
            err = f"{prefix}  (error: {e})"
            lines.append(err)
            if print_output:
                print(err)
            if file:
                file.write(err + "\n")

    return "\n".join(lines)


def dump_element_details(element: auto.Control) -> str:
    """요소의 모든 속성을 상세히 덤프 (디버깅용)

    Args:
        element: 덤프할 UIA 요소

    Returns:
        속성 문자열
    """
    lines = []
    lines.append(f"ControlType: {element.ControlTypeName}")
    lines.append(f"Name: {element.Name}")
    lines.append(f"ClassName: {element.ClassName}")
    lines.append(f"AutomationId: {element.AutomationId}")

    # LegacyIAccessible 패턴 시도
    try:
        legacy = element.GetLegacyIAccessiblePattern()
        if legacy:
            lines.append(f"Legacy.Name: {legacy.Name}")
            lines.append(f"Legacy.Value: {legacy.Value}")
            lines.append(f"Legacy.Description: {legacy.Description}")
    except Exception:
        pass

    # Value 패턴 시도
    try:
        value_pattern = element.GetValuePattern()
        if value_pattern:
            lines.append(f"Value: {value_pattern.Value}")
    except Exception:
        pass

    # Text 패턴 시도
    try:
        text_pattern = element.GetTextPattern()
        if text_pattern:
            lines.append(f"Text: {text_pattern.DocumentRange.GetText(-1)[:100]}")
    except Exception:
        pass

    return "\n".join(lines)


def dump_tree_json(
    element: auto.Control,
    max_depth: int = 5,
    current_depth: int = 0,
    include_coords: bool = False,
    filter_fn: Optional[Callable[[auto.Control], bool]] = None
) -> Optional[dict]:
    """요소의 하위 트리를 JSON 형식으로 덤프

    Args:
        element: 덤프할 UIA 요소
        max_depth: 최대 탐색 깊이
        current_depth: 현재 깊이 (내부용)
        include_coords: True면 BoundingRectangle 좌표 포함
        filter_fn: 필터 함수 - True 반환 시에만 해당 요소 포함

    Returns:
        트리 구조 dict (JSON 직렬화 가능)
    """
    # 필터 조건 확인
    if filter_fn is not None and not filter_fn(element):
        # 필터 불통과 시 자식만 탐색 (플랫하게 반환)
        children = []
        if current_depth < max_depth:
            try:
                for child in element.GetChildren():
                    child_result = dump_tree_json(
                        child, max_depth, current_depth + 1,
                        include_coords, filter_fn
                    )
                    if child_result:
                        if isinstance(child_result, list):
                            children.extend(child_result)
                        else:
                            children.append(child_result)
            except Exception:
                pass
        return children if children else None

    raw_name = element.Name or ""
    node = {
        "ControlType": element.ControlTypeName,
        "Name": raw_name,
        "ClassName": element.ClassName or "",
        "AutomationId": element.AutomationId or "",
        "IsEmpty": not raw_name.strip(),
    }

    if include_coords:
        try:
            rect = element.BoundingRectangle
            node["BoundingRectangle"] = {
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom
            }
        except Exception:
            pass

    # 자식 탐색
    if current_depth < max_depth:
        children = []
        try:
            for child in element.GetChildren():
                child_result = dump_tree_json(
                    child, max_depth, current_depth + 1,
                    include_coords, filter_fn
                )
                if child_result:
                    if isinstance(child_result, list):
                        children.extend(child_result)
                    else:
                        children.append(child_result)
        except Exception as e:
            children.append({"error": str(e)})

        if children:
            node["Children"] = children

    return node


def compare_trees(tree1: dict, tree2: dict) -> dict:
    """두 JSON 트리 비교

    Args:
        tree1: 첫 번째 트리 (dump_tree_json 결과)
        tree2: 두 번째 트리 (dump_tree_json 결과)

    Returns:
        {
            'added': [...],     # tree2에만 있는 요소
            'removed': [...],   # tree1에만 있는 요소
            'changed': [...],   # Name이 변경된 요소
            'unchanged': int,   # 변경 없는 요소 수
        }
    """
    def flatten_tree(tree: dict, path: str = "") -> dict:
        """트리를 {path: element} 딕셔너리로 평탄화"""
        result = {}
        if not tree or not isinstance(tree, dict):
            return result

        # 현재 요소 식별자 생성 (ControlType + ClassName + 인덱스)
        ctrl_type = tree.get("ControlType", "")
        class_name = tree.get("ClassName", "")
        current_id = f"{path}/{ctrl_type}[{class_name}]" if path else f"{ctrl_type}[{class_name}]"

        result[current_id] = {
            "Name": tree.get("Name", ""),
            "ControlType": ctrl_type,
            "ClassName": class_name,
            "AutomationId": tree.get("AutomationId", ""),
            "IsEmpty": tree.get("IsEmpty", False),
        }

        # 자식 처리
        children = tree.get("Children", [])
        child_counts = {}  # 같은 타입 자식 인덱스 관리
        for child in children:
            if isinstance(child, dict):
                child_type = child.get("ControlType", "")
                child_class = child.get("ClassName", "")
                child_key = f"{child_type}[{child_class}]"
                idx = child_counts.get(child_key, 0)
                child_counts[child_key] = idx + 1
                child_path = f"{current_id}/{child_key}#{idx}"
                result.update(flatten_tree(child, child_path))

        return result

    flat1 = flatten_tree(tree1)
    flat2 = flatten_tree(tree2)

    keys1 = set(flat1.keys())
    keys2 = set(flat2.keys())

    added = []
    removed = []
    changed = []
    unchanged = 0

    # 추가된 요소
    for key in keys2 - keys1:
        elem = flat2[key]
        added.append({
            "path": key,
            "Name": elem["Name"],
            "ControlType": elem["ControlType"],
        })

    # 삭제된 요소
    for key in keys1 - keys2:
        elem = flat1[key]
        removed.append({
            "path": key,
            "Name": elem["Name"],
            "ControlType": elem["ControlType"],
        })

    # 변경 확인 (공통 키)
    for key in keys1 & keys2:
        elem1 = flat1[key]
        elem2 = flat2[key]
        if elem1["Name"] != elem2["Name"]:
            changed.append({
                "path": key,
                "old_name": elem1["Name"],
                "new_name": elem2["Name"],
                "ControlType": elem1["ControlType"],
            })
        else:
            unchanged += 1

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
        "summary": {
            "tree1_total": len(flat1),
            "tree2_total": len(flat2),
            "added_count": len(added),
            "removed_count": len(removed),
            "changed_count": len(changed),
        }
    }


def format_tree_diff(diff: dict) -> str:
    """트리 비교 결과를 읽기 쉬운 형식으로 포맷"""
    lines = [
        "# UIA 트리 비교 결과",
        "",
        "## 요약",
        f"- 이전 트리: {diff['summary']['tree1_total']}개 요소",
        f"- 현재 트리: {diff['summary']['tree2_total']}개 요소",
        f"- 추가: {diff['summary']['added_count']}개",
        f"- 삭제: {diff['summary']['removed_count']}개",
        f"- 변경: {diff['summary']['changed_count']}개",
        f"- 유지: {diff['unchanged']}개",
        "",
    ]

    if diff["added"]:
        lines.extend(["## 추가된 요소", ""])
        for item in diff["added"][:20]:  # 최대 20개
            name = item["Name"] or "<EMPTY>"
            lines.append(f"+ [{item['ControlType']}] Name='{name}'")
        if len(diff["added"]) > 20:
            lines.append(f"  ... 외 {len(diff['added']) - 20}개")
        lines.append("")

    if diff["removed"]:
        lines.extend(["## 삭제된 요소", ""])
        for item in diff["removed"][:20]:
            name = item["Name"] or "<EMPTY>"
            lines.append(f"- [{item['ControlType']}] Name='{name}'")
        if len(diff["removed"]) > 20:
            lines.append(f"  ... 외 {len(diff['removed']) - 20}개")
        lines.append("")

    if diff["changed"]:
        lines.extend(["## 변경된 요소", ""])
        for item in diff["changed"][:20]:
            old = item["old_name"] or "<EMPTY>"
            new = item["new_name"] or "<EMPTY>"
            lines.append(f"* [{item['ControlType']}] '{old}' -> '{new}'")
        if len(diff["changed"]) > 20:
            lines.append(f"  ... 외 {len(diff['changed']) - 20}개")
        lines.append("")

    return "\n".join(lines)


def is_focus_in_control(parent_control: auto.Control) -> bool:
    """현재 포커스가 해당 컨트롤의 자손인지 확인

    Args:
        parent_control: 부모 컨트롤 (ListControl 등)

    Returns:
        포커스가 parent_control의 자손이면 True
    """
    if not parent_control:
        return False

    try:
        focused = auto.GetFocusedControl()
        if not focused:
            return False

        # 포커스된 컨트롤이 부모와 같으면 True
        if focused == parent_control:
            return True

        # 부모 체인을 따라 올라가며 확인 (대부분 3~5단계에서 매칭)
        current = focused
        for _ in range(12):  # 20→12로 축소
            parent = current.GetParentControl()
            if not parent:
                break

            if parent == parent_control:
                return True

            current = parent

        return False

    except Exception:
        return False


def is_focus_in_message_list() -> bool:
    """현재 포커스가 메시지 목록(채팅방) 내부인지 확인

    ClassName과 Name 둘 다 확인하여 정확도 향상.
    - ClassName: EVA_VH_ListControl_Dblclk (카카오톡 메시지 목록)
    - Name: 메시지

    Returns:
        메시지 목록 내부이면 True
    """
    try:
        focused = auto.GetFocusedControl()
        if not focused:
            return False

        current = focused
        for _ in range(12):  # 20→12로 축소 (대부분 3~5단계에서 매칭)
            if not current:
                break
            # ClassName AND Name 둘 다 매칭
            if (current.ClassName == "EVA_VH_ListControl_Dblclk"
                    and current.Name == "메시지"):
                return True
            current = current.GetParentControl()

        return False

    except Exception:
        return False
