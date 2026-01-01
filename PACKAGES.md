# 권장 패키지 및 기술 스택

## 환경 관리: UV (필수)

사용자는 UV 기반으로 Python 환경을 관리함. pip 직접 사용 금지.

### UV 기본 명령어
```bash
# 패키지 추가
uv add <package>

# 개발 의존성 추가
uv add --dev <package>

# 동기화 (lock 파일 기반 설치)
uv sync

# 스크립트 실행
uv run python main.py

# 가상환경 활성화 없이 실행
uv run pytest
```

## Python 3.10+ 권장

## 핵심 패키지 (pyproject.toml에 정의됨)

### 1. 이미지 인식
```
opencv-python==4.8.0.76
numpy>=1.24.0
```
- 템플릿 매칭으로 이모지 위치 탐지
- 100% 로컬 처리, 외부 통신 없음

### 2. 화면 캡처 및 마우스 제어
```
pyautogui>=0.9.54
pillow>=10.0.0
```
- 화면 캡처
- 마우스 좌표 클릭

### 3. 윈도우 제어 (카카오톡 창 찾기)
```
pywin32>=306
```
- 카카오톡 윈도우 핸들 찾기
- 창 위치/크기 정보 획득

### 4. 접근성 GUI (NVDA 호환)
```
accessible_output2>=0.17
wxPython>=4.2.0
```
- accessible_output2: NVDA/JAWS 등 스크린 리더에 텍스트 출력
- wxPython: 접근성 지원 GUI 프레임워크

### 대안 GUI 옵션
```
# 더 가벼운 대안
pyttsx3>=2.90  # TTS 엔진 (스크린 리더 없을 때 대비)
keyboard>=0.13.5  # 글로벌 핫키 등록
```

## 설치 (UV 사용)
```bash
# 자동 셋업 스크립트 실행 (권장)
./setup.sh

# 또는 수동으로
uv sync

# GUI 포함 설치
uv sync --extra gui

# 개발 의존성 포함
uv sync --dev
```

## 프로젝트 구조 (UV + src 레이아웃)
```
kakaotalk-a11y-client/
├── pyproject.toml       # UV 프로젝트 설정
├── uv.lock              # 의존성 lock 파일 (자동 생성)
├── setup.sh             # 자동 셋업 스크립트
├── README.md            # 프로젝트 설명
├── PACKAGES.md          # 패키지 정보
├── CLAUDE_CODE_INSTRUCTIONS.md  # 클코 자동화 지시사항
├── src/
│   └── kakaotalk_a11y_client/
│       ├── __init__.py
│       ├── main.py              # 진입점
│       ├── detector.py          # 이모지 탐지 로직
│       ├── clicker.py           # 클릭 동작
│       ├── window_finder.py     # 카카오톡 창 찾기
│       ├── accessibility.py     # 스크린 리더 출력
│       ├── hotkeys.py           # 키보드 단축키
│       └── config.py            # 설정
├── templates/           # 이모지 템플릿 이미지
│   ├── heart.png
│   ├── thumbsup.png
│   ├── check.png
│   ├── smile.png
│   ├── surprise.png
│   └── sad.png
└── samples/             # 개발용 샘플 이미지
    └── screenshot_full.png
```

## 핵심 로직 흐름
```
1. 단축키 입력 (예: Ctrl+Shift+E)
2. 카카오톡 창 찾기 (pywin32)
3. 채팅 영역 스크린샷 (pyautogui)
4. 템플릿 매칭으로 이모지 탐지 (opencv)
5. 탐지 결과 음성 안내 (accessible_output2)
6. 사용자 선택 대기 (1~6 숫자키)
7. 선택된 이모지 좌표 클릭 (pyautogui)
```

## 실행 방법
```bash
# 개발 중 실행
uv run python -m kakaotalk_a11y_client.main

# 또는 스크립트로 등록된 경우
uv run kakaotalk-a11y
```

## 주의사항
- pyautogui의 failsafe 기능 활성화 권장 (마우스를 화면 모서리로 이동 시 중단)
- 템플릿 이미지는 실제 카카오톡에서 추출해야 정확도 높음
- DPI 스케일링 고려 필요 (100%, 125%, 150% 등)
