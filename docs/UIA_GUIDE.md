# Windows UI Automation (UIA) 완전 가이드

Python으로 Windows 앱 자동화나 접근성 도구를 개발하는 분을 위한 가이드입니다.
Windows 10/11, Python 3.10+, uiautomation 패키지 기준으로 작성되었습니다.

---

## 목차

1. [UIA 아키텍처 개괄](#1-uia-아키텍처-개괄)
2. [UIA 핵심 개념](#2-uia-핵심-개념)
3. [Python UIA 패키지 비교](#3-python-uia-패키지-비교)
4. [UIA 이벤트 시스템](#4-uia-이벤트-시스템)
5. [UIA 탐색 실전 가이드](#5-uia-탐색-실전-가이드)
6. [uiautomation 패키지 빠른 참조](#6-uiautomation-패키지-빠른-참조)
7. [UIA 문제 해결 가이드](#7-uia-문제-해결-가이드)

---

# 1. UIA 아키텍처 개괄

## 1.1 UIA란?

**Microsoft UI Automation (UIA)**는 Windows의 접근성 API로, 두 가지 목적으로 사용됨:

1. **접근성**: 스크린 리더(NVDA, JAWS 등)가 앱 UI 정보를 읽을 수 있게 함
2. **자동화**: 테스트 도구나 RPA가 앱을 프로그래밍 방식으로 제어

### UIA vs MSAA

| 항목 | MSAA (구형) | UIA (현재) |
|------|-------------|------------|
| 출시 | Windows 95 | Windows Vista (2005) |
| 아키텍처 | IAccessible COM | Provider/Client 분리 |
| 컨트롤 타입 | Role (30개) | ControlType (38개) |
| 기능 분류 | 없음 | Control Pattern |
| 트리 구조 | 단일 | Raw/Control/Content View |
| 성능 | 낮음 | 높음 (캐싱, 필터링) |

새 프로젝트에서는 UIA를 사용하는 것이 좋습니다.

## 1.2 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                  UIA Client (소비자)                         │
│         스크린 리더, 자동화 도구, 테스트 프레임워크             │
│              NVDA, pyautogui, uiautomation                  │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                   UIA Core (Windows)                        │
│          UIAutomationCore.dll - 중개자 역할                  │
│     - Provider와 Client 연결                                 │
│     - 프로세스 간 통신 처리                                   │
│     - 이벤트 라우팅                                          │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                  UIA Provider (제공자)                       │
│              UI 요소 정보를 노출하는 앱                       │
│      Win32, WinForms, WPF, Qt, Electron, 카카오톡 등         │
└─────────────────────────────────────────────────────────────┘
```

### Provider vs Client

| 역할 | Provider | Client |
|------|----------|--------|
| 누가 | 앱 개발자 | 자동화 도구 개발자 |
| 하는 일 | UI 정보 노출 | UI 정보 조회/조작 |
| 예시 | 카카오톡이 메시지 목록 노출 | 우리 스크립트가 메시지 읽기 |

## 1.3 지원 프레임워크

UIA Provider가 자동 제공되는 프레임워크:

| 프레임워크 | 지원 수준 | 비고 |
|------------|----------|------|
| Win32 표준 컨트롤 | ✅ 완전 | 버튼, 에디트, 리스트 등 |
| WinForms | ✅ 완전 | .NET 기반 |
| WPF | ✅ 완전 | XAML 기반 |
| UWP/WinUI | ✅ 완전 | 모던 앱 |
| Qt | ⚠️ 부분 | 기본 지원, 일부 커스텀 필요 |
| Electron | ⚠️ 부분 | Chromium 기반 |
| DirectUI/CustomDraw | ❌ 없음 | 앱에서 직접 구현 필요 |

카카오톡의 경우 대부분 UIA를 지원하지만, 공감 이모지 같은 일부 커스텀 UI는 지원되지 않습니다.

## 1.4 UIA 트리 구조

UIA는 UI 요소를 트리 형태로 표현합니다. 세 가지 뷰가 있습니다:

### Raw View
- 모든 요소 포함
- 가장 상세하지만 노이즈 많음

### Control View (기본)
- 사용자가 상호작용 가능한 컨트롤만
- 대부분의 자동화에서 사용

### Content View
- 실제 콘텐츠만 (텍스트, 이미지 등)
- 데이터 추출에 유용

```
Desktop (Root)
├── 카카오톡 (Window)
│   ├── 탭 컨트롤 (Tab)
│   │   ├── 친구 탭 (TabItem)
│   │   ├── 채팅 탭 (TabItem)
│   │   └── 더보기 탭 (TabItem)
│   └── 채팅 목록 (List)
│       ├── 채팅방 1 (ListItem)
│       ├── 채팅방 2 (ListItem)
│       └── ...
└── 다른 앱들...
```

---

# 2. UIA 핵심 개념

## 2.1 Automation Element

UIA의 기본 단위입니다. 화면의 모든 UI 요소는 Automation Element로 표현됩니다.

### 주요 속성 (Property)

| 속성 | 설명 | 예시 |
|------|------|------|
| **Name** | 요소 이름 (스크린 리더가 읽음) | "전송 버튼", "홍길동" |
| **ControlType** | 컨트롤 종류 | Button, Edit, List |
| **AutomationId** | 개발자 지정 ID | "sendButton", "chatList" |
| **ClassName** | Win32 클래스명 | "Button", "Edit" |
| **BoundingRectangle** | 화면 좌표 (x, y, w, h) | (100, 200, 80, 30) |
| **IsEnabled** | 활성화 여부 | True/False |
| **IsOffscreen** | 화면 밖 여부 | True/False |
| **ProcessId** | 프로세스 ID | 1234 |

### 속성 카테고리 분류

UIA 속성은 용도별로 분류됩니다:

**식별 (Identification)**
| 속성 | 설명 |
|------|------|
| AutomationId | 개발자 지정 고유 ID |
| Name | 사용자에게 표시되는 이름 |
| ClassName | Win32 윈도우 클래스 |
| RuntimeId | 런타임 고유 식별자 |
| ProcessId | 소속 프로세스 ID |

**표시 (Display)**
| 속성 | 설명 |
|------|------|
| BoundingRectangle | 화면 좌표와 크기 |
| IsOffscreen | 화면 밖 여부 |
| Orientation | 방향 (수평/수직) |
| HelpText | 도움말 텍스트 |

**IsOffscreenBehavior (화면 밖 판별 설정)**

`IsOffscreen` 속성 판별 방식 설정:
- `Default`: 표준 판별 (요소가 뷰포트 밖이면 True)
- `Offscreen`: 항상 화면 밖으로 처리
- `Onscreen`: 항상 화면 안으로 처리

스크롤 영역 내 요소가 "화면 밖"으로 잘못 판정되는 문제 해결에 사용.

**상호작용 (Interaction)**
| 속성 | 설명 |
|------|------|
| IsEnabled | 활성화 여부 |
| HasKeyboardFocus | 키보드 포커스 보유 |
| IsKeyboardFocusable | 포커스 가능 여부 |
| AcceleratorKey | 단축키 |
| AccessKey | 접근 키 (Alt+문자) |

**요소 유형 (Element Type)**
| 속성 | 설명 |
|------|------|
| ControlType | 컨트롤 종류 |
| IsControlElement | Control View에 포함 여부 |
| IsContentElement | Content View에 포함 여부 |
| ItemType | 항목 유형 설명 |

**패턴 지원 확인**
| 속성 | 설명 |
|------|------|
| IsInvokePatternAvailable | Invoke 패턴 지원 |
| IsValuePatternAvailable | Value 패턴 지원 |
| IsScrollPatternAvailable | Scroll 패턴 지원 |
| ... | (각 패턴마다 존재) |

### 로컬라이제이션 주의사항

다음 속성은 시스템 언어에 따라 값이 달라집니다:
- `Name` - 사용자에게 표시되는 이름
- `HelpText` - 도움말 텍스트
- `AcceleratorKey` - 단축키 표시
- `LocalizedControlType` - 지역화된 컨트롤 타입명

자동화 시 언어 독립적인 속성(`AutomationId`, `ClassName`)을 우선 사용하세요.

### 접근성 특화 속성

스크린 리더와 보조 기술이 활용하는 속성:

| 속성 | 설명 | 값 |
|------|------|-----|
| **LiveSetting** | 동적 콘텐츠 변경 알림 수준 | Off, Polite, Assertive |
| **HeadingLevel** | 문서 헤딩 수준 | Level1~Level9, None |

**LiveSetting (라이브 리전)**
- `Off`: 변경 알림 안 함
- `Polite`: 사용자 작업 완료 후 알림 (채팅 메시지 등)
- `Assertive`: 즉시 알림 (긴급 오류 등)

ARIA의 `aria-live` 속성과 동일 개념. 실시간 채팅 영역에서 새 메시지 알림에 중요.

### 요소 찾기 전략

```
우선순위:
1. AutomationId - 가장 안정적 (개발자가 지정, 변경 적음)
2. Name + ControlType - 일반적
3. ClassName - Win32 앱에서 유용
4. 트리 위치 - 최후의 수단 (UI 변경 시 깨짐)
```

## 2.2 Control Type (컨트롤 타입)

UIA가 정의한 38개의 표준 컨트롤 타입:

### 자주 쓰는 타입

| ControlType | 용도 | 예시 |
|-------------|------|------|
| **Window** | 최상위 창 | 앱 메인 창, 다이얼로그 |
| **Button** | 클릭 가능 버튼 | 전송, 확인, 취소 |
| **Edit** | 텍스트 입력 | 검색창, 메시지 입력 |
| **Text** | 읽기 전용 텍스트 | 레이블, 안내문 |
| **List** | 목록 컨테이너 | 채팅 목록, 친구 목록 |
| **ListItem** | 목록 항목 | 개별 채팅방, 친구 |
| **Tab** | 탭 컨테이너 | 탭 바 |
| **TabItem** | 개별 탭 | 친구 탭, 채팅 탭 |
| **Menu** | 메뉴 | 우클릭 메뉴 |
| **MenuItem** | 메뉴 항목 | 복사, 삭제, 전달 |
| **Tree** | 트리 구조 | 폴더 목록 |
| **TreeItem** | 트리 항목 | 개별 폴더 |
| **Image** | 이미지 | 프로필 사진, 썸네일 |
| **CheckBox** | 체크박스 | 설정 옵션 |
| **RadioButton** | 라디오 버튼 | 단일 선택 |
| **ComboBox** | 드롭다운 | 선택 목록 |
| **ScrollBar** | 스크롤바 | 수직/수평 스크롤 |
| **ToolBar** | 도구 모음 | 버튼 모음 |
| **Pane** | 일반 컨테이너 | 패널, 영역 |
| **Document** | 문서 영역 | 채팅 내용 영역 |
| **Custom** | 커스텀 컨트롤 | 특수 UI (공감 이모지 등) |

## 2.3 Control Pattern (컨트롤 패턴)

컨트롤이 할 수 있는 기능을 정의합니다. 하나의 컨트롤이 여러 패턴을 지원할 수 있습니다.

### 전체 패턴 목록 (20개)

| Pattern | 기능 | 지원 컨트롤 | 주요 메서드/속성 |
|---------|------|-------------|------------------|
| **Invoke** | 클릭/실행 | Button, MenuItem | `Invoke()` |
| **Value** | 값 읽기/쓰기 | Edit, ComboBox | `Value`, `SetValue()` |
| **Text** | 텍스트 조작 | Edit, Document | `DocumentRange`, `GetText()` |
| **Selection** | 선택 관리 | List, Tab | `GetSelection()` |
| **SelectionItem** | 선택 가능 항목 | ListItem, TabItem | `Select()`, `IsSelected` |
| **ExpandCollapse** | 펼치기/접기 | TreeItem, ComboBox | `Expand()`, `Collapse()` |
| **Toggle** | 토글 상태 | CheckBox | `Toggle()`, `ToggleState` |
| **Scroll** | 스크롤 | ScrollBar, List | `Scroll()`, `ScrollPercent` |
| **ScrollItem** | 스크롤해서 보이기 | ListItem | `ScrollIntoView()` |
| **Grid** | 그리드 접근 | Table, DataGrid | `GetItem(row, col)` |
| **GridItem** | 그리드 항목 | DataItem | `Row`, `Column` |
| **Table** | 테이블 구조 | Table | `GetRowHeaders()` |
| **TableItem** | 테이블 항목 | DataItem | `GetRowHeaderItems()` |
| **RangeValue** | 범위 값 | Slider, ProgressBar | `Value`, `Minimum`, `Maximum` |
| **Transform** | 이동/크기조정 | Window | `Move()`, `Resize()`, `Rotate()` |
| **Dock** | 도킹 위치 | Pane | `DockPosition`, `SetDockPosition()` |
| **MultipleView** | 다중 뷰 | Calendar | `GetViewName()`, `SetCurrentView()` |
| **Window** | 창 제어 | Window | `Close()`, `WindowState` |
| **VirtualizedItem** | 가상화 아이템 실체화 | ListItem (가상 스크롤) | `Realize()` |
| **ItemContainer** | 속성으로 아이템 검색 | List, Tree | `FindItemByProperty()` |
| **SynchronizedInput** | 입력 동기화 추적 | 입력 받는 요소 | `StartListening()`, `Cancel()` |

### 동적 Control Patterns

일부 패턴은 컨트롤 상태에 따라 동적으로 지원 여부가 바뀝니다:

| 상황 | 패턴 변화 |
|------|----------|
| 멀티라인 EditBox에 텍스트 많음 | ScrollPattern 활성화 |
| 멀티라인 EditBox에 텍스트 적음 | ScrollPattern 비활성화 |
| ComboBox 펼쳐짐 | Selection 패턴 접근 가능 |
| TreeItem에 자식 없음 | ExpandCollapse 비활성화 |

패턴 지원 여부 확인:
```python
# 패턴 지원 여부 확인
if element.GetPattern(auto.PatternId.ScrollPattern):
    scroll = element.GetScrollPattern()
    scroll.Scroll(auto.ScrollAmount.LargeIncrement, auto.ScrollAmount.NoAmount)
```

### 패턴 사용 예시

```python
import uiautomation as auto

# 버튼 클릭 (Invoke 패턴)
button = auto.ButtonControl(Name="전송")
button.GetInvokePattern().Invoke()
# 또는 간단히
button.Click()

# 텍스트 입력 (Value 패턴)
edit = auto.EditControl(Name="메시지 입력")
edit.GetValuePattern().SetValue("안녕하세요")

# 리스트 아이템 선택 (SelectionItem 패턴)
item = auto.ListItemControl(Name="홍길동")
item.GetSelectionItemPattern().Select()

# 체크박스 토글 (Toggle 패턴)
checkbox = auto.CheckBoxControl(Name="알림 받기")
checkbox.GetTogglePattern().Toggle()
```

## 2.4 ControlType별 필수/선택 패턴

| ControlType | 필수 패턴 | 선택 패턴 |
|-------------|----------|----------|
| Button | Invoke | ExpandCollapse, Toggle |
| CheckBox | Toggle | - |
| ComboBox | ExpandCollapse | Selection, Value |
| Edit | - | Value, Text, RangeValue |
| List | - | Selection, Scroll, Grid |
| ListItem | SelectionItem | ExpandCollapse, Invoke, Toggle |
| Menu | - | - |
| MenuItem | - | Invoke, ExpandCollapse, Toggle |
| Tab | Selection | Scroll |
| TabItem | SelectionItem | - |
| Tree | - | Selection, Scroll |
| TreeItem | ExpandCollapse | SelectionItem, Invoke, Toggle |
| Window | Transform, Window | Dock |

---

# 3. Python UIA 패키지 비교

## 3.1 패키지 개요

| 패키지 | 설명 | 장점 | 단점 |
|--------|------|------|------|
| **uiautomation** | UIA 전용 래퍼 | 직관적, 문서화 좋음, 한국 사용자 다수 | Windows 전용 |
| **pywinauto** | UIA + Win32 지원 | 다양한 백엔드, 성숙한 프로젝트 | API 복잡 |
| **comtypes** | 저수준 COM 접근 | 완전한 제어 | 직접 COM 다뤄야 함 |

## 3.2 uiautomation (권장)

```bash
uv add uiautomation
```

**특징:**
- Microsoft UIA를 직접 래핑
- Python 3.4+ 지원
- comtypes 의존
- 직관적인 API

**기본 사용:**
```python
import uiautomation as auto

# 창 찾기
window = auto.WindowControl(searchDepth=1, Name='카카오톡')

# 컨트롤 찾기
button = window.ButtonControl(Name='전송')

# 존재 확인
if button.Exists(timeout=3):
    button.Click()
```

## 3.3 pywinauto

```bash
uv add pywinauto
```

**특징:**
- 두 가지 백엔드: `win32` (기본), `uia`
- 속성 기반 접근 (문자열로 컨트롤 찾기)
- 더 넓은 커뮤니티

**기본 사용:**
```python
from pywinauto import Application

# UIA 백엔드로 연결
app = Application(backend='uia').connect(title='카카오톡')

# 창 접근
main_window = app.window(title='카카오톡')

# 컨트롤 찾기 (문자열 기반)
main_window['전송'].click()

# 또는 명시적
button = main_window.child_window(title='전송', control_type='Button')
button.click()
```

## 3.4 어떤 걸 선택할까?

| 상황 | 추천 |
|------|------|
| UIA 학습/단순 자동화 | **uiautomation** |
| 복잡한 프로젝트, Win32도 필요 | pywinauto |
| 저수준 제어 필요 | comtypes |
| 접근성 도구 개발 | **uiautomation** |

이 문서는 `uiautomation` 패키지 기준으로 작성되었습니다.

---

# 4. UIA 이벤트 시스템

## 4.1 이벤트 종류

UIA 이벤트는 4가지 카테고리로 분류됩니다:

### 이벤트 카테고리

| 카테고리 | 설명 | 예시 |
|----------|------|------|
| **Property Change** | 속성 값 변경 | 체크박스 상태, 텍스트 값 |
| **Element Action** | 사용자/프로그램 활동 | 버튼 클릭, 메뉴 선택 |
| **Structure Change** | 트리 구조 변경 | 항목 추가/제거 |
| **Global Desktop** | 전역 이벤트 | 포커스 이동, 윈도우 종료 |

### 주요 이벤트 목록

| 이벤트 | 카테고리 | 설명 |
|--------|----------|------|
| **FocusChanged** | Global | 키보드 포커스 이동 |
| **PropertyChanged** | Property | 속성 값 변경 |
| **StructureChanged** | Structure | 트리 구조 변경 |
| **TextChanged** | Property | 텍스트 내용 변경 |
| **Notification** | Element | 중요 알림 |
| **WindowOpened** | Element | 새 윈도우 열림 |
| **WindowClosed** | Element | 윈도우 닫힘 |
| **MenuOpened** | Element | 메뉴 열림 |
| **MenuClosed** | Element | 메뉴 닫힘 |

### 이벤트 효율성

UIA Provider는 클라이언트 구독 여부에 따라 이벤트를 선택적으로 발생시킵니다:
- 구독자 없음 → 이벤트 발생 안 함 (성능 최적화)
- 구독자 있음 → 해당 이벤트만 발생

### 이벤트 주의사항

⚠️ 다음 이벤트는 실제 상태 변경 없이도 발생할 수 있습니다:
- `PropertyChangedEvent` - 같은 값으로 다시 설정될 때
- `ElementSelectedEvent` - 이미 선택된 항목 재선택 시
- `TextChangedEvent` - 같은 텍스트로 덮어쓸 때

이벤트 핸들러에서 실제 변경 여부를 검증하세요:
```python
def on_property_changed(sender, event_id, old_value, new_value):
    if old_value != new_value:  # 실제 변경 확인
        print(f"변경됨: {old_value} → {new_value}")
```

## 4.2 이벤트 구독 (uiautomation)

```python
import uiautomation as auto
import threading

# 포커스 변경 이벤트 핸들러
def on_focus_changed(sender, event_id):
    element = auto.Control(element=sender)
    print(f"포커스 변경: {element.Name} ({element.ControlTypeName})")

# 구조 변경 이벤트 핸들러  
def on_structure_changed(sender, event_id, runtime_id):
    element = auto.Control(element=sender)
    print(f"구조 변경: {element.Name}")

# 이벤트 등록
auto.UIAutomationEventHandlerGroup.AddFocusChangedEventHandler(on_focus_changed)

# 메인 루프 (이벤트 수신 대기)
print("이벤트 모니터링 시작... (Ctrl+C로 종료)")
try:
    while True:
        auto.ProcessMessages()  # 이벤트 처리
except KeyboardInterrupt:
    print("종료")
```

## 4.3 실전: 새 메시지 감지

```python
import uiautomation as auto
import time

class MessageMonitor:
    def __init__(self, chat_name):
        self.chat_name = chat_name
        self.last_message_count = 0
    
    def find_chat_list(self):
        """채팅 메시지 리스트 찾기"""
        kakao = auto.WindowControl(Name='카카오톡')
        # 채팅방 창에서 메시지 리스트 찾기
        chat_window = kakao.WindowControl(Name=self.chat_name)
        return chat_window.ListControl()
    
    def check_new_messages(self):
        """새 메시지 확인"""
        chat_list = self.find_chat_list()
        if not chat_list.Exists(timeout=1):
            return []
        
        items = chat_list.GetChildren()
        current_count = len(items)
        
        if current_count > self.last_message_count:
            new_messages = items[self.last_message_count:]
            self.last_message_count = current_count
            return new_messages
        
        return []
    
    def monitor(self, interval=1.0):
        """폴링 방식 모니터링"""
        print(f"{self.chat_name} 모니터링 시작...")
        while True:
            new = self.check_new_messages()
            for msg in new:
                print(f"새 메시지: {msg.Name}")
            time.sleep(interval)

# 사용
monitor = MessageMonitor("홍길동")
monitor.monitor()
```

## 4.4 이벤트 vs 폴링

| 방식 | 장점 | 단점 |
|------|------|------|
| **이벤트** | 실시간, CPU 효율적 | 구현 복잡, 일부 앱 미지원 |
| **폴링** | 단순, 확실함 | CPU 사용, 지연 발생 |

이벤트가 안정적이지 않으면 폴링을 사용하세요. 카카오톡 같은 앱에서는 폴링이 더 안정적인 경우가 많습니다.

---

# 5. UIA 탐색 실전 가이드

## 5.1 기본 탐색 패턴

### 1단계: 최상위 창 찾기

```python
import uiautomation as auto

# 방법 1: 이름으로 찾기
window = auto.WindowControl(searchDepth=1, Name='카카오톡')

# 방법 2: 클래스명으로 찾기
window = auto.WindowControl(searchDepth=1, ClassName='EVA_Window_Dblclk')

# 방법 3: 프로세스명으로 찾기 (불확실할 때)
for win in auto.GetRootControl().GetChildren():
    if win.ClassName and 'KakaoTalk' in win.ClassName:
        window = win
        break

# 존재 확인
if window.Exists(timeout=3):
    print(f"창 발견: {window.Name}")
else:
    print("창을 찾을 수 없음")
```

### 2단계: 하위 요소 찾기

```python
# 방법 1: 직접 자식에서 찾기
chat_list = window.ListControl(Name='채팅 목록')

# 방법 2: 깊이 지정 탐색
chat_list = window.ListControl(searchDepth=5)

# 방법 3: 전체 하위에서 찾기 (느림)
chat_list = window.ListControl(searchDepth=0xFFFFFFFF)

# 방법 4: 여러 조건 조합
button = window.ButtonControl(
    Name='전송',
    AutomationId='sendButton',
    searchDepth=3
)
```

### 3단계: 컬렉션 순회

```python
# 모든 자식 가져오기
children = chat_list.GetChildren()
for i, child in enumerate(children):
    print(f"{i}: {child.Name} ({child.ControlTypeName})")

# 특정 타입만 필터링
list_items = [c for c in children if c.ControlType == auto.ControlType.ListItemControl]

# n번째 항목 접근
if len(list_items) > 1:
    second_item = list_items[1]
    second_item.Click()
```

### 요소 획득 방법 비교

| 방법 | 용도 | 예시 |
|------|------|------|
| **FindFirst** | 첫 번째 일치 요소 | 특정 버튼 찾기 |
| **FindAll** | 모든 일치 요소 | 리스트 항목 전체 |
| **GetChildren** | 직접 자식 전체 | 컨테이너 내 요소 |
| **TreeWalker** | 트리 순회 | 부모/형제 탐색 |
| **FromPoint** | 좌표로 찾기 | 마우스 위치 요소 |
| **FromHandle** | HWND로 찾기 | Win32 윈도우 연결 |

### 좌표/핸들로 요소 찾기

```python
import uiautomation as auto

# 마우스 위치의 요소
element = auto.ControlFromPoint(x=500, y=300)
print(f"좌표(500,300): {element.Name}")

# 현재 마우스 위치
cursor_element = auto.GetCursorControl()
print(f"마우스 위치: {cursor_element.Name}")

# 포커스된 요소
focused = auto.GetFocusedControl()
print(f"포커스: {focused.Name}")
```

### TreeWalker 활용

UIA 트리를 직접 탐색할 때 사용합니다. 세 가지 미리 정의된 Walker가 있습니다:

| Walker | 포함 요소 | 용도 |
|--------|----------|------|
| **RawViewWalker** | 모든 요소 | 디버깅, 전체 구조 파악 |
| **ControlViewWalker** | IsControlElement=True | 일반 자동화 |
| **ContentViewWalker** | IsContentElement=True | 데이터 추출 |

```python
import uiautomation as auto

# 부모/형제 탐색
element = auto.ButtonControl(Name='전송')
parent = element.GetParentControl()
next_sibling = element.GetNextSiblingControl()
prev_sibling = element.GetPreviousSiblingControl()

# 첫 번째/마지막 자식
first_child = parent.GetFirstChildControl()
last_child = parent.GetLastChildControl()
```

### 복합 조건 검색

UIA는 조건을 조합해서 검색할 수 있습니다.

**조건 조합 클래스 (.NET)**

| 클래스 | 용도 | 예시 |
|--------|------|------|
| `AndCondition` | 모든 조건 만족 | Button이면서 Name="확인" |
| `OrCondition` | 하나라도 만족 | Button 또는 CheckBox |
| `NotCondition` | 조건 부정 | Name이 비어있지 않은 요소 |
| `PropertyCondition` | 단일 속성 조건 | Name="전송" |

**PropertyConditionFlags (조건 옵션)**

| 플래그 | 설명 |
|--------|------|
| `IgnoreCase` | 대소문자 무시 |
| `MatchSubstring` | 부분 일치 (포함 여부) |

**Python uiautomation 매핑**

```python
import uiautomation as auto

# AndCondition: 다중 파라미터로 암묵적 AND
button = window.ButtonControl(Name='확인', AutomationId='okBtn')

# 부분 일치: SubName 파라미터
button = window.ButtonControl(SubName='확')  # '확인', '확정' 등 매칭

# OrCondition: 직접 지원 안 함 → 여러 번 검색
button = window.ButtonControl(Name='확인')
if not button.Exists(timeout=0.1):
    button = window.ButtonControl(Name='OK')
```

## 5.2 탐색 최적화

### searchDepth 이해

```python
# searchDepth=1: 직접 자식만
# searchDepth=2: 자식 + 손자
# searchDepth=0xFFFFFFFF: 전체 하위 (느림!)

# 나쁜 예 - 전체 탐색
button = window.ButtonControl(searchDepth=0xFFFFFFFF, Name='전송')  # 느림!

# 좋은 예 - 단계적 탐색
toolbar = window.ToolBarControl(searchDepth=2)
button = toolbar.ButtonControl(searchDepth=1, Name='전송')  # 빠름
```

### foundIndex 사용

```python
# 같은 이름의 여러 요소 중 n번째 선택
first_button = window.ButtonControl(Name='확인', foundIndex=1)
second_button = window.ButtonControl(Name='확인', foundIndex=2)
```

### 캐싱 활용

```python
# 요소 재사용 (매번 찾지 않음)
chat_list = window.ListControl(Name='채팅 목록')

# 첫 접근 시 검색 발생
if chat_list.Exists():
    # 이후 접근은 캐시된 요소 사용
    print(chat_list.Name)
    print(chat_list.BoundingRectangle)

    # 명시적 새로고침 필요 시
    chat_list.Refind()
```

### UIA 캐싱 상세

UIA는 프로세스 간 통신(IPC)을 사용하므로 매번 속성을 조회하면 성능 저하가 발생합니다. 캐싱을 활용하면 여러 속성을 한 번에 가져와 성능을 크게 개선할 수 있습니다.

#### CacheRequest 개념

| 옵션 | 설명 | 예시 |
|------|------|------|
| **캐시할 속성** | 미리 로드할 속성 지정 | Name, BoundingRectangle |
| **캐시할 패턴** | 미리 로드할 패턴 지정 | Invoke, Value |
| **TreeScope** | 캐시 범위 | Element, Children, Descendants |
| **TreeFilter** | 포함할 요소 조건 | ControlView, ContentView |
| **AutomationElementMode** | 요소 정보 로드 수준 | None, Full |

**AutomationElementMode**
- `None`: 참조만 유지, 실제 요소 정보 안 가져옴 (메모리 절약)
- `Full`: 완전한 요소 정보 캐시 (기본값)

대량 요소 검색 시 `None` 모드로 참조만 가져온 후 필요한 요소만 `Full`로 조회하면 성능 개선.

#### 속성 접근 방식 비교

```python
# GetCurrentPropertyValue: 매번 IPC 발생 (느림)
name = element.GetPropertyValue(auto.PropertyId.NameProperty)

# GetCachedPropertyValue: 캐시된 값 사용 (빠름)
# - CacheRequest로 미리 로드한 경우만 사용 가능
# - uiautomation 패키지에서는 내부적으로 자동 캐싱 처리
```

#### uiautomation 패키지의 자동 캐싱

`uiautomation` 패키지는 내부적으로 캐싱을 자동 처리합니다:

```python
import uiautomation as auto

# 요소 검색 시 기본 속성들이 자동 캐싱됨
element = window.ButtonControl(Name='전송')

# 캐시된 속성 접근 (IPC 없음)
name = element.Name  # 캐시됨
rect = element.BoundingRectangle  # 캐시됨

# UI 변경 후 캐시 갱신
element.Refind()  # 캐시 무효화 + 재검색
```

#### 캐시 갱신이 필요한 상황

| 상황 | 대응 |
|------|------|
| UI 구조 변경됨 | `element.Refind()` 호출 |
| 속성값 변경됨 | 해당 속성 재조회 |
| 오래된 캐시 사용 중 | TTL 기반 자동 갱신 구현 |

#### 성능 팁

```python
# 나쁜 예: 반복문 내에서 매번 검색
for i in range(100):
    button = window.ButtonControl(Name='확인')  # 매번 검색!
    button.Click()

# 좋은 예: 검색 결과 재사용
button = window.ButtonControl(Name='확인')
for i in range(100):
    if button.Exists(timeout=0.1):
        button.Click()
    else:
        button.Refind()  # 필요 시만 재검색
```

## 5.3 트리 덤프 (디버깅)

개발 중 UI 구조 파악에 필수:

```python
import uiautomation as auto

def dump_tree(control, depth=0, max_depth=5, file=None):
    """UIA 트리 구조 출력"""
    if depth > max_depth:
        return
    
    indent = "  " * depth
    
    # 요소 정보 수집
    info = f"{control.ControlTypeName}"
    if control.Name:
        info += f" | Name: '{control.Name}'"
    if control.AutomationId:
        info += f" | ID: {control.AutomationId}"
    if control.ClassName:
        info += f" | Class: {control.ClassName}"
    
    line = f"{indent}{info}"
    
    if file:
        file.write(line + "\n")
    else:
        print(line)
    
    # 자식 순회
    for child in control.GetChildren():
        dump_tree(child, depth + 1, max_depth, file)

# 사용
kakao = auto.WindowControl(Name='카카오톡')
if kakao.Exists():
    # 콘솔 출력
    dump_tree(kakao, max_depth=4)
    
    # 파일 저장
    with open('kakao_tree.txt', 'w', encoding='utf-8') as f:
        dump_tree(kakao, max_depth=6, file=f)
```

## 5.4 카카오톡 탐색 실전 예시

### 메인 창 구조 파악

```python
import uiautomation as auto

def explore_kakao():
    kakao = auto.WindowControl(searchDepth=1, Name='카카오톡')
    
    if not kakao.Exists(timeout=3):
        print("카카오톡을 찾을 수 없습니다")
        return
    
    print("=== 카카오톡 메인 창 ===")
    print(f"Name: {kakao.Name}")
    print(f"ClassName: {kakao.ClassName}")
    print(f"AutomationId: {kakao.AutomationId}")
    
    print("\n=== 직접 자식 요소 ===")
    for i, child in enumerate(kakao.GetChildren()):
        print(f"{i}: {child.ControlTypeName} | {child.Name or '(이름없음)'}")

explore_kakao()
```

### 탭 전환

```python
def switch_to_chat_tab():
    kakao = auto.WindowControl(Name='카카오톡')
    
    # 탭 컨트롤 찾기
    tab = kakao.TabControl(searchDepth=3)
    
    if tab.Exists():
        # 채팅 탭 찾기 (보통 2번째)
        tab_items = tab.GetChildren()
        for item in tab_items:
            if '채팅' in item.Name:
                item.GetSelectionItemPattern().Select()
                print("채팅 탭으로 전환")
                return True
    
    return False
```

### 채팅방 메시지 읽기

```python
def read_messages(chat_name):
    kakao = auto.WindowControl(Name='카카오톡')
    
    # 채팅방 창 찾기 (별도 창으로 열린 경우)
    chat_window = auto.WindowControl(searchDepth=1, Name=chat_name)
    
    if not chat_window.Exists():
        # 메인 창 내부에서 찾기
        chat_window = kakao
    
    # 메시지 리스트 찾기
    msg_list = chat_window.ListControl(searchDepth=5)
    
    if msg_list.Exists():
        messages = msg_list.GetChildren()
        print(f"총 {len(messages)}개 메시지")
        
        # 최근 5개만 출력
        for msg in messages[-5:]:
            print(f"- {msg.Name}")
```

---

# 6. uiautomation 패키지 빠른 참조

## 6.1 설치 및 임포트

```bash
uv add uiautomation
```

```python
import uiautomation as auto

# 버전 확인
print(auto.VERSION)
```

## 6.2 컨트롤 클래스

모든 컨트롤은 `Control` 클래스를 상속:

| 클래스 | ControlType |
|--------|-------------|
| `WindowControl` | Window |
| `ButtonControl` | Button |
| `EditControl` | Edit |
| `TextControl` | Text |
| `ListControl` | List |
| `ListItemControl` | ListItem |
| `TabControl` | Tab |
| `TabItemControl` | TabItem |
| `MenuControl` | Menu |
| `MenuItemControl` | MenuItem |
| `TreeControl` | Tree |
| `TreeItemControl` | TreeItem |
| `CheckBoxControl` | CheckBox |
| `RadioButtonControl` | RadioButton |
| `ComboBoxControl` | ComboBox |
| `ImageControl` | Image |
| `PaneControl` | Pane |
| `DocumentControl` | Document |
| `CustomControl` | Custom |
| `Control` | 모든 타입 |

## 6.3 검색 매개변수

```python
control = auto.ButtonControl(
    # 검색 조건
    Name='전송',              # 정확히 일치
    SubName='전',             # 부분 일치
    RegexName=r'전송.*',      # 정규식 일치
    AutomationId='sendBtn',
    ClassName='Button',
    ControlType=auto.ControlType.ButtonControl,

    # 검색 범위
    searchDepth=5,            # 탐색 깊이 (기본: 0xFFFFFFFF)
    searchFromControl=parent, # 시작 지점 (기본: 데스크톱)

    # 검색 동작
    searchWaitTime=1.0,       # 검색 간격 (초)
    foundIndex=1,             # n번째 일치 항목 (1부터 시작)

    # 커스텀 조건 (람다 함수)
    Compare=lambda c, d: c.Name in ['확인', 'OK', '예'],
)
```

### 이름 매칭 옵션 (Name, SubName, RegexName)

세 가지 이름 검색 방식 중 **하나만** 사용할 수 있습니다 (상호 배타적).

| 파라미터 | 매칭 방식 | 예시 | 매칭되는 Name |
|----------|----------|------|--------------|
| `Name` | 정확히 일치 | `Name='확인'` | "확인"만 |
| `SubName` | 부분 문자열 포함 | `SubName='확'` | "확인", "확정", "미확인" |
| `RegexName` | 정규식 (`re.match`) | `RegexName=r'확.*'` | "확인", "확정" (시작 일치) |

```python
# 정확히 일치 - 가장 안정적
button = window.ButtonControl(Name='전송', searchDepth=3)

# 부분 일치 - 이름이 동적으로 바뀌는 경우 유용
# 예: "전송 (3)", "전송 중..." 등
button = window.ButtonControl(SubName='전송', searchDepth=3)

# 정규식 - 복잡한 패턴 매칭
# 예: "메시지 1", "메시지 2", "메시지 100" 등
item = window.ListItemControl(RegexName=r'메시지 \d+', searchDepth=5)
```

**주의**: `RegexName`은 `re.match()`를 사용하므로 문자열 **시작**부터 일치해야 합니다.
- `RegexName=r'확인'` → "확인" ✅, "미확인" ❌
- `RegexName=r'.*확인'` → "미확인" ✅

### Compare 파라미터 (커스텀 조건)

`Compare` 파라미터로 람다 함수를 전달해 **OR 조건**이나 복잡한 조건을 구현할 수 있습니다.

```python
# 함수 시그니처: lambda control, depth -> bool
# - control: 현재 검사 중인 요소
# - depth: 현재 탐색 깊이

# OR 조건 - 여러 이름 중 하나 매칭
button = window.ButtonControl(
    searchDepth=3,
    Compare=lambda c, d: c.Name in ['확인', 'OK', '예', 'Yes']
)

# 이름이 비어있지 않은 요소만
items = window.ListItemControl(
    searchDepth=5,
    Compare=lambda c, d: c.Name and len(c.Name.strip()) > 0
)

# 특정 깊이에서만 검색
button = window.ButtonControl(
    Compare=lambda c, d: d == 2 and c.Name == '전송'
)

# 복합 조건
element = window.Control(
    Compare=lambda c, d: (
        c.ControlType == auto.ControlType.ButtonControl and
        c.Name and
        '전송' in c.Name and
        c.IsEnabled
    )
)
```

**활용 예시: 다국어 버튼 찾기**

```python
# 확인/OK/Yes 버튼 찾기 (언어 무관)
CONFIRM_LABELS = ['확인', 'OK', 'Yes', '예', 'Confirm']
confirm_btn = window.ButtonControl(
    searchDepth=5,
    Compare=lambda c, d: c.Name in CONFIRM_LABELS
)
```

**Compare vs 여러 번 검색**

```python
# 방법 1: Compare로 한 번에 검색 (권장)
button = window.ButtonControl(
    Compare=lambda c, d: c.Name in ['확인', 'OK']
)

# 방법 2: 여러 번 검색 (느릴 수 있음)
button = window.ButtonControl(Name='확인')
if not button.Exists(timeout=0.1):
    button = window.ButtonControl(Name='OK')
```

## 6.4 주요 메서드

### 존재/상태 확인

```python
control.Exists(maxSearchSeconds=5, searchIntervalSeconds=0.5)
control.IsEnabled
control.IsOffscreen
control.HasKeyboardFocus
```

### 속성 조회

```python
control.Name
control.ControlType
control.ControlTypeName
control.AutomationId
control.ClassName
control.ProcessId
control.BoundingRectangle  # (left, top, right, bottom)
```

### 트리 탐색

```python
control.GetParentControl()
control.GetChildren()
control.GetFirstChildControl()
control.GetLastChildControl()
control.GetNextSiblingControl()
control.GetPreviousSiblingControl()
```

### 상호작용

```python
# 기본 동작
control.Click(x=None, y=None, simulateMove=True)
control.DoubleClick()
control.RightClick()
control.MiddleClick()

# 포커스
control.SetFocus()

# 키 입력
control.SendKeys(text, interval=0.01)
control.SendKeys('{Enter}')  # 특수키

# 스크롤
control.WheelUp(wheelTimes=3)
control.WheelDown(wheelTimes=3)
```

### 패턴 접근

```python
# Invoke 패턴
control.GetInvokePattern().Invoke()

# Value 패턴
pattern = control.GetValuePattern()
value = pattern.Value
pattern.SetValue("새 값")

# Selection 패턴
pattern = control.GetSelectionPattern()
selected = pattern.GetSelection()

# SelectionItem 패턴
control.GetSelectionItemPattern().Select()

# Toggle 패턴
control.GetTogglePattern().Toggle()

# ExpandCollapse 패턴
control.GetExpandCollapsePattern().Expand()
control.GetExpandCollapsePattern().Collapse()

# Text 패턴
pattern = control.GetTextPattern()
text = pattern.DocumentRange.GetText()
```

## 6.5 전역 함수

```python
# 루트(데스크톱) 컨트롤
auto.GetRootControl()

# 포커스된 컨트롤
auto.GetFocusedControl()

# 마우스 위치의 컨트롤
auto.GetCursorControl()

# 특정 좌표의 컨트롤
auto.ControlFromPoint(x, y)

# 타임아웃 설정
auto.SetGlobalSearchTimeout(10)  # 초

# 마우스 위치
auto.GetCursorPos()  # (x, y)
auto.SetCursorPos(x, y)

# 클립보드
auto.GetClipboardText()
auto.SetClipboardText("텍스트")
```

## 6.6 특수키 코드

```python
# SendKeys에서 사용하는 특수키
{Enter}     # Enter
{Tab}       # Tab
{Escape}    # ESC
{Space}     # 스페이스
{Back}      # Backspace
{Delete}    # Delete
{Up}        # ↑
{Down}      # ↓
{Left}      # ←
{Right}     # →
{Home}      # Home
{End}       # End
{PageUp}    # Page Up
{PageDown}  # Page Down
{F1}~{F12}  # 함수키

# 조합키
{Ctrl}a     # Ctrl+A
{Alt}f      # Alt+F
{Shift}a    # Shift+A
{Ctrl}{Shift}s  # Ctrl+Shift+S
{Win}       # Windows 키
```

## 6.7 설정

```python
# 전역 타임아웃 (기본 10초)
auto.SetGlobalSearchTimeout(15)

# 로그 활성화
auto.Logger.SetLevel(auto.LogLevel.Debug)

# 화면 캡처
control.CaptureToImage('screenshot.png')
```

---

# 7. UIA 문제 해결 가이드

## UIA 예외 클래스

UIA 작업 중 발생하는 주요 예외:

| 예외 (.NET) | 발생 상황 | Python 매핑 |
|-------------|----------|-------------|
| `ElementNotAvailableException` | 요소가 더 이상 존재하지 않음 (창 닫힘, 동적 UI 변경) | `COMError` 또는 `LookupError` |
| `ElementNotEnabledException` | 비활성 요소 조작 시도 | `COMError` |
| `NoClickablePointException` | `GetClickablePoint()` 실패 (가려지거나 화면 밖) | `COMError` |

**Python에서의 처리**

```python
import uiautomation as auto
from comtypes import COMError

try:
    button = window.ButtonControl(Name='확인')
    button.Click()
except COMError as e:
    # 요소가 사라졌거나 접근 불가
    print(f"UIA 오류: {e}")
except LookupError:
    # 요소를 찾지 못함
    print("요소를 찾을 수 없음")
```

## 7.1 요소를 찾을 수 없음

### 증상
```python
control.Exists()  # False
# 또는
LookupError: Can't find control
```

### 원인과 해결

| 원인 | 해결 |
|------|------|
| **Name이 다름** | dump_tree로 실제 이름 확인 |
| **searchDepth 부족** | depth 늘리거나 단계적 탐색 |
| **창이 최소화됨** | 창 활성화 후 탐색 |
| **타이밍 문제** | `Exists(timeout=5)` 대기 |
| **UIA 미지원** | DirectUI/Custom 컨트롤은 이미지 인식 사용 |

### 디버깅 코드

```python
def find_with_debug(parent, name, control_type=None):
    """디버깅 정보와 함께 요소 찾기"""
    print(f"찾는 중: Name='{name}'")
    print(f"부모: {parent.Name} ({parent.ControlTypeName})")
    
    # 부모의 모든 자식 출력
    print("자식 목록:")
    for i, child in enumerate(parent.GetChildren()):
        print(f"  {i}: {child.Name or '(없음)'} | {child.ControlTypeName}")
    
    # 검색 시도
    if control_type:
        result = getattr(parent, control_type)(Name=name, searchDepth=3)
    else:
        result = parent.Control(Name=name, searchDepth=3)
    
    if result.Exists(timeout=2):
        print(f"찾음: {result.Name}")
        return result
    else:
        print("찾지 못함")
        return None
```

## 7.2 동적 UI 처리

### 문제: UI가 로딩 중

```python
# 나쁜 예
button = window.ButtonControl(Name='확인')
button.Click()  # 아직 버튼이 없으면 에러

# 좋은 예
button = window.ButtonControl(Name='확인')
if button.Exists(timeout=10):  # 최대 10초 대기
    button.Click()
```

### 문제: 요소가 생겼다 사라짐

```python
def wait_and_click(control, timeout=10, interval=0.5):
    """요소가 나타날 때까지 대기 후 클릭"""
    import time
    start = time.time()
    
    while time.time() - start < timeout:
        if control.Exists(timeout=0.1):
            if control.IsEnabled:
                control.Click()
                return True
        time.sleep(interval)
    
    return False
```

### 문제: 리스트 아이템이 동적 로드됨

```python
def scroll_and_find(list_control, item_name, max_scrolls=10):
    """스크롤하면서 아이템 찾기"""
    for _ in range(max_scrolls):
        item = list_control.ListItemControl(Name=item_name, searchDepth=1)
        if item.Exists(timeout=0.5):
            return item
        
        # 아래로 스크롤
        list_control.WheelDown(3)
        auto.time.sleep(0.3)
    
    return None
```

## 7.3 타이밍 이슈

### 문제: 너무 빠른 동작

```python
# 나쁜 예 - 메뉴가 열리기 전에 클릭
menu_button.Click()
menu_item.Click()  # 메뉴 안 열렸으면 실패

# 좋은 예
menu_button.Click()
auto.time.sleep(0.3)  # 메뉴 열리기 대기
if menu_item.Exists(timeout=2):
    menu_item.Click()
```

### 일반적인 대기 시간 가이드

| 동작 | 권장 대기 |
|------|----------|
| 창 열기 | 1~3초 |
| 메뉴 열기 | 0.2~0.5초 |
| 탭 전환 | 0.3~0.5초 |
| 리스트 로딩 | 0.5~2초 |
| 애니메이션 완료 | 0.3~1초 |

## 7.4 권한 및 보안 문제

### 증상
```
RuntimeError: Can not get an instance of IUIAutomation
```

### 해결

1. **관리자 권한으로 실행**
   ```powershell
   # PowerShell 관리자 모드로 실행
   uv run python script.py
   ```

2. **UAC 설정 확인**
   - 일부 앱은 관리자 권한 필요

3. **Windows 버전 확인**
   - XP는 KB971513 업데이트 필요 (레거시)

### UAC와 UIA 보안 모델

Windows Vista 이후 UAC(사용자 계정 컨트롤)가 UIA 접근에 영향을 미칩니다.

| 상황 | 접근 가능 여부 |
|------|---------------|
| 일반 앱 → 일반 앱 | ✅ 가능 |
| 일반 앱 → 관리자 앱 | ❌ 불가 (권한 상승 필요) |
| 관리자 앱 → 모든 앱 | ✅ 가능 |
| 일반 앱 → UAC 대화상자 | ❌ 불가 (보호됨) |

### 높은 권한이 필요한 상황

- 관리자 권한으로 실행된 앱 자동화
- UAC 동의 대화상자 접근
- 보호된 시스템 프로세스 접근
- Windows 로그온 화면 접근

### manifest 파일로 권한 요청

접근성 도구가 보호된 UI에 접근하려면 manifest 파일에 `uiAccess` 속성이 필요합니다:

```xml
<trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
  <security>
    <requestedPrivileges>
      <requestedExecutionLevel
        level="highestAvailable"
        uiAccess="true" />
    </requestedPrivileges>
  </security>
</trustInfo>
```

**uiAccess="true" 요구사항**:
- 애플리케이션이 디지털 서명되어야 함
- `Program Files` 또는 `Windows\System32` 등 보호된 경로에 설치
- 신뢰할 수 있는 인증서로 서명

**일반 자동화 스크립트**: `uiAccess`가 필요 없음. 관리자 권한 실행만으로 충분.

## 7.5 스레드 문제

### 스레딩 충돌의 원인

UIA는 Windows 메시지를 사용하여 통신합니다. 클라이언트가 자신의 UI 스레드에서 UIA를 호출하면 메시지 처리가 충돌하여 성능 저하나 응답 중지가 발생할 수 있습니다.

### 권장 스레딩 전략

| 상황 | 권장 방식 |
|------|----------|
| GUI 앱에서 UIA 호출 | 별도 작업 스레드 사용 |
| 콘솔 스크립트 | 메인 스레드 사용 가능 |
| 이벤트 핸들러 내부 | 안전 (비-UI 스레드에서 호출됨) |

### 문제: 다른 스레드에서 UIA 사용

```python
# 나쁜 예 - 스레드에서 바로 사용
import threading

def worker():
    window = auto.WindowControl(Name='카카오톡')  # 에러 가능!

threading.Thread(target=worker).start()
```

### 해결: UIAutomationInitializerInThread 사용

```python
import threading
import uiautomation as auto

def worker():
    # 스레드에서 UIA 사용 시 반드시 필요
    with auto.UIAutomationInitializerInThread():
        window = auto.WindowControl(Name='카카오톡')
        if window.Exists():
            print(f"찾음: {window.Name}")

thread = threading.Thread(target=worker)
thread.start()
thread.join()
```

### COM 초기화 (pythoncom 직접 사용 시)

`uiautomation` 패키지 대신 `comtypes`를 직접 사용할 때:

```python
import pythoncom
import threading

def worker():
    pythoncom.CoInitialize()  # COM 초기화
    try:
        # UIA 작업 수행
        pass
    finally:
        pythoncom.CoUninitialize()  # 반드시 정리

thread = threading.Thread(target=worker)
thread.start()
```

### 이벤트 핸들러와 스레드

- **이벤트 핸들러 내 UIA 호출**: 안전 (항상 비-UI 스레드에서 호출됨)
- **이벤트 구독/해제**: 비-UI 스레드에서 수행 권장
- **핸들러 등록과 해제**: 같은 스레드에서 수행

### 주의사항

- 메인 스레드에서 만든 Control 객체는 다른 스레드에서 사용 불가
- 각 스레드에서 새로 찾아야 함
- daemon 스레드 사용 시 `finally`에서 COM 정리 보장

## 7.6 성능 최적화

### 문제: 탐색이 너무 느림

```python
# 나쁜 예 - 매번 전체 탐색
for _ in range(100):
    button = auto.ButtonControl(searchDepth=0xFFFFFFFF, Name='확인')
    button.Click()

# 좋은 예 - 캐싱 활용
button = auto.ButtonControl(searchDepth=0xFFFFFFFF, Name='확인')
for _ in range(100):
    if button.Exists(timeout=0.1):
        button.Click()
    else:
        button.Refind()  # 필요 시만 재탐색
```

### 탐색 경로 최적화

```python
# 나쁜 예 - 루트에서 깊은 탐색
deep_button = auto.ButtonControl(searchDepth=10, Name='확인')

# 좋은 예 - 단계적 탐색
window = auto.WindowControl(searchDepth=1, Name='카카오톡')
toolbar = window.ToolBarControl(searchDepth=2)
button = toolbar.ButtonControl(searchDepth=1, Name='확인')
```

## 7.7 자주 겪는 문제 FAQ

### Q: Exists()는 True인데 Click()이 안 됨
**A:** 
- 요소가 화면 밖에 있을 수 있음 → 스크롤 필요
- 다른 요소에 가려져 있을 수 있음 → 창 활성화
- 비활성화 상태일 수 있음 → `IsEnabled` 확인

### Q: Name이 자꾸 바뀜
**A:**
- AutomationId 사용 (더 안정적)
- SubName으로 부분 일치 사용
- ControlType + 위치 조합 사용

### Q: 한글이 깨짐
**A:**
```python
# 파일 저장 시 인코딩 지정
with open('output.txt', 'w', encoding='utf-8') as f:
    f.write(control.Name)
```

### Q: 멀티모니터에서 좌표가 이상함
**A:**
```python
# BoundingRectangle은 가상 좌표 반환
rect = control.BoundingRectangle
# 음수 값이 나올 수 있음 (보조 모니터)
print(f"좌표: {rect}")
```

---

# 8. 커스텀 UI 앱 실전 대응

## 8.1 개요

카카오톡, 게임 클라이언트 등 커스텀 UI 프레임워크를 사용하는 앱은 표준 UIA 패턴을 따르지 않는 경우가 많다.

### 흔한 문제들

| 문제 | 설명 | 대응 |
|------|------|------|
| **빈 ListItem 대량 발생** | 가상 스크롤로 인한 placeholder | 스마트 필터링 |
| **ClassName 부재** | 대부분 컨트롤에 클래스 미지정 | Name + ControlType 조합 |
| **AutomationId 불규칙** | 숫자만, 내용 복제, 빈값 혼재 | AutomationId 의존 최소화 |
| **메뉴 탐색 불안정** | 팝업 메뉴 즉시 감지 안 됨 | 적응형 재시도 |
| **UIA 미노출 영역** | DirectUI/CustomDraw | 이미지 인식 대체 |

## 8.2 가상 스크롤/빈 요소 필터링

### 문제 상황

```
[ListItemControl] Name: "실제 메시지 1"
[ListItemControl] Name: "실제 메시지 2"
[ListItemControl] Name: (no name)    ← 빈 항목 시작
[ListItemControl] Name: (no name)
... (100개 이상 연속)
```

### 원인
- 성능 최적화를 위한 가상화 (virtualization)
- 화면에 보이지 않는 영역은 placeholder로 대체
- UIA는 이 placeholder도 노출함

### 대응 패턴

```python
def filter_virtual_list(parent: auto.Control, max_items: int = 100) -> list:
    """가상 스크롤 리스트 필터링"""
    children = parent.GetChildren()
    valid_items = []
    consecutive_empty = 0
    MAX_CONSECUTIVE_EMPTY = 15  # 연속 빈 항목 한계
    
    for child in children:
        if len(valid_items) >= max_items:
            break
        
        name = child.Name
        is_empty = not name or not name.strip()
        
        if is_empty:
            consecutive_empty += 1
            # 조기 종료: 유효 항목 발견 후 연속 빈 항목 초과
            if valid_items and consecutive_empty > MAX_CONSECUTIVE_EMPTY:
                break
        else:
            valid_items.append(child)
            consecutive_empty = 0
    
    return valid_items
```

### 캐싱으로 성능 개선

```python
class VirtualListNavigator:
    def __init__(self):
        # 마지막 유효 범위 캐싱
        self._valid_range: tuple = None  # (start_idx, end_idx)
    
    def get_items(self, parent):
        children = parent.GetChildren()
        
        # 캐시된 범위 먼저 검사 (빠른 경로)
        if self._valid_range:
            start, end = self._valid_range
            # 캐시 범위 내에서 먼저 검색
            ...
```

## 8.3 ClassName 없는 환경 탐색

### 문제 상황

```python
# 실패: ClassName이 없어서 찾지 못함
button = window.ButtonControl(ClassName='Button', Name='전송')
```

### 대응 전략

**1. Name + ControlType 조합**
```python
# ClassName 대신 Name으로 검색
button = window.ButtonControl(Name='전송', searchDepth=5)

# 또는 SubName으로 부분 일치
button = window.ButtonControl(SubName='전송', searchDepth=5)
```

**2. 계층적 탐색**
```python
# 부모 → 자식 순서로 좁혀가기
toolbar = window.ToolBarControl(searchDepth=3)
button = toolbar.ButtonControl(Name='전송', searchDepth=2)
```

**3. 인덱스 기반 (최후의 수단)**
```python
# 구조가 고정적일 때만 사용
buttons = toolbar.GetChildren()
send_button = buttons[2]  # 3번째 버튼이 전송
```

### 안정적인 식별자 우선순위

```
1. AutomationId (있다면)
2. Name + ControlType
3. SubName + ControlType
4. 부모 경로 + 인덱스
5. 화면 좌표 (최후)
```

## 8.4 메뉴 탐색 안정화

### 문제 상황
- 우클릭 후 메뉴가 UIA에 즉시 노출되지 않음
- 고정 대기 시간으로는 불안정

### 적응형 재시도 패턴

```python
class AdaptiveRetry:
    """적응형 재시도"""
    
    def __init__(self):
        self.success_count = 0
        self.fail_count = 0
        self.total_wait_ms = 0
    
    def find_with_retry(
        self,
        find_func,
        max_retries: int = 7,
        initial_delay_ms: int = 150,
        backoff_factor: float = 1.5
    ):
        delay_ms = initial_delay_ms
        
        for attempt in range(max_retries):
            result = find_func()
            
            if result:
                self.success_count += 1
                return result
            
            # 지수 백오프
            time.sleep(delay_ms / 1000)
            self.total_wait_ms += delay_ms
            delay_ms = min(delay_ms * backoff_factor, 500)
        
        self.fail_count += 1
        return None
```

### 다중 방법 시도

```python
def find_popup_menu():
    """여러 방법으로 메뉴 찾기"""
    root = auto.GetRootControl()
    
    methods = [
        # 방법 1: 특정 클래스 깊은 검색
        lambda: root.MenuControl(searchDepth=10, ClassName='EVA_Menu'),
        # 방법 2: 앱 창 내부에서 검색
        lambda: find_in_app_windows(),
        # 방법 3: 일반 MenuControl
        lambda: root.MenuControl(searchDepth=10),
    ]
    
    for method in methods:
        try:
            result = method()
            if result and result.Exists(timeout=0.05):
                return result
        except:
            continue
    
    return None
```

## 8.5 UIA 미노출 영역 대응

### 문제
- 일부 커스텀 컨트롤은 UIA로 접근 불가
- 예: 카카오톡 공감 이모지

### 대체 방안

**1. 이미지 인식 (OpenCV)**
```python
import cv2
import pyautogui

def find_emoji_by_image(template_path: str):
    """템플릿 매칭으로 이모지 위치 찾기"""
    screenshot = pyautogui.screenshot()
    screenshot_np = np.array(screenshot)
    
    template = cv2.imread(template_path)
    result = cv2.matchTemplate(screenshot_np, template, cv2.TM_CCOEFF_NORMED)
    
    threshold = 0.8
    locations = np.where(result >= threshold)
    
    return list(zip(*locations[::-1]))  # (x, y) 리스트
```

**2. 좌표 기반 클릭**
```python
def click_relative_to_element(element: auto.Control, offset_x: int, offset_y: int):
    """요소 기준 상대 좌표 클릭"""
    rect = element.BoundingRectangle
    center_x = (rect[0] + rect[2]) // 2
    center_y = (rect[1] + rect[3]) // 2
    
    pyautogui.click(center_x + offset_x, center_y + offset_y)
```

## 8.6 성능 프로파일링

### 병목 지점 파악

```python
import time
from contextlib import contextmanager

@contextmanager
def measure(operation: str):
    start = time.perf_counter()
    yield
    elapsed_ms = (time.perf_counter() - start) * 1000
    if elapsed_ms > 100:  # 100ms 이상이면 경고
        print(f"⚠️ SLOW: {operation} took {elapsed_ms:.1f}ms")

# 사용
with measure("find_chat_list"):
    chat_list = window.ListControl(searchDepth=6)
```

### 로깅 권장 항목

```python
# UIA 검색마다 로깅
log.info(f"UIA Search: {control_type}({params}) → {result_count} results, {elapsed_ms:.0f}ms")

# 리스트 필터링 로깅
log.info(f"ListItems: total={total}, empty={empty}, valid={valid}, {elapsed_ms:.0f}ms")

# 재시도 로깅
log.info(f"Retry {attempt}/{max}: method={method_name}, success={success}")
```

## 8.7 커스텀 앱 대응 체크리스트

새로운 앱 자동화 시작 시:

- [ ] **UIA 트리 덤프**: `dump_tree(app_window, max_depth=6)`
- [ ] **ClassName 확인**: 대부분 비어있는지
- [ ] **AutomationId 패턴**: 규칙적인지, 신뢰할 수 있는지
- [ ] **가상 스크롤 여부**: 리스트에 빈 항목 많은지
- [ ] **동적 UI 여부**: 로딩/애니메이션 있는지
- [ ] **UIA 미노출 영역**: 커스텀 드로잉 있는지
- [ ] **메뉴/팝업 동작**: 즉시 감지되는지

---

# 부록: 용어 정리

| 용어 | 설명 |
|------|------|
| **UIA** | UI Automation, Windows 접근성/자동화 API |
| **Provider** | UI 정보를 제공하는 쪽 (앱) |
| **Client** | UI 정보를 소비하는 쪽 (자동화 도구) |
| **Automation Element** | UIA의 기본 요소 단위 |
| **ControlType** | 컨트롤 종류 (Button, Edit 등) |
| **Control Pattern** | 컨트롤 기능 (Invoke, Value 등) |
| **Tree View** | UI 계층 구조 (Raw/Control/Content) |
| **MSAA** | Microsoft Active Accessibility (구형) |
| **AT** | Assistive Technology (보조 기술) |

---

# 참고 자료

## Microsoft UI Automation 공식 문서

- [UI Automation Overview](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-overview)
- [Caching in UI Automation Clients](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/caching-in-ui-automation-clients)
- [UI Automation Threading Issues](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-threading-issues)
- [Obtaining UI Automation Elements](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/obtaining-ui-automation-elements)
- [UI Automation Control Patterns](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-control-patterns)
- [UI Automation Properties Overview](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-properties-overview)
- [UI Automation Events Overview](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-events-overview)
- [UI Automation Security Overview](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-security-overview)
- [Windows Automation API (Win32)](https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32)

## Python 라이브러리

- [uiautomation GitHub](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows)
- [pywinauto 문서](https://pywinauto.readthedocs.io/)
