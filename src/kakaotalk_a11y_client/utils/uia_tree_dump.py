# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""UIA 트리 덤프/비교. 디버깅용 유틸리티."""

from typing import Callable, Optional

import uiautomation as auto


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
    """UIA 트리를 문자열로 덤프. 디버깅용."""
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
    """요소의 모든 속성 상세 덤프. LegacyIAccessible, Value, Text 패턴 포함."""
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


def compare_trees(tree1: dict, tree2: dict) -> dict:
    """두 JSON 트리 비교. added/removed/changed/unchanged 반환."""
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
    """compare_trees 결과를 마크다운으로 포맷."""
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
