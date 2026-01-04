# 컨텍스트 메뉴 처리 개선안 상세 분석

> 작성일: 2026-01-04
> 분석 대상: 채팅방 메시지 컨텍스트 메뉴 vs 친구탭/채팅탭 컨텍스트 메뉴

---

## 1. 현재 상황 요약

### 1.1 왜 메시지 컨텍스트 메뉴가 특수한가

**친구탭/채팅탭:**
- FocusMonitor 단독 실행 (단일 STA)
- 메뉴 열면 카카오톡이 포커스 이동 → NVDA가 직접 읽음
- 이 프로그램은 개입 없음 (패스스루)

**채팅방 메시지:**
- FocusMonitor(STA1) + MessageListMonitor(STA2) 동시 실행
- 두 스레드가 동시에 UIA COM 서버 접근 시 충돌
- 7단계 위임 아키텍처로 해결 중

```
충돌 시나리오:
┌────────────────┐     ┌────────────────┐
│ FocusMonitor   │     │ MessageList    │
│ (STA1)         │     │ Monitor(STA2)  │
│                │     │                │
│ GetFocused     │     │ PumpWaiting    │
│ Control()  ────┼─────┼─→ Messages()   │
│                │     │                │
│      ↓         │     │      ↓         │
│  UIA COM 서버 ◀┼─────┼─→ 동시 접근    │
│      ↓         │     │                │
│  COMError!     │     │                │
└────────────────┘     └────────────────┘
```

### 1.2 현재 해결 아키텍처

```
메뉴 열림 감지
    ↓
enter_context_menu_mode()
    ↓
message_monitor.pause() ─→ 이벤트 핸들러 해제 (동기 200ms 대기)
    ↓
request_menu_read() ─→ 메뉴 읽기 작업 위임
    ↓
MessageListMonitor._process_menu_read() ─→ 동일 STA에서 UIA 호출
    ↓
콜백으로 결과 반환
    ↓
speak()
```

---

## 2. 개선안 A: NVDA 완전 위임

### 2.1 개념

메뉴 읽기를 이 프로그램에서 처리하지 않고, NVDA의 기본 동작에 맡긴다.

**현재 동작:**
```
메뉴 열림 → 이 프로그램이 메뉴 항목 읽기 → speak()
         → NVDA도 포커스 변경 감지 → 읽기 (중복 가능)
```

**개선 후:**
```
메뉴 열림 → NVDA가 포커스 변경 감지 → 읽기 (단일)
```

### 2.2 구현 상세

#### 변경 파일 1: `focus_monitor.py`

```python
# 제거할 메서드들

def _read_first_menu_item(self, menu_hwnd: int) -> None:
    """[삭제] 메뉴 열림 시 첫 번째 항목 즉시 읽기"""
    pass  # 또는 메서드 전체 삭제

def _read_first_menu_item_direct(self, menu_hwnd: int) -> None:
    """[삭제] 폴백용 직접 읽기"""
    pass

def _on_menu_item_read(self, name: str) -> None:
    """[삭제] 위임 결과 콜백"""
    pass
```

```python
# 수정할 부분 (162-193행)

# Before
if menu_hwnd:
    if not self._mode_manager.in_context_menu_mode:
        self._mode_manager.enter_context_menu_mode(self._message_monitor)
        self._read_first_menu_item(menu_hwnd)  # ← 삭제

    if not self._menu_read_pending:
        # 메뉴 항목 읽기 로직... ← 삭제

# After
if menu_hwnd:
    if not self._mode_manager.in_context_menu_mode:
        self._mode_manager.enter_context_menu_mode(self._message_monitor)
        # NVDA가 자동으로 읽음 - 추가 처리 불필요
```

#### 변경 파일 2: `utils/uia_events.py`

```python
# 제거할 메서드들 (493-555행)

def request_menu_read(self, menu_hwnd: int, callback: Callable[[str], None]) -> None:
    """[삭제] 메뉴 읽기 요청"""
    pass

def _process_menu_read(self) -> None:
    """[삭제] 메뉴 읽기 처리"""
    pass
```

```python
# 수정할 부분 - 이벤트 루프 (575-624행)

# Before
if self._pending_menu_hwnd:
    time.sleep(0.03)
    self._process_menu_read()

# After
# 해당 블록 삭제
```

#### 변경 파일 3: `navigation/message_monitor.py`

