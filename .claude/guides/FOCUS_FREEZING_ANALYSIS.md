# FocusMonitor 프리징 분석 (0.5.1 실패 케이스)

## 문서 목적

**Claude 코딩 시**: 이 문제를 다시 수정할 때 시도했던 방법과 실패 원인을 참고하여 올바른 방향으로 수정.

**사용자 참고**: 어떤 시도가 있었고 왜 실패했는지 이해. 향후 테스트 시 검증 포인트 파악.

---

## 문제 증상

### 증상 1: 빠른 탐색 시 브리징 (Phase 1, 2로 해결)
- **환경**: `--debug --trace` 모드
- **증상**: 빠른 포커스 이동 시 NVDA 프리징
- **재현**: 채팅방 목록에서 빠르게 위/아래 탐색
- **해결**: Phase 1 (RuntimeID + 30ms 디바운싱), Phase 2 (EventCoalescer)

### 증상 2: 카카오톡 새 시작 시 브리징 (미해결)
- **환경**: 릴리즈/디버그 모드 무관
- **증상**: 카카오톡 프로세스 새로 시작 시 브리징 (트레이 복원은 문제없음)
- **재현**: 클라이언트 실행 → 카카오톡 종료 후 재실행

---

## 해결된 시도들 (Phase 1, 2)

### Phase 1: CompareElements 제거 + RuntimeID + 30ms 디바운싱
**커밋**: `1d2cc9b`

**변경 내용**:
- `CompareElements()` 제거 (1-5ms COM 호출)
- `RuntimeID` 기반 중복 체크로 대체
- 30ms 시간 기반 디바운싱

**결과**: ✅ 탐색 중 브리징 감소

---

### Phase 2: EventCoalescer 추가
**커밋**: `df116d4`

**변경 내용**:
- NVDA 스타일 이벤트 병합 (같은 요소의 이벤트는 최신만 유지)
- 20ms 배치 처리

**결과**: ✅ 빠른 탐색 시 이벤트 50-80% 감소

---

## 실패한 시도들 (카카오톡 새 시작 브리징)

### 시도 1: UIA Typelib 백그라운드 Preload

**파일**: `main.py`

**변경 내용**:
```python
def _preload_uia_typelib():
    """백그라운드에서 UIA typelib 캐시 생성."""
    def load():
        from comtypes.client import GetModule
        GetModule("UIAutomationCore.dll")
    threading.Thread(target=load, daemon=True).start()

_preload_uia_typelib()  # import 직후 즉시 시작
```

**의도**: GetModule() 첫 호출 비용을 앱 시작 시 미리 지불

**결과**: ❌ 실패

**이유**: import 순서상 `uia_events.py`의 동기 `GetModule()`이 preload보다 먼저 실행됨
```
1. _preload_uia_typelib() 스레드 시작
2. from .focus_monitor import ... (동기)
   └─> uia_events.py 로드
       └─> GetModule() 호출 ← preload보다 먼저!
```

---

### 시도 2: CacheRequestManager 사전 초기화

**파일**: `uia_cache_request.py`

**변경 내용**:
```python
def preload_cache_manager() -> None:
    def init():
        mgr = get_cache_manager()
        mgr._ensure_initialized()
    threading.Thread(target=init, daemon=True).start()
```

**의도**: CacheRequestManager COM 객체 미리 생성

**결과**: ❌ 실패

**이유**: 시도 1과 동일. import 순서 문제.

---

### 시도 3: FocusMonitor 비동기 초기화

**파일**: `focus_monitor.py`

**변경 내용**:
```python
def start(self) -> None:
    # FocusMonitor는 여기서 시작하지 않음
    self._thread = threading.Thread(target=self._monitor_loop)
    self._thread.start()

def _ensure_focus_monitor_async(self) -> None:
    """카카오톡 창 감지 시 FocusMonitor 백그라운드 초기화."""
    if self._focus_monitor_started or self._focus_monitor_initializing:
        return
    self._focus_monitor_initializing = True

    def init():
        self._focus_monitor = FocusMonitor()
        self._focus_monitor.start(on_focus_changed=self._on_focus_event)
        self._focus_monitor_started = True

    threading.Thread(target=init, daemon=True).start()

# _monitor_loop에서 카카오톡 창 감지 시 호출
self._ensure_focus_monitor_async()
```

