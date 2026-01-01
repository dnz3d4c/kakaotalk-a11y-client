"""메시지 변화 감지 테스트 스크립트

목적: 폴링 기반 새 메시지 감지 가능 여부 확인
- 채팅방 창에서 메시지 목록 가져오기
- 500ms 간격으로 폴링하며 변화 감지
- 새 메시지 발견 시 콘솔 출력

사용법:
1. 카카오톡 채팅방 열기
2. 스크립트 실행
3. Ctrl+C로 종료
"""

import sys
import time
from datetime import datetime

# 프로젝트 소스 경로 추가
sys.path.insert(0, str(__file__).rsplit('scripts', 1)[0] + 'src')

import uiautomation as auto
import pythoncom

from kakaotalk_a11y_client.utils.uia_utils import get_children_recursive
from kakaotalk_a11y_client.window_finder import find_chat_window


def find_chat_room_window():
    """열려있는 채팅방 창 찾기"""
    hwnd = find_chat_window()
    if hwnd:
        return auto.ControlFromHandle(hwnd)
    return None


def get_messages(chat_control):
    """채팅방에서 메시지 목록 가져오기"""
    try:
        msg_list = chat_control.ListControl(
            Name="메시지",
            searchDepth=5
        )

        if not msg_list.Exists(maxSearchSeconds=0.5):
            return []

        messages = get_children_recursive(msg_list, max_depth=2, filter_empty=True)
        return messages
    except Exception as e:
        print(f"오류: {e}")
        return []


def get_message_hash(messages):
    """메시지 리스트의 고유 해시값 생성"""
    if not messages:
        return ""

    # 마지막 3개 메시지의 이름 조합
    last_names = [m.Name or "" for m in messages[-3:]]
    return f"{len(messages)}:{hash(tuple(last_names))}"


def p(msg):
    """버퍼링 없이 출력"""
    print(msg, flush=True)


def main():
    pythoncom.CoInitialize()

    p("="*50)
    p("메시지 변화 감지 테스트")
    p("="*50)
    p("")
    p("채팅방 창 찾는 중...")

    chat_win = find_chat_room_window()

    if not chat_win:
        p("채팅방을 찾을 수 없습니다.")
        p("카카오톡 채팅방을 먼저 열어주세요.")
        return

    p(f"찾은 채팅방: {chat_win.Name}")
    p("")

    # 초기 메시지 목록 가져오기
    messages = get_messages(chat_win)
    last_count = len(messages)
    last_hash = get_message_hash(messages)

    p(f"초기 메시지 수: {last_count}")
    if messages:
        p(f"마지막 메시지: {messages[-1].Name[:50] if messages[-1].Name else '(없음)'}...")
    p("")
    p("모니터링 시작 (Ctrl+C로 종료)")
    p("-"*50)

    poll_count = 0
    poll_interval = 0.5  # 500ms

    try:
        while True:
            time.sleep(poll_interval)
            poll_count += 1

            # 메시지 목록 새로고침
            messages = get_messages(chat_win)
            current_count = len(messages)
            current_hash = get_message_hash(messages)

            # 변화 감지
            if current_hash != last_hash:
                now = datetime.now().strftime("%H:%M:%S")
                new_count = current_count - last_count

                p("")
                p(f"[{now}] 변화 감지!")
                p(f"  이전: {last_count}개 -> 현재: {current_count}개")

                if new_count > 0:
                    p(f"  새 메시지 {new_count}개:")
                    # 새 메시지들 출력
                    for msg in messages[-new_count:]:
                        name = msg.Name or "(빈 이름)"
                        p(f"    - {name[:80]}")
                elif new_count < 0:
                    p(f"  메시지 {-new_count}개 줄어듦 (스크롤?)")
                else:
                    p("  내용 변경 (수 같음)")

                last_count = current_count
                last_hash = current_hash

            # 10번마다 상태 표시
            if poll_count % 20 == 0:
                p(f"[폴링 {poll_count}회] 메시지 수: {current_count}")

    except KeyboardInterrupt:
        p("")
        p("-"*50)
        p(f"종료. 총 {poll_count}회 폴링")


if __name__ == "__main__":
    main()
