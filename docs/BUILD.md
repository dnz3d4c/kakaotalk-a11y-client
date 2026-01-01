# 빌드 가이드

## 요구사항

- Python 3.10+
- uv (패키지 관리자)
- PyInstaller
- wxPython 4.2+ (GUI 모드용)

## 빌드 방법

### 1. PyInstaller 설치

```powershell
uv pip install pyinstaller
```

### 2. 빌드 실행

```powershell
uv run python scripts/build.py
```

### 3. 결과물

빌드 완료 후 `dist/KakaotalkA11y/` 폴더에 실행 파일 생성:

```
dist/KakaotalkA11y/
├── KakaotalkA11y.exe    # 메인 실행 파일
├── *.dll                 # 의존 라이브러리
└── ...
```

## 빌드 설정

### KakaotalkA11y.spec

- **진입점**: `src/kakaotalk_a11y_client/__main__.py`
- **콘솔 모드**: `console=True` (필수)
  - `console=False`로 빌드하면 즉시 종료되는 현상이 발생합니다
  - 콘솔 창 숨기기(ShowWindow, FreeConsole)는 프로세스 종료를 유발하여 사용할 수 없습니다
  - 콘솔 창을 숨기려면 바로가기에서 "최소화 실행" 설정을 사용합니다 (아래 참조)
- **제외된 패키지**: tkinter, unittest, sqlite3 등 미사용 모듈

### Hidden Imports

PyInstaller가 자동 감지하지 못하는 모듈:

- `accessible_output2.*` - 스크린 리더 출력
- `pyttsx3.*` - TTS 엔진
- `uiautomation` - UI 자동화
- `win32api`, `win32con`, `win32gui` - Windows API
- `wx`, `wx.adv` - wxPython GUI
- `kakaotalk_a11y_client.*` - 메인 패키지 및 하위 모듈

## 실행 방법

### GUI 모드 (기본, 권장)

```powershell
# 소스에서 실행 - 시스템 트레이로 시작
uv run kakaotalk-a11y

# 빌드된 exe 실행
dist\KakaotalkA11y\KakaotalkA11y.exe
```

- 시스템 트레이 아이콘으로 실행
- 콘솔 창 없이 백그라운드 동작
- 트레이 우클릭으로 메뉴 접근 (설정, 종료)
- 트레이 더블클릭으로 설정 다이얼로그 열기
- Win+B → 화살표키로 트레이 아이콘 선택 (NVDA 사용자)

### 콘솔 모드

```powershell
# 기존 콘솔 방식으로 실행
uv run kakaotalk-a11y --console

# 빌드된 exe
dist\KakaotalkA11y\KakaotalkA11y.exe --console
```

콘솔 창에서 실행합니다. 디버깅이나 이전 방식을 선호하는 경우에 사용합니다.

### 디버그 모드

```powershell
# 소스에서 실행
$env:DEBUG=1; uv run kakaotalk-a11y

# 빌드된 exe 실행
$env:DEBUG=1; dist\KakaotalkA11y\KakaotalkA11y.exe
```

DEBUG 환경변수 설정 시:
- 콘솔에 상세 로그 출력
- `%TEMP%\kakaotalk_a11y_debug.log` 디버그 로그
- `%TEMP%\kakaotalk_a11y_profile_*.log` 프로파일러 로그

| DEBUG 값 | 로그 레벨 | 설명 |
|----------|----------|------|
| 미설정 | NONE | 로그 없음 (기본) |
| 1 | DEBUG | 모든 로그 출력 |
| 2 | INFO | INFO 이상만 출력 |

## 배포

`dist/KakaotalkA11y/` 폴더 전체를 압축하여 배포합니다.

사용자는 `KakaotalkA11y.exe`를 실행하면 됩니다.

## 문제 해결

### ModuleNotFoundError

빌드 후 실행 시 모듈을 찾지 못하면 `KakaotalkA11y.spec`의 `hiddenimports`에 해당 모듈 추가.

### DLL 누락

Windows 시스템 DLL 누락 시 Visual C++ Redistributable 설치 필요.

### 콘솔 창 숨기기

실행 시 콘솔 창이 표시됨. 숨기려면 바로가기 설정 사용:

1. `KakaotalkA11y.exe` 우클릭 → "바로가기 만들기"
2. 바로가기 우클릭 → "속성"
3. "실행" 항목을 "최소화"로 변경
4. 확인

이후 바로가기로 실행하면 콘솔 창이 최소화된 상태로 시작.
