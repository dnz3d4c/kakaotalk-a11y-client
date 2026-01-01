"""UIA 이벤트 테스트 스크립트

목적: 카카오톡에서 어떤 UIA 이벤트가 발생하는지 확인
- comtypes로 실제 이벤트 핸들러 등록
- StructureChanged, PropertyChanged, FocusChanged 테스트
- 어떤 이벤트가 메시지 감지에 사용 가능한지 확인

사용법:
1. 카카오톡 채팅방 열기
2. uv run python scripts/test_uia_events.py
3. 다른 기기에서 메시지 전송
4. 콘솔에서 발생하는 이벤트 확인
5. Ctrl+C로 종료
"""

import sys
import time
from datetime import datetime
from pathlib import Path

# 프로젝트 소스 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import uiautomation as auto
import pythoncom

# comtypes 이벤트 핸들러용
try:
    from comtypes import COMObject
    from comtypes.client import CreateObject, GetModule

    # UIA COM 인터페이스 로드
    GetModule("UIAutomationCore.dll")
    from comtypes.gen.UIAutomationClient import (
        CUIAutomation,
        IUIAutomationStructureChangedEventHandler,
        IUIAutomationPropertyChangedEventHandler,
        IUIAutomationFocusChangedEventHandler,
        TreeScope_Subtree,
        TreeScope_Element,
    )
    HAS_COMTYPES = True
    print("[OK] comtypes UIA 모듈 로드 성공")
except Exception as e:
    print(f"[ERROR] comtypes 로드 실패: {e}")
    HAS_COMTYPES = False

# 이벤트 카운터
event_counts = {
    'StructureChanged': 0,
    'PropertyChanged': 0,
    'FocusChanged': 0,
    'Polling': 0,
}


# 로그 파일
log_file = None


def init_log_file():
    """로그 파일 초기화"""
    global log_file
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_path = logs_dir / f"uia_event_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file = open(log_path, "w", encoding="utf-8")
    print(f"[INFO] 로그 파일: {log_path}")
    return log_path