```python
# 제거할 메서드 (112-128행)

def request_menu_read(self, menu_hwnd: int, callback: Callable[[str], None]) -> None:
    """[삭제] FocusMonitor 래퍼"""
    pass
```

#### 변경 파일 4: `focus_monitor.py` 멤버 변수

```python
# 제거할 멤버 변수
self._menu_read_pending: bool  # 삭제
```

### 2.3 영향 범위

| 파일 | 변경 유형 | 줄 수 |
|------|----------|-------|
| `focus_monitor.py` | 메서드 3개 삭제, 호출부 수정 | -80줄 |
| `uia_events.py` | 메서드 2개 삭제, 루프 수정 | -60줄 |
| `message_monitor.py` | 메서드 1개 삭제 | -15줄 |
| **합계** | | **-155줄** |

### 2.4 유지되는 부분

- `pause()/resume()`: COM 충돌 방지용으로 여전히 필요
- `enter_context_menu_mode()/exit_context_menu_mode()`: 모드 관리 유지
- Grace Period/Debounce: 메뉴 전환 안정성용 유지
- 마우스 훅: 비메시지 항목 차단 유지

### 2.5 예상 부작용

| 부작용 | 심각도 | 대응책 |
|--------|--------|--------|
| NVDA 없으면 메뉴 읽기 불가 | 낮음 | 이미 NVDA 필수 환경 |
| KAKAO-002 (UIA Name 없음) | 중간 | NVDA도 동일 문제, 별도 해결 필요 |
| 메뉴 항목 읽기 타이밍 변화 | 낮음 | NVDA가 더 안정적일 수 있음 |

### 2.6 테스트 방법

```
1. 채팅방 진입
2. 메시지에 포커스
3. Apps 키 또는 우클릭으로 메뉴 열기
4. 확인 사항:
   - [ ] NVDA가 첫 번째 메뉴 항목 읽는지
   - [ ] 화살표 키로 이동 시 각 항목 읽는지
   - [ ] 하위 메뉴 진입 시 정상 읽는지
   - [ ] ESC로 메뉴 닫을 때 오류 없는지
```

### 2.7 마이그레이션 전략

**단계 1: 비활성화 테스트 (1일)**
```python
def _read_first_menu_item(self, menu_hwnd: int) -> None:
    return  # 임시 비활성화
```

**단계 2: 테스트 통과 시 코드 제거 (1일)**
- 관련 메서드 삭제
- 멤버 변수 정리
- import 정리

**단계 3: 문서 업데이트**
- ARCHITECTURE.md 수정
- 이 문서에 결과 기록

---

## 3. 개선안 B: pause 최적화

### 3.1 개념

현재 `pause()`는 이벤트 핸들러를 해제하고 동기적으로 완료를 대기한다. 이를 콜백만 무시하는 경량 버전으로 대체한다.

**현재:**
```python
def pause(self):
    self._pending_unregister = True  # 핸들러 해제 요청
    self._pause_complete.wait(0.2)   # 200ms 동기 대기
```

**개선 후:**
```python
def pause_light(self):
    self._ignore_callbacks = True    # 콜백만 무시
    # 핸들러 유지, 대기 없음
```

### 3.2 구현 상세

#### 변경 파일: `utils/uia_events.py`

```python
class MessageListMonitor:
    def __init__(self):
        # 기존 멤버
        self._paused: bool = False
        self._pending_unregister: bool = False
        self._pending_register: bool = False

        # 추가 멤버
        self._ignore_callbacks: bool = False  # 새로 추가

    def pause_light(self) -> None:
        """경량 일시 중지 - 콜백만 무시

        이벤트 핸들러는 유지하여 재등록 오버헤드 없음.
        메뉴 열릴 때처럼 짧은 중단에 적합.
        """
        if not self._ignore_callbacks:
            self._ignore_callbacks = True
            self._pause_time = time.time()
            log.trace("MessageListMonitor 경량 일시 중지")

    def resume_light(self) -> None:
        """경량 재개"""
        if self._ignore_callbacks:
            elapsed = time.time() - self._pause_time
            if elapsed < TIMING_RESUME_DEBOUNCE:
                log.trace(f"resume_light 무시 (debounce)")
                return
            self._ignore_callbacks = False
            log.trace("MessageListMonitor 경량 재개")

    # 콜백 처리 부분 수정
    def _on_structure_changed(self, change_type: int) -> None:
        """StructureChanged 이벤트 콜백"""
        # 경량 일시 중지 상태면 무시
        if self._ignore_callbacks:
            return

        # 기존 로직...
```

