# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""UIA 트리 JSON 덤프. 디버깅용 유틸리티."""

from typing import Callable, Optional

import uiautomation as auto


def dump_tree_json(
    element: auto.Control,
    max_depth: int = 5,
    current_depth: int = 0,
    include_coords: bool = False,
    filter_fn: Optional[Callable[[auto.Control], bool]] = None
) -> Optional[dict]:
    """UIA 트리를 JSON 형식으로 덤프."""
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