**의도**: 카카오톡 창 감지 전까지 FocusMonitor 초기화 지연

**결과**: ❌ 실패

**이유**: 비동기로 시작해도 카카오톡이 막 시작된 상태에서 UIA 접근하면 브리징 발생. 카카오톡 UIA Provider가 아직 준비 안 됨.

---

### 시도 4: _warmup_uia() 제거

**파일**: `focus_monitor.py`

**변경 내용**:
```python
# 제거된 코드
def _warmup_uia():
    self._uia.init_com()
    _ = self._uia.get_focused_control()  # ← 카카오톡 새 시작 시 브리징 유발
    self._uia.uninit_com()

warmup_thread = threading.Thread(target=_warmup_uia)
warmup_thread.start()

# 워밍업 완료까지 최대 5초 대기
while self._running:
    if uia_ready.is_set():
        break
    time.sleep(0.1)
```

**의도**:
- 카카오톡 새 시작 시 `get_focused_control()` 호출이 브리징 유발
- 워밍업 목적은 FocusMonitor 비동기 초기화로 대체됨

**결과**: ❌ 실패

**이유**: _warmup_uia() 제거만으로는 부족. FocusMonitor 비동기 초기화 시점에 여전히 브리징 발생.

---

## 근본 원인 분석

### 카카오톡 새 시작 시 브리징

```
카카오톡 프로세스 시작
├─ 카카오톡 UI 로드 중
├─ 카카오톡 UIA Provider 초기화 중 ← 아직 준비 안 됨
└─ 클라이언트에서 UIA 접근 시도 ← 브리징!
```

### 트레이 복원은 왜 괜찮은가?

- 트레이 복원 = 같은 프로세스, UIA Provider 이미 초기화됨
- 새 프로세스 = UIA Provider 초기화 중 → 외부 UIA 요청 시 블로킹

---

## 미검증 해결 방향

### 방향 1: 카카오톡 준비 상태 감지

카카오톡 UIA Provider가 준비될 때까지 대기 후 FocusMonitor 초기화.

**문제점**: "준비됨"을 어떻게 판단? 명확한 시그널 없음.

### 방향 2: 점진적 초기화

FocusMonitor 초기화를 여러 단계로 나눠서 각 단계마다 지연.

**문제점**: 복잡도 증가, 효과 불확실.

### 방향 3: 이벤트 큐 분리 (NVDA PR #14888)

COM 콜백에서 즉시 반환, 처리는 별도 큐에서.

**상태**: 탐색 브리징은 Phase 1, 2로 해결됨. 새 프로세스 브리징에 효과 있을지 불확실.

### 방향 4: 첫 UIA 접근 지연

카카오톡 창 감지 후 일정 시간(예: 500ms~1초) 대기 후 FocusMonitor 초기화.

**검토 필요**: 단순하지만 UX 저하 가능성.

---

## 현재 코드 상태

| 파일 | 상태 |
|------|------|
| `main.py` | preload 코드 제거됨 |
| `uia_cache_request.py` | preload_cache_manager() 제거됨 |
| `focus_monitor.py` | FocusMonitor 비동기 초기화 + _warmup_uia() 제거됨 |

**현재 변경사항**: 커밋 안 됨 (롤백 또는 추가 수정 필요)

---

## 저장된 코드 (Git Stash)

미완성 코드가 stash에 저장되어 있음:

```bash
# stash 목록 확인
git stash list
# stash@{0}: On main: FocusMonitor 비동기 초기화 시도 (미완성)

# 복원하려면
git stash pop

# 내용만 확인하려면
git stash show -p stash@{0}
```

**포함된 변경사항**:
- `focus_monitor.py`: FocusMonitor 비동기 초기화, _warmup_uia() 제거
- `main.py`: preload 코드 제거
- `uia_cache_request.py`: preload_cache_manager() 제거

---

## 다음 시도 시 체크리스트

- [ ] 카카오톡 UIA Provider 준비 감지 방법 조사
- [ ] 첫 UIA 접근 전 고정 지연 효과 테스트
- [ ] C++ 없이 Python으로 가능한 범위 재검토
- [ ] NVDA 소스코드에서 앱 시작 시 처리 방식 참고