def log_event(event_type: str, details: str = ""):
    """이벤트 로그 출력 (콘솔 + 파일)"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    event_counts[event_type] = event_counts.get(event_type, 0) + 1
    count = event_counts[event_type]
    line = f"[{timestamp}] [{event_type}] #{count} {details}"
    print(line)
    if log_file:
        log_file.write(line + "\n")
        log_file.flush()


# =============================================================================
# comtypes 이벤트 핸들러 클래스들
# =============================================================================

if HAS_COMTYPES:

    class StructureChangedHandler(COMObject):
        """StructureChanged 이벤트 핸들러"""
        _com_interfaces_ = [IUIAutomationStructureChangedEventHandler]

        def HandleStructureChangedEvent(self, sender, changeType, runtimeId):
            """구조 변경 이벤트 처리

            changeType:
                0 = ChildAdded
                1 = ChildRemoved
                2 = ChildrenInvalidated
                3 = ChildrenBulkAdded
                4 = ChildrenBulkRemoved
                5 = ChildrenReordered
            """
            change_names = {
                0: "ChildAdded",
                1: "ChildRemoved",
                2: "ChildrenInvalidated",
                3: "ChildrenBulkAdded",
                4: "ChildrenBulkRemoved",
                5: "ChildrenReordered",
            }
            change_name = change_names.get(changeType, f"Unknown({changeType})")
            log_event("StructureChanged", f"type={change_name}")


    class PropertyChangedHandler(COMObject):
        """PropertyChanged 이벤트 핸들러"""
        _com_interfaces_ = [IUIAutomationPropertyChangedEventHandler]

        def HandlePropertyChangedEvent(self, sender, propertyId, newValue):
            """속성 변경 이벤트 처리

            주요 propertyId:
                30005 = Name
                30045 = ItemStatus
                30043 = IsOffscreen
            """
            prop_names = {
                30005: "Name",
                30045: "ItemStatus",
                30043: "IsOffscreen",
                30010: "IsEnabled",
            }
            prop_name = prop_names.get(propertyId, f"Property({propertyId})")
            value_str = str(newValue)[:50]
            log_event("PropertyChanged", f"{prop_name} = {value_str}")


    class FocusChangedHandler(COMObject):
        """FocusChanged 이벤트 핸들러"""
        _com_interfaces_ = [IUIAutomationFocusChangedEventHandler]

        def HandleFocusChangedEvent(self, sender):
            """포커스 변경 이벤트 처리"""
            try:
                name = sender.CurrentName if sender else "(없음)"
                log_event("FocusChanged", f"element={name[:40]}")
            except Exception:
                log_event("FocusChanged", "element=(error)")


def find_chat_room_window():
    """열려있는 채팅방 창 찾기"""
    # 방법 1: EVA_Window_Dblclk 클래스로 찾기
    chat_window = auto.WindowControl(
        RegexName=r".*",
        ClassName="EVA_Window_Dblclk"
    )

    if chat_window.Exists(maxSearchSeconds=2):
        return chat_window

    # 방법 2: 이름 패턴으로 찾기
    root = auto.GetRootControl()
    for win in root.GetChildren():
        cls = win.ClassName or ''
        if 'EVA_Window' in cls:
            return win

    return None


def register_event_handlers(chat_win, msg_list):
    """이벤트 핸들러 등록"""
    if not HAS_COMTYPES:
        print("[ERROR] comtypes를 사용할 수 없습니다.")
        return None, []

    handlers = []

    try:
        # UIA 클라이언트 생성
        uia = CreateObject(CUIAutomation)

        # 채팅방 창의 IUIAutomationElement
        hwnd = chat_win.NativeWindowHandle
        if not hwnd:
            print("[ERROR] 창 핸들을 가져올 수 없습니다.")
            return None, []

        root_element = uia.ElementFromHandle(hwnd)
        print(f"[OK] 루트 요소: {root_element.CurrentName}")

        # 메시지 목록 요소 찾기
        # Name="메시지"인 List 컨트롤
        name_condition = uia.CreatePropertyCondition(30005, "메시지")  # UIA_NamePropertyId
        msg_element = root_element.FindFirst(TreeScope_Subtree, name_condition)

        if msg_element:
            print(f"[OK] 메시지 목록 요소: {msg_element.CurrentName}")
        else:
            print("[WARN] 메시지 목록 요소를 찾을 수 없음, 루트 요소 사용")
            msg_element = root_element

        # 1. StructureChanged 이벤트
        print("[INFO] StructureChanged 이벤트 등록 시도...")
        try:
            struct_handler = StructureChangedHandler()
            uia.AddStructureChangedEventHandler(
                msg_element,
                TreeScope_Subtree,
                None,
                struct_handler
            )
            handlers.append(("StructureChanged", struct_handler))
            print("[OK] StructureChanged 이벤트 등록 성공")
        except Exception as e:
            print(f"[FAIL] StructureChanged 등록 실패: {e}")

        # 2. PropertyChanged 이벤트
        print("[INFO] PropertyChanged 이벤트 등록 시도...")
        try:
            prop_handler = PropertyChangedHandler()
            # Name(30005), ItemStatus(30045) 감시
            prop_ids = (30005, 30045)
            uia.AddPropertyChangedEventHandler(
                msg_element,
                TreeScope_Subtree,
                None,
                prop_handler,
                prop_ids
            )
            handlers.append(("PropertyChanged", prop_handler))
            print("[OK] PropertyChanged 이벤트 등록 성공")
        except Exception as e:
            print(f"[FAIL] PropertyChanged 등록 실패: {e}")

        # 3. FocusChanged 이벤트 (전역)
        print("[INFO] FocusChanged 이벤트 등록 시도...")
        try:
            focus_handler = FocusChangedHandler()
            uia.AddFocusChangedEventHandler(None, focus_handler)
            handlers.append(("FocusChanged", focus_handler))
            print("[OK] FocusChanged 이벤트 등록 성공")
        except Exception as e:
            print(f"[FAIL] FocusChanged 등록 실패: {e}")

        print(f"[INFO] 총 {len(handlers)}개 이벤트 핸들러 등록됨")
        return uia, handlers

    except Exception as e:
        print(f"[ERROR] 이벤트 등록 오류: {e}")
        import traceback
        traceback.print_exc()
        return None, []


def main():
    pythoncom.CoInitialize()

    print("=" * 60)
    print("UIA 이벤트 테스트 (comtypes)")
    print("=" * 60)
    print()

    # 로그 파일 초기화
    log_path = init_log_file()
    log_file.write("=" * 60 + "\n")
    log_file.write("UIA 이벤트 테스트\n")
    log_file.write(f"시작: {datetime.now().isoformat()}\n")
    log_file.write("=" * 60 + "\n\n")

    # 채팅방 찾기
    print("[INFO] 카카오톡 채팅방 찾는 중...")
    chat_win = find_chat_room_window()

    if not chat_win:
        print("[ERROR] 채팅방을 찾을 수 없습니다.")
        print("        카카오톡 채팅방을 먼저 열어주세요.")
        pythoncom.CoUninitialize()
        return

    print(f"[OK] 채팅방: {chat_win.Name}")

    # 메시지 목록 찾기
    msg_list = chat_win.ListControl(Name="메시지", searchDepth=10)
    if not msg_list.Exists(maxSearchSeconds=2):
        print("[ERROR] 메시지 목록을 찾을 수 없습니다.")
        pythoncom.CoUninitialize()
        return

    children = msg_list.GetChildren()
    initial_count = len(children) if children else 0
    print(f"[OK] 메시지 목록: {msg_list.Name} (현재 {initial_count}개)")
    print()

    # 이벤트 핸들러 등록
    uia, handlers = register_event_handlers(chat_win, msg_list)

    if not handlers:
        print("[WARN] 등록된 이벤트 핸들러 없음, 폴링만 테스트")

    print()
    print("=" * 60)
    print("이벤트 모니터링 + 폴링 비교 테스트 시작")
    print("메시지를 수신하면 이벤트가 표시됩니다.")
    print("종료하려면 Ctrl+C를 누르세요.")
    print("=" * 60)
    print()

    # 폴링 비교용 변수
    last_count = initial_count
    start_time = time.time()

    try:
        while True:
            # COM 메시지 펌프 (이벤트 수신용)
            pythoncom.PumpWaitingMessages()

            # 폴링으로도 변화 감지 (비교용)
            try:
                children = msg_list.GetChildren()
                current_count = len(children) if children else 0

                if current_count != last_count:
                    diff = current_count - last_count
                    log_event("Polling", f"count: {last_count} -> {current_count} ({diff:+d})")
                    last_count = current_count

            except Exception:
                pass

            time.sleep(0.5)  # 500ms 간격

    except KeyboardInterrupt:
        print()
        print("[INFO] 종료 요청됨")

    # 결과 요약
    elapsed = int(time.time() - start_time)
    print()
    print("=" * 60)
    print(f"테스트 결과 (총 {elapsed}초)")
    print("=" * 60)

    # 파일에도 결과 저장
    log_file.write("\n" + "=" * 60 + "\n")
    log_file.write(f"테스트 결과 (총 {elapsed}초)\n")
    log_file.write("=" * 60 + "\n\n")

    for event_type, count in event_counts.items():
        status = "발생" if count > 0 else "미발생"
        line = f"  {event_type}: {count}회 ({status})"
        print(line)
        log_file.write(line + "\n")

    print()
    log_file.write("\n")

    # 결론
    if event_counts.get("StructureChanged", 0) > 0:
        conclusion = "[결론] StructureChanged 이벤트 사용 가능!"
    elif event_counts.get("PropertyChanged", 0) > 0:
        conclusion = "[결론] PropertyChanged 이벤트 사용 가능!"
    elif event_counts.get("Polling", 0) > 0:
        conclusion = "[결론] 이벤트 미발생, 폴링 방식 유지 필요"
    else:
        conclusion = "[결론] 변화 없음 (메시지 수신 확인 필요)"

    print(conclusion)
    log_file.write(conclusion + "\n")

    # 파일 닫기
    log_file.write(f"\n종료: {datetime.now().isoformat()}\n")
    log_file.close()
    print()
    print(f"[INFO] 결과 저장됨: {log_path}")

    pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
