# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""소스 파일에 SPDX 라이선스 헤더를 일괄 추가하는 스크립트"""

import os
from pathlib import Path

HEADER = """# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""

SRC_DIR = Path(__file__).parent.parent / "src" / "kakaotalk_a11y_client"


def add_header_to_file(filepath: Path) -> bool:
    """파일에 헤더 추가. 이미 있으면 스킵. 추가했으면 True 반환."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 이미 SPDX 헤더가 있으면 스킵
    if content.startswith("# SPDX-License-Identifier:"):
        return False

    # 헤더 추가
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(HEADER + content)

    return True


def main():
    """모든 .py 파일에 헤더 추가"""
    added = 0
    skipped = 0

    for py_file in SRC_DIR.rglob("*.py"):
        if add_header_to_file(py_file):
            print(f"[추가] {py_file.relative_to(SRC_DIR)}")
            added += 1
        else:
            print(f"[스킵] {py_file.relative_to(SRC_DIR)} (이미 헤더 있음)")
            skipped += 1

    print(f"\n완료: {added}개 추가, {skipped}개 스킵")


if __name__ == "__main__":
    main()
