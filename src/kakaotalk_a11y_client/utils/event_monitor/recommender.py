# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""요소 타입별 권장 이벤트 제안."""

from typing import TYPE_CHECKING

from .types import EventType

if TYPE_CHECKING:
    import uiautomation as auto


# ControlType별 권장 이벤트 매핑
CONTROL_TYPE_RECOMMENDATIONS: dict[str, list[EventType]] = {
    # 목록 관련
    "ListControl": [EventType.STRUCTURE, EventType.FOCUS],
    "ListItemControl": [EventType.FOCUS, EventType.PROPERTY],
    "TreeControl": [EventType.STRUCTURE, EventType.FOCUS],
    "TreeItemControl": [EventType.FOCUS, EventType.PROPERTY],
    "DataGridControl": [EventType.STRUCTURE, EventType.FOCUS],
    "DataItemControl": [EventType.FOCUS, EventType.PROPERTY],

    # 버튼/입력 관련
    "ButtonControl": [EventType.FOCUS],
    "EditControl": [EventType.FOCUS, EventType.PROPERTY],
    "ComboBoxControl": [EventType.FOCUS, EventType.PROPERTY],
    "CheckBoxControl": [EventType.PROPERTY],  # ToggleState
    "RadioButtonControl": [EventType.PROPERTY],  # IsSelected
    "SliderControl": [EventType.PROPERTY],  # RangeValue
    "SpinnerControl": [EventType.PROPERTY],

    # 메뉴 관련
    "MenuControl": [EventType.MENU_OPENED, EventType.MENU_CLOSED],
    "MenuItemControl": [EventType.FOCUS],
    "MenuBarControl": [EventType.FOCUS],

    # 탭/윈도우 관련
    "TabControl": [EventType.FOCUS],
    "TabItemControl": [EventType.FOCUS, EventType.PROPERTY],  # IsSelected
    "WindowControl": [EventType.WINDOW_OPENED, EventType.WINDOW_CLOSED],
    "PaneControl": [EventType.FOCUS],

    # 텍스트 관련
    "TextControl": [EventType.PROPERTY],  # Name 변경
    "DocumentControl": [EventType.PROPERTY],
    "HyperlinkControl": [EventType.FOCUS],

    # 상태 표시
    "ProgressBarControl": [EventType.PROPERTY],  # RangeValue
    "StatusBarControl": [EventType.PROPERTY],
    "ToolTipControl": [EventType.PROPERTY],

    # 기타
    "ScrollBarControl": [EventType.PROPERTY],
    "ThumbControl": [],
    "GroupControl": [EventType.STRUCTURE],
    "ImageControl": [],
    "SeparatorControl": [],
    "HeaderControl": [EventType.STRUCTURE],
    "HeaderItemControl": [EventType.FOCUS],
    "TableControl": [EventType.STRUCTURE],
    "CustomControl": [EventType.FOCUS, EventType.STRUCTURE, EventType.PROPERTY],
}

# 이벤트 타입별 설명
EVENT_TYPE_DESCRIPTIONS: dict[EventType, str] = {
    EventType.FOCUS: "포커스 변경 추적",
    EventType.STRUCTURE: "자식 요소 추가/제거 감지",
    EventType.PROPERTY: "속성 값 변경 감지 (이름, 상태 등)",
    EventType.NOTIFICATION: "중요 알림 감지",
    EventType.WINDOW_OPENED: "새 윈도우 열림 감지",
    EventType.WINDOW_CLOSED: "윈도우 닫힘 감지",
    EventType.MENU_OPENED: "메뉴 열림 감지",
    EventType.MENU_CLOSED: "메뉴 닫힘 감지",
}


def get_recommendations(control_type: str) -> list[EventType]:
    """컨트롤 타입에 대한 권장 이벤트 목록 반환.

    Args:
        control_type: UIA ControlTypeName (예: "ListItemControl")

    Returns:
        권장 EventType 목록
    """
    return CONTROL_TYPE_RECOMMENDATIONS.get(control_type, [EventType.FOCUS])


def get_recommendations_for_control(control: "auto.Control") -> list[EventType]:
    """컨트롤 객체에 대한 권장 이벤트 목록 반환.

    Args:
        control: uiautomation Control 객체

    Returns:
        권장 EventType 목록
    """
    control_type = control.ControlTypeName or ""
    return get_recommendations(control_type)


def format_recommendations(control_type: str) -> str:
    """컨트롤 타입에 대한 권장 이벤트를 포맷팅된 문자열로 반환.

    Args:
        control_type: UIA ControlTypeName

    Returns:
        포맷팅된 권장 이벤트 문자열
    """
    recommendations = get_recommendations(control_type)

    if not recommendations:
        return f"[SUGGEST] {control_type}: 권장 이벤트 없음"

    lines = [f"[SUGGEST] {control_type}:"]
    for event_type in recommendations:
        desc = EVENT_TYPE_DESCRIPTIONS.get(event_type, "")
        lines.append(f"  - {event_type.name}: {desc}")

    return "\n".join(lines)


def print_recommendations(control_type: str) -> None:
    """권장 이벤트를 콘솔에 출력."""
    print(format_recommendations(control_type))


def print_recommendations_for_control(control: "auto.Control") -> None:
    """컨트롤 객체의 권장 이벤트를 콘솔에 출력."""
    control_type = control.ControlTypeName or "Unknown"
    name = control.Name or "(이름 없음)"
    class_name = control.ClassName or ""

    print(f"[SUGGEST] 현재 요소: {control_type} - {name} ({class_name})")

    recommendations = get_recommendations(control_type)
    if not recommendations:
        print("  권장 이벤트 없음")
        return

    print("  권장 이벤트:")
    for event_type in recommendations:
        desc = EVENT_TYPE_DESCRIPTIONS.get(event_type, "")
        print(f"  - {event_type.name}: {desc}")
