# 카카오톡 접근성 클라이언트 - UIA 개발 난황 분석

## 프로젝트 개요

카카오톡 PC 버전을 스크린 리더(NVDA) 사용자가 키보드만으로 조작할 수 있도록 하는 접근성 스크립트.

### 핵심 기술
- **UI Automation (UIA)**: 카카오톡 UI 요소 탐색/조작
- **OpenCV 템플릿 매칭**: 공감 이모지 탐지 (UIA 미노출 영역)
- **keyboard 라이브러리**: 전역 키보드 후킹
- **accessible_output2**: NVDA 음성 출력

### 현재 구현 상태
- 이모지 탐지 및 클릭 (MVP 완료)
- 채팅방 메시지 탐색 (부분 구현)
- 탭 전환, ~~컨텍스트 메뉴 처리~~ (폐기됨 - NVDA 네이티브 동작에 위임)

---

## 1. 카카오톡 UI 특이점 (UIA 덤프 분석)

### 1.1 빈 ListItemControl 대량 발생 (심각)

**현상:**
```
[ListItemControl] Name: (no name) | AutoId:
[ListItemControl] Name: (no name) | AutoId:
... (164개 연속)
```

**상세:**
- 메시지 리스트에서 실제 메시지 9~10개, 빈 항목 164개 연속
- 스크린리더 탐색 시 극심한 지연 발생

**추정 원인:**
- 가상 스크롤/렌더링 최적화로 인한 더미 요소
- 화면 밖 메시지용 placeholder

**현재 대응:**
```python
# uia_utils.py
def get_children_recursive(control, max_depth=2, filter_empty=True):
    # filter_empty=True로 빈 항목 제외
```

**개선 요청:**
- 빈 항목 탐지 최적화 방안
- 가상 스크롤 환경에서의 UIA 탐색 전략

---

### 1.2 Class 정보 부재 (심각)

**현상:**
```
[ButtonControl] Name: "전송" | Class: (no class)
[ListItemControl] Name: "메시지 내용" | Class:
[MenuItemControl] Name: "대화 캡처" | Class=
```

**상세:**
- 대부분의 컨트롤이 ClassName 미지정
- 일부만 EVA_* 클래스 사용 (EVA_Window_Dblclk, EVA_Menu 등)

**영향:**
- ClassName 기반 검색 불가
- 컨트롤 타입 구분 어려움

**현재 대응:**
```python
# ClassName 대신 Name 또는 ControlTypeName으로 검색
list_control = parent.ListControl(Name="메시지", searchDepth=5)
```

**개선 요청:**
- ClassName 없는 환경에서의 안정적인 요소 식별 패턴

---

### 1.3 AutomationId 불균일 (중간)

**현상:**
```
AutoId: 86438192              (숫자만)
AutoId: [홍길동] , TEST [오후 2:24]  (내용 복제)
AutoId:                       (빈값)
```

**상세:**
- 세 가지 패턴이 혼재
- 메시지의 경우 AutoId에 내용이 복제되는 경우 있음

**영향:**
- AutomationId 기반 유일 식별 어려움

**현재 대응:**
- AutoId 의존 최소화, Name + ControlTypeName 조합 사용

---

### 1.4 광고 요소 (Chromium 웹뷰) (경미)

**현상:**
```
[PaneControl] Class=Chrome_WidgetWin_0/1
  → AdFit NAS Advertisement
  → BrowserRootView (웹 콘텐츠)
```

**영향:**
- UIA 트리 계층 복잡화
- 웹뷰 내부 요소는 표준 UIA로 접근 어려울 수 있음

---

## 2. UIA 탐색 성능/안정성 문제

### 2.1 searchDepth 깊이와 성능 트레이드오프

**문제:**
- searchDepth 너무 얕으면 요소 못 찾음
- searchDepth 너무 깊으면 탐색 느림

**현재 설정:**
| 대상 | searchDepth | 이유 |
|------|-------------|------|
| 메인 탭 | 5 | 얕은 계층 |
| 채팅/친구 목록 | 6 | 리스트 컨트롤 내부 |
| 메시지 리스트 | 5 | 깊은 계층 피하기 |
| ~~컨텍스트 메뉴~~ | ~~10-15~~ | ~~EVA_Menu 깊숙이 위치~~ (폐기됨) |