#### 변경 파일: `mode_manager.py`

```python
def enter_context_menu_mode(self, message_monitor: "MessageMonitor") -> None:
    if self._in_context_menu_mode:
        return

    self._in_context_menu_mode = True
    self._menu_closed_time = time.time()

    # 변경: pause() → pause_light()
    if message_monitor and message_monitor.is_running():
        message_monitor.pause_light()  # 경량 버전 사용
    log.trace("메뉴 모드 진입")

def exit_context_menu_mode(self, message_monitor: "MessageMonitor") -> None:
    if not self._in_context_menu_mode:
        return

    self._in_context_menu_mode = False
    self._menu_closed_time = time.time()

    # 변경: resume() → resume_light()
    if message_monitor and message_monitor.is_running():
        message_monitor.resume_light()  # 경량 버전 사용
    log.trace("메뉴 모드 종료")
```

### 3.3 영향 범위

| 파일 | 변경 유형 | 줄 수 |
|------|----------|-------|
| `uia_events.py` | 메서드 2개 추가, 콜백 수정 | +30줄 |
| `mode_manager.py` | 호출부 변경 | ±0줄 |

### 3.4 예상 부작용

| 부작용 | 심각도 | 대응책 |
|--------|--------|--------|
| 이벤트는 계속 수신 | 낮음 | CPU 영향 미미 (콜백만 무시) |
| 기존 pause()와 혼재 | 중간 | 사용처 명확히 구분 필요 |

### 3.5 테스트 방법

```
1. 채팅방 진입
2. 메시지 메뉴 열기/닫기 반복 (10회)
3. 확인 사항:
   - [ ] 메뉴 열 때 지연 없음
   - [ ] 메뉴 닫은 후 새 메시지 자동 읽기 정상
   - [ ] 빠르게 열고 닫을 때 오류 없음
```

### 3.6 마이그레이션 전략

**단계 1: 병행 운영**
- `pause_light()/resume_light()` 추가
- 기존 `pause()/resume()` 유지
- 메뉴 모드에서만 light 버전 사용

**단계 2: 모니터링**
- 2주간 안정성 확인
- 문제 발생 시 기존 방식으로 롤백

**단계 3: 기존 pause 정리 (선택)**
- 사용처 없으면 제거
- 다른 용도 있으면 유지

---

## 4. 개선안 C: CacheRequest 확대 적용

### 4.1 개념

현재 FocusMonitor에서 사용하는 CacheRequest를 메뉴 읽기에도 적용하여 COM 호출을 줄인다.

**현재:**
```python
# uia_events.py - _process_menu_read()
focused = auto.GetFocusedControl()  # COM 호출 1
name = focused.Name                  # COM 호출 2
control_type = focused.ControlTypeName  # COM 호출 3
```

**개선 후:**
```python
cached = get_focused_with_cache()  # COM 호출 1 (캐시로 속성 포함)
name = cached.name                  # 캐시된 값
control_type = cached.control_type_name  # 캐시된 값
```

### 4.2 구현 상세

#### 변경 파일: `utils/uia_events.py`

```python
from kakaotalk_a11y_client.utils.uia_cache_request import get_focused_with_cache

def _process_menu_read(self) -> None:
    """이벤트 루프에서 메뉴 읽기 처리"""
    if not self._pending_menu_hwnd:
        return

    hwnd = self._pending_menu_hwnd
    callback = self._menu_read_callback
    self._pending_menu_hwnd = None
    self._menu_read_callback = None

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # 변경: CacheRequest 사용
            cached = get_focused_with_cache()
            if cached and cached.control_type_name == 'MenuItemControl':
                name = cached.name
                if name and callback:
                    callback(name)
                    log.trace(f"메뉴 첫 항목 읽기 (캐시): {name[:30]}...")
                    return

            # 폴백: 메뉴 컨트롤에서 직접 검색
            # (기존 로직 유지)
            ...
```

### 4.3 영향 범위

| 파일 | 변경 유형 | 줄 수 |
|------|----------|-------|
| `uia_events.py` | import 추가, 호출 변경 | +5줄 |

### 4.4 의존성

- `uia_cache_request.py`가 이미 존재하고 동작 중
- `get_focused_with_cache()` 함수 사용

### 4.5 예상 효과

| 항목 | Before | After |
|------|--------|-------|
| 메뉴 항목 읽기 COM 호출 | 3회 | 1회 |
| 재시도 시 COM 호출 | 9회 (3x3) | 3회 (1x3) |

