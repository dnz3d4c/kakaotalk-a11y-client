"""UIA 덤프 통합 도구

사용법:
    uv run python scripts/dump_uia.py chat_list  # 채팅 목록 덤프
    uv run python scripts/dump_uia.py menu       # 메뉴 덤프 (7초 대기)
    uv run python scripts/dump_uia.py focus      # 현재 포커스 덤프
    uv run python scripts/dump_uia.py snapshot   # 현재 트리 JSON 스냅샷 저장
    uv run python scripts/dump_uia.py compare <file1> <file2>  # 두 스냅샷 비교
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import uiautomation as auto
import pythoncom

sys.path.insert(0, str(__file__).rsplit('scripts', 1)[0] + 'src')
from kakaotalk_a11y_client.utils.uia_utils import (
    dump_tree, dump_tree_json, compare_trees, format_tree_diff
)


def dump_chat_list():
    """채팅 목록 덤프"""
    print("3초 후 채팅 목록 덤프... 카카오톡 채팅 탭 열어두세요!")
    time.sleep(3)

    root = auto.GetRootControl()
    filename = f"chat_list_dump_{datetime.now().strftime('%H%M%S')}.txt"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"채팅 목록 덤프 - {datetime.now()}\n")
        f.write("=" * 60 + "\n\n")

        f.write("== 최상위 창들 ==\n")
        for win in root.GetChildren():
            wname = win.Name or ''
            wcls = win.ClassName or ''
            f.write(f"  {wname[:30]} | {wcls}\n")
        f.write("\n")

        for win in root.GetChildren():
            name = win.Name or ''
            cls = win.ClassName or ''

            if 'EVA' in cls or '카카오톡' in name:
                f.write(f"== 카카오톡 창: {name} ==\n\n")

                chat_list = win.ListControl(Name="채팅", searchDepth=6)
                if chat_list.Exists(maxSearchSeconds=1):
                    f.write("== 채팅 목록 (ListControl Name='채팅') ==\n\n")

                    children = chat_list.GetChildren()
                    f.write(f"총 {len(children)}개 항목\n\n")

                    for i, child in enumerate(children[:30]):
                        cname = child.Name or "(빈 이름)"
                        ctype = child.ControlTypeName
                        ccls = child.ClassName or ""

                        expand_state = ""
                        try:
                            pattern = child.GetExpandCollapsePattern()
                            if pattern:
                                state = pattern.ExpandCollapseState
                                expand_state = f" [Expand={state}]"
                        except:
                            pass

                        f.write(f"{i + 1}. [{ctype}] \"{cname[:80]}\" Class={ccls}{expand_state}\n")

                        try:
                            sub = child.GetChildren()
                            if sub:
                                f.write(f"   -> 자식 {len(sub)}개\n")
                        except:
                            pass

                    f.write("\n")
                else:
                    f.write("채팅 목록 못 찾음\n")

    print(f"저장됨: {filename}")


def dump_menu():
    """메뉴 덤프"""
    print("4초 후 메뉴 덤프... 카카오톡에서 메뉴 열어두세요!")
    time.sleep(4)
    print("메뉴/팝업 검색 중...")

    root = auto.GetRootControl()
    focused = auto.GetFocusedControl()

    if focused:
        print(f"포커스: [{focused.ControlTypeName}] {focused.Name[:50] if focused.Name else ''}")

    filename = f"menu_dump_{datetime.now().strftime('%H%M%S')}.txt"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"메뉴 덤프 - {datetime.now()}\n")
        f.write("=" * 60 + "\n\n")

        if focused:
            f.write("== 포커스된 요소 ==\n")
            f.write(f"[{focused.ControlTypeName}] {focused.Name}\n")
            f.write(f"Class: {focused.ClassName}\n\n")

            f.write("== 부모 체인 ==\n")
            parent = focused
            menu_control = None
            for i in range(10):
                parent = parent.GetParentControl()
                if not parent:
                    break
                f.write(f"{i + 1}. [{parent.ControlTypeName}] {parent.Name[:50] if parent.Name else ''} Class={parent.ClassName}\n")
                if parent.ControlTypeName == "MenuControl":
                    menu_control = parent
            f.write("\n")

            if menu_control:
                f.write("== 메뉴 항목 전체 ==\n")
                dump_tree(menu_control, max_depth=5, indent=0, file=f, print_output=True)
                f.write("\n")

        f.write("== 최상위 창들 ==\n")
        for win in root.GetChildren():
            name = win.Name or ''
            cls = win.ClassName or ''
            ctype = win.ControlTypeName

            if 'Menu' in ctype or 'Menu' in cls or 'EVA' in cls or 'Popup' in cls.lower():
                f.write(f"\n[{ctype}] \"{name}\" Class={cls}\n")
                dump_tree(win, max_depth=5, indent=1, file=f, print_output=True)

    print(f"저장됨: {filename}")


def dump_focus():
    """현재 포커스 덤프 (3초 대기)"""
    print("3초 후 포커스 덤프...")
    time.sleep(3)

    focused = auto.GetFocusedControl()

    if not focused:
        print("포커스된 요소 없음")
        return

    print(f"\n=== 포커스된 요소 ===")
    print(f"Type: {focused.ControlTypeName}")
    print(f"Name: {focused.Name}")
    print(f"Class: {focused.ClassName}")
    print(f"AutomationId: {focused.AutomationId}")

    print(f"\n=== 부모 체인 ===")
    parent = focused
    for i in range(5):
        parent = parent.GetParentControl()
        if not parent:
            break
        print(f"{i + 1}. [{parent.ControlTypeName}] {parent.Name[:40] if parent.Name else ''}")


def dump_snapshot():
    """현재 카카오톡 트리를 JSON으로 스냅샷 저장"""
    print("3초 후 카카오톡 트리 스냅샷 저장...")
    time.sleep(3)

    root = auto.GetRootControl()
    kakao_window = None

    # 카카오톡 창 찾기
    for win in root.GetChildren():
        name = win.Name or ''
        cls = win.ClassName or ''
        if 'EVA' in cls or '카카오톡' in name:
            kakao_window = win
            break

    if not kakao_window:
        print("카카오톡 창을 찾을 수 없습니다.")
        return

    print(f"찾은 창: {kakao_window.Name}")
    print("트리 덤프 중... (시간이 걸릴 수 있음)")

    tree = dump_tree_json(kakao_window, max_depth=6, include_coords=True)

    filename = f"uia_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)

    print(f"저장됨: {filename}")
    print("나중에 'compare' 명령으로 두 스냅샷을 비교할 수 있습니다.")


def compare_snapshots(file1: str, file2: str):
    """두 스냅샷 JSON 파일 비교"""
    path1 = Path(file1)
    path2 = Path(file2)

    if not path1.exists():
        print(f"파일 없음: {path1}")
        return
    if not path2.exists():
        print(f"파일 없음: {path2}")
        return

    print(f"비교: {path1.name} vs {path2.name}")

    with open(path1, 'r', encoding='utf-8') as f:
        tree1 = json.load(f)
    with open(path2, 'r', encoding='utf-8') as f:
        tree2 = json.load(f)

    diff = compare_trees(tree1, tree2)
    report = format_tree_diff(diff)

    print(report)

    # 결과 파일로도 저장
    output_file = f"tree_diff_{datetime.now().strftime('%H%M%S')}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n결과 저장됨: {output_file}")


def main():
    pythoncom.CoInitialize()

    if len(sys.argv) < 2:
        print(__doc__)
        print("사용 가능한 명령: chat_list, menu, focus, snapshot, compare")
        return

    command = sys.argv[1].lower()

    if command == 'chat_list':
        dump_chat_list()
    elif command == 'menu':
        dump_menu()
    elif command == 'focus':
        dump_focus()
    elif command == 'snapshot':
        dump_snapshot()
    elif command == 'compare':
        if len(sys.argv) < 4:
            print("사용법: dump_uia.py compare <file1.json> <file2.json>")
            return
        compare_snapshots(sys.argv[2], sys.argv[3])
    else:
        print(f"알 수 없는 명령: {command}")
        print("사용 가능한 명령: chat_list, menu, focus, snapshot, compare")


if __name__ == "__main__":
    main()