**코드 예시:**
```python
# chat_list.py:41
list_control = parent.ListControl(searchDepth=6, ClassName='EVA_VH_ListControl_Dblclk')

# [폐기됨] context_menu.py:49-96 - NVDA 네이티브 동작에 위임
# eva_menu = root.MenuControl(searchDepth=10, ClassName='EVA_Menu')
# 실패 시 searchDepth=15까지 증가
```

**개선 요청:**
- searchDepth 동적 조정 전략
- 성능과 정확도 균형점 찾기

---

### ~~2.2 컨텍스트 메뉴 탐색 (5회 재시도 필요)~~ [폐기됨]

> **폐기 사유**: context_menu.py 제거됨 (2025-12-31). NVDA 네이티브 동작에 위임.
> 현재는 main.py의 포커스 모니터가 MenuItemControl 감지 시 자동 발화.

**문제:**
- 우클릭 후 메뉴가 즉시 UIA로 감지되지 않음
- 포커스 이벤트 불안정

**현재 코드 (context_menu.py:37-43):**
```python
for attempt in range(5):
    log.debug(f"메뉴 찾기 시도 {attempt + 1}/5")
    if self._find_popup_menu():
        return True
    time.sleep(0.1)
# 총 0.5초 대기, 그래도 실패 가능
```

**4가지 메뉴 탐색 방법 (context_menu.py:49-96):**
```python
def _find_popup_menu(self) -> bool:
    # 방법 1: MenuControl + EVA_Menu 클래스 깊은 검색
    eva_menu = root.MenuControl(searchDepth=10, ClassName='EVA_Menu')

    # 방법 2: 카카오톡 창들 내에서 검색
    for win in root.GetChildren():
        if 'EVA_' in (win.ClassName or ''):
            menu = win.MenuControl(searchDepth=5, ClassName='EVA_Menu')

    # 방법 3: 일반 MenuControl 검색
    menu = root.MenuControl(searchDepth=10)

    # 방법 4: Win32 API로 팝업 모드 확인 후 재검색
    if self._check_popup_menu_mode():
        eva_menu = root.MenuControl(searchDepth=15, ClassName='EVA_Menu')
```

**개선 요청:**
- 메뉴 탐색 안정화 전략
- 적응형 재시도 로직 (성공률 기반)

---

### 2.3 포커스 모니터링 CPU 부하

**문제:**
- 포커스 변화 감지를 위해 지속적 폴링 필요
- UIA GetFocusedControl() 반복 호출로 CPU 사용

**현재 최적화 (main.py:427-507):**
```python
def _focus_monitor_loop(self) -> None:
    # 1. 웜업 기간: 초기 3초는 느린 폴링 (0.5s)
    if elapsed < warmup_duration:
        time.sleep(0.5)
        continue

    # 2. 비활성 시 UIA 호출 스킵
    fg_hwnd = win32gui.GetForegroundWindow()
    if not is_kakaotalk_window(fg_hwnd):
        time.sleep(0.5)
        continue

    # 3. 적응형 폴링 간격
    # 메뉴 모드: 50ms (빠른 응답)
    # 탭 모드: 100ms
    # 평상시: 200ms

    # 4. 디바운싱: 50ms 후 재확인
    focused2 = auto.GetFocusedControl()
    if focused2 and focused.Name == focused2.Name:
        self._speak_item(name, control_type)
```

**개선 요청:**
- 이벤트 기반 방식 전환 가능성 검토
- 폴링 간격 추가 최적화

---

### 2.4 COM 초기화 중복

**문제:**
- 각 네비게이터에서 매번 CoInitialize() 호출
- 스레드마다 필요하지만 중복 호출됨

**현재 코드 (각 네비게이터 enter() 함수):**
```python
def enter(self, hwnd: int) -> bool:
    pythoncom.CoInitialize()  # 매번 호출
    parent_control = auto.ControlFromHandle(hwnd)
    ...
```

**개선 요청:**
- 스레드당 1회 초기화로 통합하는 패턴

---

## 3. 키보드 후킹 문제

### 3.1 keyboard.unhook_all() 부작용

**문제:**
- disable() 시 모든 후킹 제거
- 타 모듈의 후킹도 함께 제거됨

**현재 코드 (keyboard_nav.py:78):**
```python
def disable(self) -> None:
    if self._hooks_installed:
        keyboard.unhook_all()  # 위험: 다른 후킹도 제거
        self._hooks_installed = False
```