### 4.6 테스트 방법

```
1. --debug 모드로 실행
2. 메시지 메뉴 열기
3. 로그 확인:
   - [ ] "메뉴 첫 항목 읽기 (캐시)" 메시지 출력
   - [ ] COM 관련 오류 없음
```

---

## 5. 개선안 D: 단일 스레드 아키텍처

### 5.1 개념

FocusMonitor와 MessageListMonitor를 단일 스레드(단일 STA)로 통합하여 COM 충돌 원천 차단.

### 5.2 구현 상세

#### 새 파일: `unified_monitor.py`

```python
"""통합 모니터 - 단일 STA에서 포커스 + 이벤트 처리"""

import threading
import time
from typing import Optional, Callable

import pythoncom
import uiautomation as auto

from kakaotalk_a11y_client.config import (
    TIMING_MENU_MODE_POLL_INTERVAL,
    TIMING_NORMAL_POLL_INTERVAL,
)
from kakaotalk_a11y_client.utils.uia_cache_request import get_focused_with_cache
from kakaotalk_a11y_client.window_finder import find_kakaotalk_menu_window


class UnifiedMonitor:
    """포커스 + 메시지 이벤트 통합 모니터

    단일 STA에서 실행되어 COM 충돌 없음.
    """

    def __init__(
        self,
        on_focus_change: Callable[[str], None],
        on_new_message: Callable[[str], None],
    ):
        self._on_focus_change = on_focus_change
        self._on_new_message = on_new_message

        self._running = False
        self._thread: Optional[threading.Thread] = None

        # 상태
        self._in_menu_mode = False
        self._last_focused_name = ""
        self._event_handler = None

    def start(self) -> None:
        """모니터 시작"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._event_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """모니터 중지"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _event_loop(self) -> None:
        """이벤트 루프 - 단일 STA"""
        pythoncom.CoInitialize()

        try:
            self._register_events()

            while self._running:
                # 1. COM 이벤트 펌프
                pythoncom.PumpWaitingMessages()

                # 2. 메뉴 상태 확인
                menu_hwnd = find_kakaotalk_menu_window()
                if menu_hwnd:
                    if not self._in_menu_mode:
                        self._in_menu_mode = True
                        self._unregister_events()  # 이벤트 일시 해제
                    self._poll_interval = TIMING_MENU_MODE_POLL_INTERVAL
                else:
                    if self._in_menu_mode:
                        self._in_menu_mode = False
                        self._register_events()  # 이벤트 재등록
                    self._poll_interval = TIMING_NORMAL_POLL_INTERVAL

                # 3. 포커스 확인
                self._check_focus()

                time.sleep(self._poll_interval)

        finally:
            self._unregister_events()
            pythoncom.CoUninitialize()

    def _check_focus(self) -> None:
        """포커스 변경 확인 (동일 STA → 안전)"""
        try:
            cached = get_focused_with_cache()
            if cached and cached.name != self._last_focused_name:
                self._last_focused_name = cached.name
                if self._on_focus_change:
                    self._on_focus_change(cached.name)
        except Exception:
            pass

    def _register_events(self) -> None:
        """StructureChanged 이벤트 등록 (동일 STA → 안전)"""
        # 기존 MessageListMonitor의 이벤트 등록 로직
        ...

    def _unregister_events(self) -> None:
        """이벤트 해제"""
        ...
```

### 5.3 영향 범위

| 파일 | 변경 유형 |
|------|----------|
| `unified_monitor.py` | 새 파일 생성 (~200줄) |
| `focus_monitor.py` | 대부분 코드 이동/삭제 |
| `uia_events.py` | MessageListMonitor 클래스 삭제 |
| `message_monitor.py` | 래퍼 수정 |
| `mode_manager.py` | 인터페이스 변경 |
| `main.py` | 초기화 로직 변경 |

### 5.4 예상 부작용

| 부작용 | 심각도 | 대응책 |
|--------|--------|--------|
| 대규모 리팩토링 | 높음 | 점진적 마이그레이션 |
| 테스트 범위 큼 | 높음 | 충분한 테스트 기간 |
| 폴링 간격 조율 필요 | 중간 | 타이밍 튜닝 |
| 롤백 어려움 | 중간 | 기능 브랜치에서 작업 |

### 5.5 테스트 방법

전체 기능 회귀 테스트 필요:

