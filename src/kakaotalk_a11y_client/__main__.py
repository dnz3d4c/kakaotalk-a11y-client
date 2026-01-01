# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""PyInstaller 빌드용 런처"""
import sys


# console=False 빌드 시 stdout/stderr가 None이 되어 print() 예외 발생 방지
# (현재는 console=True 사용, 향후 호환성 위해 유지)
class _NullWriter:
    def write(self, s):
        pass

    def flush(self):
        pass


if sys.stdout is None:
    sys.stdout = _NullWriter()
if sys.stderr is None:
    sys.stderr = _NullWriter()


from kakaotalk_a11y_client.main import main

if __name__ == "__main__":
    main()
