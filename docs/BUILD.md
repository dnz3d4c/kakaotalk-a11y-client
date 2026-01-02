# 빌드 가이드

## 요구사항

- Python 3.14+
- uv (패키지 관리자)
- PyInstaller

## 개발 환경 설정

```powershell
uv sync
```

의존성 설치 후 `uv run kakaotalk-a11y`로 실행 가능.

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

## 빌드 설정 (KakaotalkA11y.spec)

### 진입점

`src/kakaotalk_a11y_client/__main__.py`

### 데이터 파일

이모지 이미지 폴더가 번들에 포함됨:

```python
datas=[
    ('src/kakaotalk_a11y_client/emojis', 'kakaotalk_a11y_client/emojis'),
],
```

### Hidden Imports

PyInstaller가 자동 감지하지 못하는 모듈:

- `accessible_output2.*` - 스크린 리더 출력
- `pyttsx3.*` - TTS 엔진
- `uiautomation` - UI 자동화
- `win32api`, `win32con`, `win32gui` - Windows API
- `wx`, `wx.adv` - wxPython GUI
- `kakaotalk_a11y_client.*` - 메인 패키지 및 하위 모듈

### 제외된 패키지

빌드 크기 최적화를 위해 제외:

- tkinter (미사용, wx 사용)
- unittest, test, pydoc, doctest
- email, html, http, xmlrpc, ftplib
- sqlite3
- lib2to3, multiprocessing

## 실행 방법

### GUI 모드 (기본)

```powershell
# 소스에서 실행
uv run kakaotalk-a11y

# 빌드된 exe
dist\KakaotalkA11y\KakaotalkA11y.exe
```

시스템 트레이 아이콘으로 백그라운드 실행. 트레이 우클릭으로 메뉴 접근.

### 콘솔 모드

```powershell
uv run kakaotalk-a11y --console
```

콘솔 창에서 실행. 디버깅용.

### 디버그 모드

```powershell
# CLI 옵션 (권장)
uv run kakaotalk-a11y --debug              # DEBUG 레벨
uv run kakaotalk-a11y --debug --trace      # TRACE 레벨 (고빈도 로그 포함)

# 환경변수 (레거시)
$env:DEBUG=1; uv run kakaotalk-a11y
```

로그 위치: `logs/debug.log`

## 배포

`dist/KakaotalkA11y/` 폴더 전체를 압축하여 배포.

## 문제 해결

### ModuleNotFoundError

빌드 후 실행 시 모듈을 찾지 못하면 `KakaotalkA11y.spec`의 `hiddenimports`에 해당 모듈 추가.

### DLL 누락

Windows 시스템 DLL 누락 시 Visual C++ Redistributable 설치 필요.
