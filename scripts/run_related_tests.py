# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""변경된 파일 기반으로 관련 테스트 스크립트 실행."""

import argparse
import subprocess
import sys
from pathlib import Path

from test_mapping import get_changed_files, get_staged_files, get_tests_for_changes


def run_test(test_name: str) -> int:
    """테스트 스크립트 실행. 종료 코드 반환."""
    script_path = Path(__file__).parent / test_name
    if not script_path.exists():
        print(f"스크립트 없음: {test_name}")
        return 1

    print(f"\n{'='*50}")
    print(f"실행: {test_name}")
    print("=" * 50)

    result = subprocess.run([sys.executable, str(script_path)])
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="변경 파일 기반 테스트 실행")
    parser.add_argument("--staged", action="store_true", help="staged 파일만")
    parser.add_argument("--all", action="store_true", help="모든 변경 파일 (staged + unstaged)")
    parser.add_argument("--dry-run", action="store_true", help="실행하지 않고 목록만 출력")
    parser.add_argument("-y", "--yes", action="store_true", help="확인 없이 바로 실행")
    args = parser.parse_args()

    # 변경 파일 수집
    if args.staged:
        files = get_staged_files()
        mode = "staged"
    elif args.all:
        files = list(set(get_staged_files() + get_changed_files()))
        mode = "all"
    else:
        files = get_changed_files()
        mode = "unstaged"

    if not files:
        print(f"변경된 파일 없음 (mode: {mode})")
        return 0

    # 관련 테스트 찾기
    tests = get_tests_for_changes(files)

    print(f"변경 파일 ({len(files)}개, {mode}):")
    for f in sorted(files):
        print(f"  {f}")

    if not tests:
        print("\n관련 테스트 없음")
        return 0

    print(f"\n관련 테스트 ({len(tests)}개):")
    for t in tests:
        print(f"  scripts/{t}")

    if args.dry_run:
        return 0

    # 실행 확인
    if not args.yes:
        try:
            answer = input("\n실행할까? (y/n): ").strip().lower()
            if answer != "y":
                print("취소됨")
                return 0
        except (EOFError, KeyboardInterrupt):
            print("\n취소됨")
            return 0

    # 테스트 실행
    failed = []
    for test in tests:
        code = run_test(test)
        if code != 0:
            failed.append(test)

    # 결과 요약
    print(f"\n{'='*50}")
    print(f"결과: {len(tests) - len(failed)}/{len(tests)} 성공")
    if failed:
        print("실패한 테스트:")
        for t in failed:
            print(f"  {t}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
