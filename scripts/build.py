"""PyInstaller 빌드 스크립트"""
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).parent.parent
    spec_file = root / "KakaotalkA11y.spec"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "-y",  # 기존 dist 덮어쓰기
        str(spec_file),
    ]

    subprocess.run(cmd, cwd=root, check=True)
    print(f"빌드 완료: {root / 'dist' / 'KakaotalkA11y'}")


if __name__ == "__main__":
    main()
