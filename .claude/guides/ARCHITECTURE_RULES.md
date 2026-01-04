# 아키텍처 규칙

코드 추가/수정 전 반드시 확인할 규칙. 이 규칙을 따르면 기존 아키텍처와 일관성 유지.

---

## 1. 계층 규칙

### 계층 구조

```
GUI (wxPython)           ← 사용자 인터페이스
    ↓
Application (main.py)    ← 모드 관리, 포커스 모니터링
    ↓
Domain                   ← 비즈니스 로직
    ↓
Infrastructure           ← UIA, Win32 API, 로깅
```

### 의존 방향
- **상위 → 하위만 허용** (GUI → Application → Domain → Infrastructure)
- **역방향 금지**: Infrastructure에서 Domain import 금지
- **역방향 통신**: 콜백/이벤트 패턴 사용

### 계층별 모듈

| 계층 | 모듈 |
|------|------|
| GUI | gui/app.py, gui/main_frame.py, gui/tray_icon.py |
| Application | main.py |
| Domain | navigation/, detector.py, hotkeys.py, clicker.py, mouse_hook.py, settings.py |
| Infrastructure | utils/uia_*.py, utils/debug.py, window_finder.py, accessibility.py |

### 순환 import 방지

```python
# 타입 힌트용 import는 TYPE_CHECKING 가드 사용
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chat_room import ChatRoomNavigator
```

---

## 2. 스레딩 규칙

### COM 초기화 (필수)

UIA 사용하는 스레드는 **반드시** COM 초기화.

```python
# 방법 1: 컨텍스트 매니저 (권장)
from ..utils.com_utils import com_thread

with com_thread():
    control = auto.ControlFromHandle(hwnd)

# 방법 2: 수동 초기화
import pythoncom

def my_thread_func():
    pythoncom.CoInitialize()
    try:
        control = auto.GetFocusedControl()
    finally:
        pythoncom.CoUninitialize()

# 방법 3: 데코레이터
from ..utils.com_utils import ensure_com_initialized

@ensure_com_initialized
def find_element():
    return auto.WindowControl(Name='창')
```

### GUI 업데이트

GUI 스레드 외에서 GUI 업데이트 시 **wx.CallAfter()** 사용.

```python
# 잘못된 방법 (크래시)
def on_event(data):
    self.label.SetLabel(data)

# 올바른 방법
def on_event(data):
    wx.CallAfter(self.label.SetLabel, data)
```

### 새 스레드 생성

```python
thread = threading.Thread(
    target=my_func,
    daemon=True  # 프로그램 종료 시 자동 정리
)
thread.start()
```

---

## 3. UIA 접근 규칙

### safe_uia_call 래핑

모든 UIA 호출은 `safe_uia_call()` 또는 `@handle_uia_errors` 사용.

```python
from ..utils.uia_utils import safe_uia_call, handle_uia_errors

# 방법 1: 함수 호출
name = safe_uia_call(lambda: control.Name, default="")

# 방법 2: 데코레이터
@handle_uia_errors(default_return=[])
def get_children(control):
    return control.GetChildren()
```

### searchDepth 제한

기본값 10은 과도함. 용도에 맞게 최소화.

| 용도 | searchDepth |
|------|-------------|
| 메시지 목록 | 4 |
| 채팅 목록 | 6 |
| 일반 탐색 | 6 (최대) |

```python
msg_list = safe_uia_call(
    lambda: chat_control.ListControl(Name="메시지", searchDepth=4),
    default=None
)
```

### 캐싱 사용

반복 접근은 UIACache 사용.

```python
from ..utils.uia_cache import message_list_cache, menu_cache

# 캐시 키: hwnd 또는 고유 식별자 포함
cache_key = f"messages_{hwnd}"

# 캐시 확인
cached = message_list_cache.get(cache_key)
if cached:
    return cached

# 캐시 저장 (TTL 기본 1.0초)
message_list_cache.set(cache_key, messages)
```

### 캐시 종류

| 캐시 | TTL | 용도 |
|------|-----|------|
| message_list_cache | 1.0s | 채팅방 메시지 목록 |
| menu_cache | 0.5s | 팝업 메뉴 항목 |
| window_cache | 1.0s | 윈도우 핸들 |

---

## 4. 상태 관리 규칙

### 모드 플래그

main.py의 모드 플래그는 직접 수정하지 말고 전용 메서드 사용.

```python
# 잘못된 방법
self._in_selection_mode = True

# 올바른 방법
self._enter_selection_mode()
self._exit_selection_mode()
```

### 상호 배제 규칙

| 모드 | 조건 |
|------|------|
| selection_mode | 이모지 탐지 후 선택 대기 중 |
| navigation_mode | 채팅방 활성 + 탐색 중 |
| context_menu_mode | 팝업 메뉴 열림 |

- context_menu_mode가 가장 높은 우선순위
- selection_mode와 navigation_mode는 동시 가능

---

## 5. 에러 처리 규칙

### COMError 처리

UIA 호출은 **항상** safe_uia_call로 래핑.

```python
# 잘못된 방법
name = control.Name  # COMError 가능

# 올바른 방법
name = safe_uia_call(lambda: control.Name, default="")
```

### bare except 금지

```python
# 잘못된 방법
except:
    pass

# 올바른 방법
except Exception as e:
    log.trace(f"예외 발생: {e}")
```

### 폴백 전략

중요 기능은 폴백 제공.

```python
# 이벤트 실패 시 폴링으로 폴백
if self._use_events:
    success = self._start_event_based()
    if not success:
        self._use_events = False

if not self._use_events:
    self._start_polling()
```

---

## 6. 로깅 규칙

### 로그 레벨 사용

| 레벨 | 용도 | 예시 |
|------|------|------|
| TRACE | 고빈도 루프 상태 | 포커스 변경 감지, 메뉴 모드 진입/종료 |
| DEBUG | 상태 변경 | 채팅방 진입, 메시지 개수 |
| INFO | 모드 전환 | 선택 모드 활성화 |
| WARNING | 복구 가능 문제 | 캐시 미스, 타임아웃 |
| ERROR | 치명적 오류 | COM 초기화 실패 |

```python
from ..utils.debug import get_logger
log = get_logger(__name__)

log.trace("포커스 변경 감지")
log.debug(f"메시지 {count}개 로드")
log.info("채팅방 네비게이션 모드 진입")
log.warning("UIA 캐시 미스")
log.error("COM 초기화 실패")
```

---

## 7. 파일 구조 규칙

### 새 모듈 추가 시

1. 계층 결정 (GUI/Application/Domain/Infrastructure)
2. 해당 디렉토리에 파일 생성
3. `__init__.py`에 export 추가 (필요시)
4. 의존성 방향 확인

### 새 유틸리티 추가 시

`utils/` 디렉토리에 추가. 파일명 접두어 규칙:

| 접두어 | 용도 |
|--------|------|
| uia_* | UIA 관련 |
| debug* | 디버깅 관련 |
| com_* | COM 관련 |

---

## 체크리스트 요약

### 새 코드 추가 전
- [ ] 계층 확인
- [ ] 의존 방향 확인
- [ ] COM 초기화 필요 여부

### UIA 코드 작성 시
- [ ] safe_uia_call 래핑
- [ ] searchDepth 명시
- [ ] 캐시 고려

### 스레드 코드 작성 시
- [ ] pythoncom.CoInitialize/Uninitialize
- [ ] daemon=True
- [ ] GUI 업데이트는 wx.CallAfter
