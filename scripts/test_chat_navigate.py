"""채팅방 메시지 네비게이션 테스트 스크립트

사용법:
    uv run python scripts/test_chat_navigate.py

동작:
    1. 카카오톡 채팅방 창 찾기
    2. 메시지 목록 로드
    3. 메시지 탐색 테스트 (첫/마지막/이동)
"""

import sys
import io
import time

# Windows 콘솔 인코딩 문제 해결
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from kakaotalk_a11y_client.window_finder import (
    check_kakaotalk_running,
    get_active_chat_windows,
)
from kakaotalk_a11y_client.navigation import ChatRoomNavigator


def main():
    print("=" * 50)
    print("채팅방 메시지 네비게이션 테스트")
    print("=" * 50)

    # 1. 카카오톡 실행 확인
    print("\n[1] 카카오톡 실행 확인...")
    if not check_kakaotalk_running():
        print("  실패: 카카오톡이 실행되지 않았습니다")
        return False

    print("  성공: 카카오톡 실행 중")

    # 2. 열린 채팅방 찾기
    print("\n[2] 열린 채팅방 확인...")
    chat_windows = get_active_chat_windows()

    if not chat_windows:
        print("  실패: 열린 채팅방이 없습니다")
        print("  카카오톡에서 채팅방을 열어주세요")
        return False

    print(f"  {len(chat_windows)}개 채팅방 열림:")
    for i, w in enumerate(chat_windows):
        print(f"    {i+1}. {w.title}")

    # 3. 첫 번째 채팅방으로 네비게이션 테스트
    target = chat_windows[0]
    print(f"\n[3] 채팅방 '{target.title}' 네비게이션 테스트...")

    navigator = ChatRoomNavigator()

    if not navigator.enter_chat_room(target.hwnd):
        print("  실패: 채팅방 진입 실패")
        print("  메시지 목록을 찾을 수 없습니다")
        return False

    print(f"  성공: 메시지 {len(navigator.messages)}개 로드됨")

    # 4. 메시지 샘플 출력
    print("\n[4] 메시지 샘플 (최근 5개)...")
    start_idx = max(0, len(navigator.messages) - 5)
    for i in range(start_idx, len(navigator.messages)):
        msg = navigator.messages[i]
        name = msg.Name or "(no name)"
        # 긴 메시지는 자르기
        if len(name) > 60:
            name = name[:60] + "..."
        print(f"    [{i+1}] {name}")

    # 5. 탐색 테스트
    print("\n[5] 탐색 테스트...")

    print("  마지막 메시지로 이동:")
    navigator.move_to_last()
    info = navigator.get_current_message_info()
    print(f"    위치: {navigator.current_index + 1}/{len(navigator.messages)}")
    print(f"    내용: {info.get('content', '')[:50]}")

    print("\n  첫 번째 메시지로 이동:")
    navigator.move_to_first()
    info = navigator.get_current_message_info()
    print(f"    위치: {navigator.current_index + 1}/{len(navigator.messages)}")
    print(f"    내용: {info.get('content', '')[:50]}")

    print("\n  아래로 3번 이동:")
    for _ in range(3):
        navigator.move_down()
    info = navigator.get_current_message_info()
    print(f"    위치: {navigator.current_index + 1}/{len(navigator.messages)}")
    print(f"    내용: {info.get('content', '')[:50]}")

    # 정리
    navigator.exit_chat_room()

    print("\n" + "=" * 50)
    print("테스트 완료")
    print("=" * 50)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