```
1. 기본 기능
   - [ ] 채팅방 진입/퇴장
   - [ ] 메시지 자동 읽기
   - [ ] 메시지 탐색 (화살표 키)

2. 메뉴 기능
   - [ ] 메시지 컨텍스트 메뉴 열기/읽기
   - [ ] 친구탭/채팅탭 메뉴 (영향 없어야 함)
   - [ ] 하위 메뉴 전환

3. 이모지 기능
   - [ ] 이모지 스캔
   - [ ] 이모지 선택

4. 안정성
   - [ ] 장시간 실행 (1시간+)
   - [ ] 빠른 동작 반복
   - [ ] 오류 로그 없음
```

### 5.6 마이그레이션 전략

**단계 1: 프로토타입 (1주)**
- `unified_monitor.py` 작성
- 별도 테스트 스크립트로 검증

**단계 2: 병행 운영 (2주)**
- 환경변수로 새/기존 아키텍처 전환
- `USE_UNIFIED_MONITOR=1`

**단계 3: 기존 코드 제거 (1주)**
- 테스트 통과 후 기존 클래스 삭제
- 문서 업데이트

---

## 6. 개선안 비교

| 항목 | A: NVDA 위임 | B: pause 최적화 | C: CacheRequest | D: 단일 스레드 |
|------|-------------|----------------|-----------------|---------------|
| **복잡도 감소** | 높음 (-155줄) | 없음 (+30줄) | 없음 (+5줄) | 높음 (재구조화) |
| **위험도** | 낮음 | 중간 | 낮음 | 높음 |
| **구현 시간** | 1일 | 2일 | 1시간 | 2-4주 |
| **테스트 범위** | 메뉴 기능 | 메뉴 기능 | 메뉴 기능 | 전체 |
| **롤백 용이성** | 쉬움 | 쉬움 | 쉬움 | 어려움 |
| **근본 해결** | 부분적 | 아니오 | 아니오 | 예 |

### 권장 적용 순서

```
1단계: C (CacheRequest) - 즉시 적용 가능, 위험 최소
2단계: A (NVDA 위임) - NVDA 테스트 후 적용
3단계: B (pause 최적화) - 필요 시 적용
4단계: D (단일 스레드) - 장기 과제로 검토
```

---

## 7. 검증 체크리스트

### 개선안 A 적용 전 필수 확인

- [ ] NVDA 기본 설정으로 EVA_Menu 클래스 지원 확인
- [ ] 카카오톡 메뉴에서 NVDA가 메뉴 항목 이름 읽는지
- [ ] KAKAO-002 문제가 NVDA에서도 동일한지

### 공통 테스트 케이스

| 시나리오 | 예상 동작 | 확인 |
|----------|----------|------|
| 메시지 우클릭 메뉴 | 첫 항목 읽음 | [ ] |
| 화살표 키 이동 | 각 항목 읽음 | [ ] |
| 하위 메뉴 진입 | 하위 메뉴 첫 항목 읽음 | [ ] |
| ESC로 닫기 | 오류 없이 닫힘 | [ ] |
| 빠른 열기/닫기 | 오류 없음 | [ ] |

---

## 8. 관련 파일 목록

| 파일 | 역할 | 변경 대상 |
|------|------|----------|
| `src/kakaotalk_a11y_client/focus_monitor.py` | 포커스 모니터, 메뉴 감지 | A, B, D |
| `src/kakaotalk_a11y_client/utils/uia_events.py` | MessageListMonitor, 이벤트 | A, B, C, D |
| `src/kakaotalk_a11y_client/mode_manager.py` | 모드 상태 관리 | B, D |
| `src/kakaotalk_a11y_client/navigation/message_monitor.py` | 래퍼 클래스 | A, D |
| `src/kakaotalk_a11y_client/utils/uia_cache_request.py` | CacheRequest 유틸리티 | C |
| `src/kakaotalk_a11y_client/config.py` | 타이밍 상수 | D |

---

## 9. 결론

**단기 권장:** 개선안 A (NVDA 완전 위임)
- 가장 적은 위험으로 가장 큰 복잡도 감소
- NVDA가 이미 필수 환경이므로 의존성 문제 없음
- 테스트 후 2일 내 적용 가능

**장기 권장:** 개선안 D (단일 스레드)
- COM 충돌의 근본적 해결
- 충분한 테스트 기간과 점진적 마이그레이션 필요
- 다음 메이저 버전에서 검토
