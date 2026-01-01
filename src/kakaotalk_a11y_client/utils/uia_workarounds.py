# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""카카오톡 UIA Workaround (NVDA 패턴)

NVDA 스타일로 앱별 특이점 및 우회 방법을 문서화.
이슈 번호 형식: #KAKAO-NNN

참고: docs/KAKAO_UIA_QUIRKS.md
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import uiautomation as auto

from .debug import get_logger

log = get_logger("UIA_Workaround")


@dataclass
class Workaround:
    """Workaround 정의"""
    id: str  # KAKAO-001 형식
    description: str
    affected_class: Optional[str] = None
    affected_function: Optional[str] = None
    solution: str = ""
    notes: str = ""


# =============================================================================
# 카카오톡 Workaround 목록
# =============================================================================

WORKAROUNDS: Dict[str, Workaround] = {
    "KAKAO-001": Workaround(
        id="KAKAO-001",
        description="빈 ListItem 대량 발생",
        affected_class="EVA_VH_ListControl_Dblclk",
        solution="SmartListFilter로 빈 항목 필터링",
        notes="가상 스크롤로 인해 화면 밖 항목은 빈 Name 반환. "
              "연속 빈 항목 15개 발견 시 조기 종료."
    ),
    "KAKAO-002": Workaround(
        id="KAKAO-002",
        description="메뉴 항목 UIA Name 없음",
        affected_class="EVA_Menu",
        solution="하드코딩된 CHATROOM_MESSAGE_MENU_ITEMS 사용",
        notes="채팅방 컨텍스트 메뉴는 UIA Name이 비어있음. "
              "MSAA LegacyIAccessible.Name은 존재하나 불안정."
    ),
    "KAKAO-003": Workaround(
        id="KAKAO-003",
        description="메뉴 팝업 지연",
        affected_function="_find_popup_menu",
        solution="적응형 재시도 (150ms 시작, 최대 7회)",
        notes="우클릭 후 EVA_Menu가 UIA에 즉시 노출되지 않음. "
              "지수 백오프로 재시도."
    ),
    "KAKAO-004": Workaround(
        id="KAKAO-004",
        description="Chromium 광고 영역 UIA 불안정",
        affected_class="Chrome_WidgetWin_*",
        solution="KAKAO_BAD_UIA_CLASSES에 등록, 탐색 제외",
        notes="카카오톡 내부 광고/웹뷰 영역. "
              "UIA 접근 시 지연 또는 COMError 발생 가능."
    ),
    "KAKAO-005": Workaround(
        id="KAKAO-005",
        description="AutomationId 불규칙",
        affected_class="*",
        solution="AutomationId 의존 최소화, Name+ControlType 조합 사용",
        notes="숫자만, 내용 복제, 빈값 등 혼재. "
              "신뢰성 낮음."
    ),
    "KAKAO-006": Workaround(
        id="KAKAO-006",
        description="ClassName 대부분 없음",
        affected_class="*",
        solution="Name + ControlType 조합으로 검색",
        notes="대다수 컨트롤 ClassName 미지정. "
              "EVA_* 클래스만 신뢰 가능."
    ),
}


def get_workaround(workaround_id: str) -> Optional[Workaround]:
    """Workaround 정보 가져오기"""
    return WORKAROUNDS.get(workaround_id)


def list_workarounds() -> List[Workaround]:
    """모든 Workaround 목록"""
    return list(WORKAROUNDS.values())


def log_workaround(workaround_id: str, context: str = "") -> None:
    """Workaround 적용 로깅

    Args:
        workaround_id: Workaround ID (예: KAKAO-001)
        context: 추가 컨텍스트 정보
    """
    wa = WORKAROUNDS.get(workaround_id)
    if wa:
        msg = f"#{workaround_id}: {wa.description}"
        if context:
            msg += f" ({context})"
        log.debug(msg)


# =============================================================================
# UIA/MSAA 선택 함수
# =============================================================================

def should_use_msaa(class_name: str) -> bool:
    """UIA 대신 MSAA 사용해야 하는지 판단

    NVDA의 badUIAWindowClassNames 패턴.

    Args:
        class_name: 윈도우 클래스명

    Returns:
        True면 MSAA 사용 권장
    """
    # 카카오톡은 대부분 UIA 지원
    # 메뉴 항목 이름만 MSAA(LegacyIAccessible) 필요
    msaa_preferred = [
        "EVA_Menu",  # KAKAO-002: 메뉴 항목 Name
    ]
    return class_name in msaa_preferred


def should_skip_element(control: auto.Control) -> bool:
    """이 요소를 탐색에서 제외해야 하는지 판단

    Args:
        control: UIA 컨트롤

    Returns:
        True면 제외
    """
    try:
        class_name = control.ClassName or ""

        # Chromium 영역 제외 (KAKAO-004)
        if class_name.startswith("Chrome_"):
            log_workaround("KAKAO-004", f"class={class_name}")
            return True

        # 빈 ListItem 제외 (KAKAO-001)
        if control.ControlTypeName == "ListItemControl":
            name = control.Name
            if not name or not name.strip():
                return True

        return False

    except Exception:
        return True  # 에러 발생 시 안전하게 제외


def get_element_name(control: auto.Control) -> str:
    """요소 이름 가져오기 (Workaround 적용)

    MSAA가 필요한 경우 LegacyIAccessible.Name 사용.

    Args:
        control: UIA 컨트롤

    Returns:
        요소 이름
    """
    try:
        class_name = control.ClassName or ""

        # MSAA 사용 권장 클래스
        if should_use_msaa(class_name):
            log_workaround("KAKAO-002", f"class={class_name}")
            try:
                legacy = control.GetLegacyIAccessiblePattern()
                if legacy and legacy.Name:
                    return legacy.Name
            except Exception:
                pass

        # 기본: UIA Name
        return control.Name or ""

    except Exception:
        return ""
