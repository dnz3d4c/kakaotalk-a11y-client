# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""소스 파일 변경 시 실행할 테스트 스크립트 매핑."""

import fnmatch
import subprocess
from pathlib import Path, PurePath

# 소스 패턴 -> 테스트 스크립트 매핑
# 패턴은 src/kakaotalk_a11y_client/ 기준 상대 경로
# **는 하위 디렉토리 전체 매칭 (pathlib.match 사용)
TEST_MAPPING: dict[str, list[str]] = {
    "updater/*.py": ["test_update_dialogs.py"],
    "updater/**/*.py": ["test_update_dialogs.py"],
    "gui/update_dialogs.py": ["test_update_dialogs.py"],
    "navigation/chat_room.py": ["test_chat_navigate.py"],
    "navigation/message_monitor.py": ["test_message_monitor.py"],
    "focus_monitor.py": ["focus_monitor.py"],
    "gui/tray_icon.py": ["test_tray_menu.py"],
    "gui/main_frame.py": ["test_tray_menu.py"],
}

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
SRC_PREFIX = "src/kakaotalk_a11y_client/"


def _match_pattern(path: str, pattern: str) -> bool:
    """패턴 매칭. **는 PurePath.match, 그 외는 fnmatch."""
    if "**" in pattern:
        # PurePath.match는 **를 하위 디렉토리 전체로 처리
        return PurePath(path).match(pattern)
    return fnmatch.fnmatch(path, pattern)


def get_tests_for_changes(changed_files: list[str]) -> list[str]:
    """변경된 파일 기반으로 실행할 테스트 반환."""
    tests: set[str] = set()

    for file_path in changed_files:
        # src/kakaotalk_a11y_client/ 접두사 제거
        if file_path.startswith(SRC_PREFIX):
            relative_path = file_path[len(SRC_PREFIX) :]
        else:
            continue  # 소스 디렉토리 외부 파일은 무시

        # 패턴 매칭
        for pattern, test_scripts in TEST_MAPPING.items():
            if _match_pattern(relative_path, pattern):
                tests.update(test_scripts)

    return sorted(tests)


def get_staged_files() -> list[str]:
    """git diff --staged --name-only로 스테이징된 파일 목록 반환."""
    result = subprocess.run(
        ["git", "diff", "--staged", "--name-only"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_changed_files() -> list[str]:
    """git diff --name-only로 변경 파일 목록 반환 (unstaged 포함)."""
    result = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> None:
    """CLI: 변경된 파일에 대한 테스트 스크립트 출력."""
    # staged + unstaged 모두 확인
    staged = get_staged_files()
    unstaged = get_changed_files()
    all_changed = list(set(staged + unstaged))

    if not all_changed:
        print("변경된 파일 없음")
        return

    print(f"변경된 파일 ({len(all_changed)}개):")
    for f in sorted(all_changed):
        print(f"  {f}")

    tests = get_tests_for_changes(all_changed)

    if tests:
        print(f"\n실행할 테스트 ({len(tests)}개):")
        for t in tests:
            print(f"  scripts/{t}")
    else:
        print("\n매핑된 테스트 없음")


if __name__ == "__main__":
    main()