**개선 요청:**
- 개별 unhook으로 변경하는 패턴
- 후킹 핸들 관리 방법

---

### 3.2 NVDA와 잠재적 충돌

**문제:**
- keyboard 라이브러리 전역 후킹
- NVDA도 키보드 이벤트 처리함

**현재 대응 (keyboard_nav.py:51-68):**
```python
def enable(self) -> None:
    # suppress=False: 기본 동작 유지 (NVDA 호환)
    keyboard.on_press_key('up', self._handle_up, suppress=False)
    keyboard.on_press_key('down', self._handle_down, suppress=False)
```

**개선 요청:**
- NVDA와의 공존 최적화 방안
- 충돌 최소화 패턴

---

## 4. 현재 코드 구조

### 4.1 프로젝트 구조
```
src/kakaotalk_a11y_client/
├── main.py                    # 진입점, 전체 플로우 조율
├── keyboard_nav.py            # 방향키 등 네비게이션 키 후킹
├── hotkeys.py                 # RegisterHotKey API 기반 핫키
├── window_finder.py           # Win32 API로 카카오톡 창 찾기
├── accessibility.py           # NVDA/TTS 음성 출력
├── detector.py                # OpenCV 템플릿 매칭 이모지 탐지
├── clicker.py                 # pyautogui 마우스 클릭
├── config.py                  # 설정값
├── navigation/
│   ├── base.py               # BaseListNavigator 추상 클래스
│   ├── chat_room.py          # 채팅방 메시지 탐색
│   ├── chat_list.py          # 채팅 탭 목록 탐색
│   ├── friend_list.py        # 친구 탭 목록 탐색
│   ├── ~~context_menu.py~~   # [폐기됨] NVDA 네이티브 동작에 위임
│   └── tabs.py               # 메인 탭 전환
└── utils/
    ├── uia_utils.py          # UIA 트리 탐색 헬퍼
    ├── debug.py               # 디버그 로깅
    └── com_utils.py
```

### 4.2 핵심 패키지 의존성
```toml
dependencies = [
    "uiautomation>=2.0.0",      # UIA 접근
    "opencv-python>=4.8.0",     # 템플릿 매칭
    "pyautogui>=0.9.54",        # 마우스/키보드 자동화
    "pywin32>=306",             # Win32 API
    "accessible-output2>=0.17", # NVDA 연동
    "keyboard>=0.13.5",         # 전역 키보드 후킹
    "pyttsx3>=2.90",            # 폴백 TTS
]
```

---

## 5. 개선이 필요한 코드 위치

| 구분 | 파일:라인 | 현재 문제 | 요청 개선 |
|------|-----------|-----------|-----------|
| 안정성 | `keyboard_nav.py:78` | unhook_all() 전체 제거 | 개별 unhook |
| 안정성 | 각 네비게이터 enter() | COM 중복 초기화 | 스레드당 1회 |
| ~~성능~~ | ~~`context_menu.py:37-43`~~ | ~~고정 5회 재시도~~ | ~~적응형 재시도~~ [폐기됨] |
| 성능 | `main.py:427-507` | 폴링 기반 모니터링 | 이벤트 기반 검토 |
| 성능 | `window_finder.py` | 매번 EnumWindows | 캐싱 추가 |

---

## 6. 원하는 개선 방향

1. **안정성 강화**: 메뉴 탐색 실패율 감소, 포커스 이벤트 안정화
2. **성능 최적화**: CPU 사용량 감소, 응답 지연 최소화
3. **코드 품질**: 중복 제거, 예외 처리 세분화
4. **NVDA 호환성**: 스크린리더와의 충돌 최소화

---

## 7. 참고: UIA 타이밍 가이드라인 (현재 사용 중)

| 동작 | 권장 대기 시간 | 설명 |
|------|---------------|------|
| 우클릭 후 초기 대기 | 200ms | 메뉴 렌더링 완료 대기 |
| 재시도 간격 | 100ms | 포커스 안정화 대기 |
| SetFocus 후 대기 | 100-150ms | 시스템 포커스 전환 대기 |
| 디바운싱 검증 | 50ms | 중복 이벤트 필터링 |
| 키 전송 후 대기 | 150ms | 키보드 이벤트 처리 대기 |
