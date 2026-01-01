"""친구/채팅탭 메뉴 시뮬레이션 테스트

카카오톡 채팅 탭에서 첫 번째 항목을 우클릭하고 메뉴 정보를 덤프
"""
import sys
import time
sys.path.insert(0, str(__file__).rsplit('scripts', 1)[0] + 'src')

import uiautomation as auto
import pythoncom

pythoncom.CoInitialize()

print("=== 친구/채팅탭 메뉴 시뮬레이션 ===")
print("3초 후 실행... 카카오톡 채팅 탭을 열어두세요!")
time.sleep(3)

# 1. 카카오톡 창 찾기
root = auto.GetRootControl()
kakao_win = None
for win in root.GetChildren():
    name = win.Name or ''
    cls = win.ClassName or ''
    if 'EVA' in cls or '카카오톡' in name or 'KakaoTalk' in name:
        kakao_win = win
        print(f"카카오톡 창 발견: {name} ({cls})")
        break

if not kakao_win:
    print("카카오톡 창을 찾을 수 없습니다")
    sys.exit(1)

# 2. 채팅 목록에서 첫 번째 항목 찾기
print("\n채팅 목록 검색 중...")
chat_list = kakao_win.ListControl(Name="채팅", searchDepth=6)
if not chat_list.Exists(maxSearchSeconds=2):
    print("채팅 목록을 찾을 수 없습니다. 친구 목록 시도...")
    chat_list = kakao_win.ListControl(Name="친구목록", searchDepth=6)
    if not chat_list.Exists(maxSearchSeconds=2):
        print("목록을 찾을 수 없습니다")
        sys.exit(1)

print(f"목록 발견: {chat_list.Name}")

# 첫 번째 ListItem 찾기
children = chat_list.GetChildren()
first_item = None
for child in children:
    if child.ControlTypeName == 'ListItemControl' and child.Name:
        first_item = child
        break

if not first_item:
    print("ListItem을 찾을 수 없습니다")
    sys.exit(1)

print(f"첫 번째 항목: {first_item.Name[:50] if first_item.Name else 'None'}")

# 3. 우클릭 시뮬레이션
rect = first_item.BoundingRectangle
if rect:
    center_x = (rect.left + rect.right) // 2
    center_y = (rect.top + rect.bottom) // 2
    print(f"\n우클릭 위치: ({center_x}, {center_y})")

    auto.RightClick(center_x, center_y)
    time.sleep(0.5)  # 메뉴 열릴 때까지 대기

    # 4. 메뉴 검색
    print("\n=== 메뉴 검색 ===")

    # 방법 1: 포커스된 요소 확인
    focused = auto.GetFocusedControl()
    if focused:
        print(f"포커스: [{focused.ControlTypeName}] {focused.Name} (Class={focused.ClassName})")

        # 부모 확인
        parent = focused.GetParentControl()
        if parent:
            print(f"  부모: [{parent.ControlTypeName}] {parent.Name} (Class={parent.ClassName})")

    # 방법 2: MenuControl 검색
    print("\n=== MenuControl 검색 ===")
    for win in root.GetChildren():
        cls = win.ClassName or ""
        name = win.Name or ""
        if 'Menu' in cls or 'EVA_' in cls:
            print(f"  창: {name} (Class={cls})")
            # 자식 덤프
            try:
                children = win.GetChildren()
                for i, child in enumerate(children[:10]):
                    cname = child.Name or ""
                    ctype = child.ControlTypeName
                    ccls = child.ClassName or ""
                    print(f"    {i}: [{ctype}] {cname[:30]} (Class={ccls})")
            except:
                pass

    # 방법 3: EVA_Menu 직접 검색
    print("\n=== EVA_Menu 검색 ===")
    menu = root.MenuControl(searchDepth=10, ClassName='EVA_Menu')
    if menu.Exists(maxSearchSeconds=0.5):
        print(f"EVA_Menu 발견: {menu.Name} (Handle={menu.NativeWindowHandle})")
        children = menu.GetChildren()
        print(f"  자식 {len(children)}개:")
        for i, child in enumerate(children[:15]):
            cname = child.Name or ""
            ctype = child.ControlTypeName
            aid = child.AutomationId or ""
            print(f"    {i}: [{ctype}] Name={cname}, AutomationId={aid}")
    else:
        print("EVA_Menu 못 찾음")

    # 방법 4: 일반 MenuControl 검색
    print("\n=== 일반 MenuControl 검색 ===")
    menu = root.MenuControl(searchDepth=10)
    if menu.Exists(maxSearchSeconds=0.5):
        print(f"MenuControl 발견: {menu.Name} (Class={menu.ClassName}, Handle={menu.NativeWindowHandle})")
        children = menu.GetChildren()
        print(f"  자식 {len(children)}개:")
        for i, child in enumerate(children[:15]):
            cname = child.Name or ""
            ctype = child.ControlTypeName
            aid = child.AutomationId or ""
            print(f"    {i}: [{ctype}] Name={cname}, AutomationId={aid}")
    else:
        print("MenuControl 못 찾음")

    # ESC로 메뉴 닫기
    print("\nESC로 메뉴 닫기...")
    import keyboard
    keyboard.send('escape')
else:
    print("BoundingRectangle 없음")

print("\n완료!")
