"""컨텍스트 메뉴 덤프 스크립트

사용법:
1. 카카오톡에서 메시지 우클릭으로 메뉴 열기
2. 메뉴가 열린 상태에서 이 스크립트 실행:
   uv run python scripts/dump_menu.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import uiautomation as auto


def dump_control(control, depth=0, max_depth=5):
    """컨트롤을 딕셔너리로 변환"""
    if depth > max_depth:
        return None

    try:
        rect = control.BoundingRectangle
        result = {
            "ControlType": control.ControlTypeName,
            "Name": control.Name or "",
            "ClassName": control.ClassName or "",
            "AutomationId": control.AutomationId or "",
            "BoundingRectangle": {
                "left": rect.left if rect else 0,
                "top": rect.top if rect else 0,
                "right": rect.right if rect else 0,
                "bottom": rect.bottom if rect else 0,
            } if rect else None,
        }

        # 자식 요소
        children = []
        for child in control.GetChildren():
            child_data = dump_control(child, depth + 1, max_depth)
            if child_data:
                children.append(child_data)

        if children:
            result["Children"] = children

        return result
    except Exception as e:
        return {"error": str(e)}


def find_menus():
    """데스크톱에서 메뉴 찾기"""
    root = auto.GetRootControl()
    menus = []

    # 방법 1: EVA_Menu 클래스 검색
    print("EVA_Menu 검색 중...")
    try:
        for win in root.GetChildren():
            cls = win.ClassName or ""
            name = win.Name or ""

            # EVA_Menu 직접 확인
            if cls == "EVA_Menu":
                print(f"  발견: {cls} - {name}")
                menus.append(("EVA_Menu_direct", win))

            # 카카오톡 창 내부 검색
            if "EVA_" in cls or "카카오톡" in name:
                try:
                    menu = win.MenuControl(searchDepth=5)
                    if menu.Exists(maxSearchSeconds=0.1):
                        print(f"  발견: MenuControl in {cls}")
                        menus.append((f"MenuInWindow_{cls}", menu))
                except:
                    pass
    except Exception as e:
        print(f"  오류: {e}")

    # 방법 2: MenuControl 검색
    print("MenuControl 검색 중...")
    try:
        menu = root.MenuControl(searchDepth=10)
        if menu.Exists(maxSearchSeconds=0.3):
            print(f"  발견: {menu.ClassName} - {menu.Name}")
            menus.append(("MenuControl_root", menu))
    except Exception as e:
        print(f"  오류: {e}")

    # 방법 3: 포커스된 요소 확인
    print("포커스된 요소 확인 중...")
    try:
        focused = auto.GetFocusedControl()
        if focused:
            print(f"  포커스: {focused.ControlTypeName} - {focused.Name} - {focused.ClassName}")
            if focused.ControlTypeName == "MenuItemControl":
                # 부모 메뉴 찾기
                parent = focused.GetParentControl()
                for _ in range(5):
                    if parent and parent.ControlTypeName == "MenuControl":
                        print(f"  부모 메뉴: {parent.ClassName} - {parent.Name}")
                        menus.append(("FocusedParent", parent))
                        break
                    if parent:
                        parent = parent.GetParentControl()
    except Exception as e:
        print(f"  오류: {e}")

    return menus


def main():
    print("=" * 50)
    print("컨텍스트 메뉴 덤프 도구")
    print("=" * 50)
    print()

    menus = find_menus()

    if not menus:
        print("메뉴를 찾을 수 없습니다.")
        print("카카오톡에서 메시지 우클릭 후 메뉴가 열린 상태에서 실행하세요.")
        return 1

    # 출력 디렉토리
    output_dir = Path.home() / ".kakaotalk_a11y" / "debug"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%H%M%S")

    for name, menu in menus:
        print(f"\n덤프 중: {name}")
        data = dump_control(menu, max_depth=5)

        filename = f"menu_{name}_{timestamp}.json"
        filepath = output_dir / filename

        filepath.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"  저장: {filepath}")

    print(f"\n완료. 덤프 위치: {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
