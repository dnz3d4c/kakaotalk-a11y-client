# NVDA UIA 패턴 레퍼런스

NVDA 스크린 리더 소스코드에서 추출한 UIA 구현 패턴.

- 참조 버전: NVDA 2026.2.0
- 참조 소스: https://github.com/nvaccess/nvda (2025-01 기준)
- 프로젝트 적용: `src/kakaotalk_a11y_client/utils/uia_*.py`

---

## 1. UIA 신뢰도 판단

### NVDA 소스
`UIAHandler/__init__.py:89-119`

```python
goodUIAWindowClassNames = (
    "RAIL_WINDOW",  # WDAG
    "Microsoft.UI.Content.DesktopChildSiteBridge",  # WinUI 3
)

badUIAWindowClassNames = (
    "Microsoft.IME.CandidateWindow.View",
    "SysTreeView32", "WuDuiListView", "ComboBox", "Edit",
    "FoxitDocWnd",  # #8944: 불완전한 UIA 구현
    "MozillaWindowClass",  # #113: IA2가 더 나음
)
```

### 판단 순서
1. `goodUIAWindowClassNames` → True
2. `appModule.isGoodUIAWindow()` 확인
3. `badUIAWindowClassNames` → False
4. `appModule.isBadUIAWindow()` 확인
5. 특수 케이스 (Office, Excel, Chrome, Console)
6. `UiaHasServerSideProvider()` API

### 프로젝트 구현
`src/kakaotalk_a11y_client/utils/uia_utils.py:33-50`

```python
KAKAO_GOOD_UIA_CLASSES = [
    "EVA_Window", "EVA_Window_Dblclk",
    "EVA_VH_ListControl_Dblclk", "EVA_Menu",
]

KAKAO_BAD_UIA_CLASSES = [
    "Chrome_WidgetWin_0", "Chrome_WidgetWin_1",  # 광고 웹뷰
    "Chrome_RenderWidgetHostHWND",
]
```

---

## 2. 에러 핸들링

구현 1순위. COM 호출은 항상 실패 가능.

### NVDA 소스
`UIAHandler/__init__.py` 전체 (366, 684, 710, 882, 946행 등)

```python
from comtypes import COMError

try:
    processId = sender.CachedProcessID
except COMError:
    pass  # 기본값

try:
    cacheElement = self.UIAElement.buildUpdatedCache(cacheRequest)
except COMError:
    log.debugWarning("buildUpdatedCache failed")
    return

# #3867: comtypes/ctypes 더블프리 버그
newValue.vt = VT_EMPTY  # 938행
```

### 프로젝트 구현
`src/kakaotalk_a11y_client/utils/uia_utils.py:110-167`

```python
def safe_uia_call(func, default=None, log_error=True, error_msg=""):
    """COMError 안전 래퍼"""
    try:
        return func()
    except COMError as e:
        if log_error:
            profile_logger.warning(f"COMError: {e}")
        return default
    except LookupError:
        return default  # 요소 못 찾음 - 정상

# 데코레이터 버전
@handle_uia_errors(default_return=[])
def get_children_safe(control):
    return control.GetChildren()
```

---

## 3. 이벤트 핸들링

### NVDA 2026 COM 인터페이스
`UIAHandler/__init__.py:305-312`

```python
class UIAHandler(COMObject):
    _com_interfaces_ = [
        IUIAutomationEventHandler,
        IUIAutomationFocusChangedEventHandler,
        IUIAutomationPropertyChangedEventHandler,
        IUIAutomationNotificationEventHandler,  # 알림 이벤트
        IUIAutomationActiveTextPositionChangedEventHandler,  # 텍스트 위치
    ]
```

### 이벤트 그룹 (IUIAutomation6)
`UIAHandler/__init__.py:568-616`

```python
# Windows 10 RS5+ 에서만 사용 가능
if isinstance(self.clientObject, UIA.IUIAutomation6):
    self.clientObject.CoalesceEvents = CoalesceEventsOptions_Enabled  # 515행
    self.clientObject.ConnectionRecoveryBehavior = ConnectionRecoveryBehaviorOptions_Enabled  # 516행
    globalEventHandlerGroup = self.clientObject.CreateEventHandlerGroup()
```

### 포커스 이벤트 핸들링
`UIAHandler/__init__.py:842-922`

```python
def HandleFocusChangedEvent(self, sender):
    if not self.MTAThreadInitEvent.is_set():
        return
    if not self.isNativeUIAElement(sender):
        return
    if self.clientObject.compareElements(sender, lastFocusObj.UIAElement):
        return  # 중복 필터링
    obj = NVDAObjects.UIA.UIA(windowHandle=window, UIAElement=sender)
    eventHandler.queueEvent("gainFocus", obj)
```

### 이벤트 매핑
`UIAHandler/__init__.py:203-250`

```python
UIAPropertyIdsToNVDAEventNames = {
    UIA_NamePropertyId: "nameChange",
    UIA_IsEnabledPropertyId: "stateChange",
    UIA_ValueValuePropertyId: "valueChange",
}

UIAEventIdsToNVDAEventNames = {
    UIA_LiveRegionChangedEventId: "liveRegionChange",
    UIA_MenuOpenedEventId: "gainFocus",
    UIA_ToolTipOpenedEventId: "UIA_toolTipOpened",
    UIA_SystemAlertEventId: "UIA_systemAlert",
}
```

### 프로젝트 구현

**FocusMonitor** (`uia_events.py`)
- 순수 이벤트 기반 (폴링 폴백 제거됨, 2026-01)
- AddFocusChangedEventHandler 사용

**MessageListMonitor** (`uia_events.py`)
- StructureChanged 이벤트 직접 구현
- COM 메시지 펌프 루프

**pause/resume 패턴**
- 메뉴 열림 중 CPU 스파이크 방지
- 이벤트 수신은 유지, 콜백만 무시

```python
class FocusMonitor:
    """순수 이벤트 기반 포커스 모니터 (2026-01 리팩터링)"""
    def start(self, on_focus_changed):
        # AddFocusChangedEventHandler 등록
        self._uia.AddFocusChangedEventHandler(
            self._cache_request, self._handler
        )
```

---

## 4. TTL 캐싱

### NVDA 소스
`UIAHandler/__init__.py:1303-1316`

```python
def isUIAWindow(self, hwnd: int) -> bool:
    now = time.time()
    v = self.UIAWindowHandleCache.get(hwnd, None)
    if not v or (now - v[1]) > 0.5:  # 0.5초 TTL
        v = (self._isUIAWindowHelper(hwnd), now)
        self.UIAWindowHandleCache[hwnd] = v
    return v[0]
```

### 프로젝트 구현
`src/kakaotalk_a11y_client/utils/uia_cache.py:34-200`

```python
class UIACache:
    def __init__(self, default_ttl: float = 0.5):
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry and entry.is_valid:
            return entry.value
        return None

# 글로벌 캐시 인스턴스 (2026-01 정리: 1개만 사용)
message_list_cache = UIACache(default_ttl=1.0)
# menu_cache, window_cache는 제거됨 (불필요)
```

---

## 5. Workaround

### NVDA 패턴
모든 workaround에 GitHub 이슈 번호 참조.

```python
# #17407, #17771: WinUI 3
"Microsoft.UI.Content.DesktopChildSiteBridge"

# #8944: Foxit UIA 불완전
"FoxitDocWnd"

# #7345: MSAA winEvent → UIA propertyChange 매핑 금지
# #14067: textChange 글로벌 핸들러 제외 (성능)
# #3867: comtypes/ctypes 더블프리 버그
```

### 프로젝트 구현
`src/kakaotalk_a11y_client/utils/uia_workarounds.py:35-84`

| ID | 설명 | 해결책 |
|----|------|--------|
| KAKAO-001 | 빈 ListItem 대량 발생 | SmartListFilter, 연속 15개 조기종료 |
| KAKAO-002 | 메뉴 항목 UIA Name 없음 | CHATROOM_MESSAGE_MENU_ITEMS 하드코딩 |
| KAKAO-003 | 메뉴 팝업 지연 (150ms+) | 적응형 재시도 (최대 7회, 지수 백오프) |
| KAKAO-004 | Chromium 광고 UIA 불안정 | KAKAO_BAD_UIA_CLASSES 등록 |
| KAKAO-005 | AutomationId 불규칙 | Name+ControlType 조합 사용 |
| KAKAO-006 | ClassName 대부분 없음 | EVA_* 클래스만 신뢰 |

---

## 6. 참고사항

### CacheRequest (미적용)
`UIAHandler/__init__.py:59-71, 523-531`

comtypes 직접 사용 필요. 현재 uiautomation 라이브러리로 충분.

```python
baseCachePropertyIDs = {
    UIA_FrameworkIdPropertyId, UIA_AutomationIdPropertyId,
    UIA_ClassNamePropertyId, UIA_ControlTypePropertyId,
    UIA_NamePropertyId, UIA_LocalizedControlTypePropertyId,
    # ... 총 11개
}
```

### ControlType 매핑 (불필요)
NVDA 자체 처리. 참고: `UIAHandler/__init__.py:155-195`

### TreeScope 제한
`NVDAObjects/UIA/__init__.py:2115-2122`

```python
# Subtree 전체 탐색 대신 직접 자식만
childrenCacheRequest.TreeScope = UIAHandler.TreeScope_Children
```

---

## 구현 우선순위

1. **에러 핸들링** - 즉시 안정성 향상
2. **TTL 캐싱** - 반복 탐색 제거
3. **UIA 신뢰도 판단** - 불필요한 탐색 방지
4. **이벤트 핸들링** - 폴링 대체 (선택적)
5. **Workaround 시스템** - 유지보수성 향상
6. CacheRequest - Phase 2 이후

---

## 패턴 상호관계

```
신뢰도 판단 (1)
    ↓
    → 이벤트 핸들링 (3) → Workaround (5)
    → TTL 캐싱 (4)
         ↓
    에러 핸들링 (2)
```

---

## 7. NVDAObjects/UIA 객체 모델

> 상세 분석: [NVDA_DEEP_ANALYSIS.md](NVDA_DEEP_ANALYSIS.md#2-객체-모델-아키텍처)

### 클래스 계층

```
NVDAObject (기반)
└─ Window (OS 윈도우)
   └─ UIA (UI Automation)
      ├─ UIAWeb (웹 브라우저)
      ├─ ExcelObject (엑셀)
      └─ Dialog, ProgressBar 등
```

### 메타클래스 기반 동적 생성

`NVDAObjects/__init__.py`

```python
DynamicNVDAObjectType.__call__()
  1. chooseBestAPI() → API 클래스 결정
  2. findOverlayClasses() → 오버레이 수집
  3. appModule.chooseNVDAObjectOverlayClasses()
  4. 동적 클래스 생성 (obj.__class__ = newCls)
  5. initOverlayClass() 호출
```

### 오버레이 클래스 패턴

```python
# NVDAObjects/UIA/__init__.py
class UIA(Window):
    @classmethod
    def findOverlayClasses(cls, obj, clsList):
        UIAControlType = obj.UIAElement.cachedControlType
        if UIAControlType == UIA_ListControlTypeId:
            clsList.insert(0, List)
        elif UIAControlType == UIA_MenuItemControlTypeId:
            clsList.insert(0, MenuItem)
```

### 프로젝트 적용

현재 미적용. 채팅 메시지용 오버레이 클래스 도입 검토 가능.

---

## 8. eventHandler 이벤트 시스템

> 상세 분석: [NVDA_DEEP_ANALYSIS.md](NVDA_DEEP_ANALYSIS.md#3-이벤트-시스템)

### 이벤트 흐름

```
플랫폼 이벤트 (WinEvent/UIA)
    ↓
OrderedWinEventLimiter (이벤트 병합)
    ↓
UIAHandler (FocusChanged, PropertyChanged)
    ↓
eventHandler.queueEvent()
    ↓
executeEvent() → speech.manager
```

### OrderedWinEventLimiter

`IAccessibleHandler/orderedWinEventLimiter.py`

```python
MAX_FOCUS_EVENTS = 4           # 포커스 이벤트 최대
MAX_WINEVENTS_PER_THREAD = 10  # 스레드당 일반 이벤트 최대

# 이벤트 충돌 처리
# SHOW + HIDE → 둘 다 제거 (최종 상태 반영)
```

### FocusLossCancellableSpeechCommand

`eventHandler.py:187-310`

이전 포커스 이벤트의 음성 출력 자동 취소:
- `isLastFocusObj()` - 현재 포커스가 이 객체인가
- `isAncestorOfCurrentFocus()` - 부모/조상인가
- `isMenuItemOfCurrentFocus()` - 메뉴 관련인가

### 프로젝트 적용

- 이벤트 병합: ✅ 적용 (EventCoalescer 20ms 간격, 디바운싱 30ms)
- 음성 취소: 미적용 → 빠른 포커스 전환 시 유용

---

## 9. compareElements API

### NVDA 패턴

`UIAHandler/utils.py:69-77`

```python
def isUIAElementInWalker(element, walker):
    try:
        newElement = walker.normalizeElement(element)
    except COMError:
        newElement = None
    return newElement and UIAHandler.handler.clientObject.compareElements(element, newElement)
```

### 프로젝트 현재 (문제)

```python
# uia_utils.py:813 - Python 객체 비교 (부정확)
if focused == parent_control:
    return True
```

### 개선 권장

```python
def compare_elements(elem1, elem2) -> bool:
    """COM 수준 요소 비교"""
    try:
        return _uia.CompareElements(elem1.NativeElement, elem2.NativeElement)
    except Exception:
        return False
```

---

## 10. FocusChanged 고급 패턴

> 2026-01-25 NVDA 소스 분석 추가 (UIAHandler, NVDAObjects/UIA)

### shouldAllowUIAFocusEvent

**NVDA 소스:** `NVDAObjects/UIA/__init__.py:1579-1583`

```python
def _get_shouldAllowUIAFocusEvent(self):
    """FocusChanged 이벤트 수용 여부 - HasKeyboardFocus 속성으로 실제 포커스 확인"""
    try:
        return bool(self._getUIACacheablePropertyValue(UIA_HasKeyboardFocusPropertyId))
    except COMError:
        return True  # 속성 조회 실패 시 허용
```

**핵심**: FocusChanged 이벤트 수신 후 `HasKeyboardFocus` 속성을 **조회**해서 실제 키보드 포커스 보유 여부 2차 검증. PropertyChanged 이벤트가 아님.

**프로젝트 적용:**
```python
# uia_focus_handler.py:_on_focus_event()
try:
    if not sender.CurrentHasKeyboardFocus:
        return  # 실제 포커스 아님
except Exception:
    pass
```

### shouldAllowDuplicateUIAFocusEvent

**NVDA 소스:** `NVDAObjects/UIA/__init__.py:1140`

```python
shouldAllowDuplicateUIAFocusEvent = False  # 기본값: 중복 포커스 이벤트 차단
```

**용도**: 특정 컨트롤에서 중복 포커스 이벤트 허용 여부 제어. 기본적으로 `compareElements()` + 이 플래그로 중복 필터링.

**프로젝트 현황:** RuntimeID 기반 중복 체크로 대체 (동일 효과)

### addLocalEventHandlerGroupToElement

**NVDA 소스:** `UIAHandler/__init__.py:673-715`

```python
def addLocalEventHandlerGroupToElement(self, element, isFocus=False):
    """포커스된 요소에만 로컬 이벤트 핸들러 등록 (CPU 절약)"""
    if isFocus:
        # 등록 전 아직 포커스 상태인지 확인
        isStillFocus = self.clientObject.CompareElements(
            self.clientObject.GetFocusedElement(),
            element,
        )
    # MTA 스레드 큐로 비동기 처리
    self.MTAThreadQueue.put_nowait(func)
```

**동작:**
- `event_gainFocus()` → `addLocalEventHandlerGroupToElement()` 호출
- `event_loseFocus()` → `removeLocalEventHandlerGroupFromElement()` 호출
- 포커스 요소에만 PropertyChanged 등 세부 이벤트 등록

**프로젝트 현황:** 미적용 (글로벌 이벤트로 충분)

### isNativeUIAElement

**NVDA 소스:** `UIAHandler/__init__.py:1451+`

```python
def isNativeUIAElement(self, UIAElement):
    """같은 프로세스의 UIA 요소는 제외 (freeze 방지)"""
    try:
        processID = UIAElement.cachedProcessId
    except COMError:
        return False
    # 같은 프로세스면 False (크로스 프로세스 COM 마샬링 문제)
```

**용도**: 자체 프로세스 UIA 요소 접근 시 발생하는 데드락/프리즈 방지

**프로젝트 현황:** Chrome_* 클래스 필터링으로 부분 대체

### FakeEventHandlerGroup

**NVDA 소스:** `UIAHandler/utils.py:276-336`

```python
class FakeEventHandlerGroup:
    """IUIAutomation6 미지원 시 EventHandlerGroup API 에뮬레이션"""

    def AddPropertyChangedEventHandler(self, scope, cacheRequest, handler, propertyArray, propertyCount):
        properties = self.clientObject.IntNativeArrayToSafeArray(propertyArray, propertyCount)
        self._propertyChangedEventHandlers[(scope, cacheRequest, properties)] = handler

    def registerToClientObject(self, element):
        for (scope, cacheRequest, properties), handler in self._propertyChangedEventHandlers.items():
            self.clientObject.AddPropertyChangedEventHandler(element, scope, cacheRequest, handler, properties)
```

**용도**: Windows 10 1809 이전 버전에서 `CreateEventHandlerGroup()` API 부재 시 폴백

**프로젝트 현황:** 미적용 (IUIAutomation6 직접 사용)

---

## 11. 프로젝트 적용 현황

| 패턴 | NVDA | 프로젝트 | 상태 |
|------|------|---------|------|
| 에러 핸들링 | try-except | safe_uia_call + COMError 세분화 | ✅ 적용 |
| TTL 캐싱 | 0.5초 | UIACache | ✅ 적용 |
| UIA 신뢰도 | good/bad 클래스 | KAKAO_*_CLASSES | ✅ 적용 |
| CacheRequest | 11+ 속성 | 4개 필수 | ✅ 더 효율적 |
| 이벤트 핸들링 | 전역+로컬 | 이벤트 기반 (FocusMonitor) | ✅ 적용 |
| Workaround | 이슈 번호 | KAKAO-00X | ✅ 적용 |
| compareElements | ✅ 사용 | RuntimeID 비교 | ✅ 적용 |
| 이벤트 병합 | OrderedWinEventLimiter | 20ms Condition 패턴 | ✅ 적용 |
| TreeWalker | ✅ 사용 | searchDepth | ⚠️ 부분 |
| MTA 아키텍처 | ✅ 단일 MTA | STA 다중 | ⚠️ 차이 |
| **CoalesceEvents** | ✅ IUIAutomation6 | ✅ 적용 | 이벤트 병합 |
| **ConnectionRecoveryBehavior** | ✅ IUIAutomation6 | ✅ 적용 | **신규 (2026-01-25)** |
| **FocusChanged CacheRequest** | ✅ 속성 캐시 | ✅ 4개 속성 | **신규 (2026-01-25)** |
| shouldAllowUIAFocusEvent | ✅ HasKeyboardFocus | ❌ 미적용 | 불필요 (RuntimeID로 충분) |
| shouldAllowDuplicateUIAFocusEvent | ✅ 플래그 | RuntimeID 대체 | ✅ 동일 효과 |
| addLocalEventHandlerGroupToElement | ✅ 동적 등록 | ❌ 미적용 | 불필요 |
| isNativeUIAElement | ✅ 프로세스 체크 | Chrome_* 필터 | ⚠️ 부분 |
| FakeEventHandlerGroup | ✅ IUIAutomation6 폴백 | ❌ 미적용 | 불필요 |

### 개선 우선순위

1. **즉시**: ~~compareElements 도입~~, ~~COM 초기화 일관성~~, ~~ConnectionRecoveryBehavior~~, ~~CacheRequest~~ → ✅ 완료
2. **중기**: ~~FocusChanged 이벤트~~, ~~이벤트 병합 Condition 패턴~~ → ✅ 완료
3. **장기**: MTA 전환, TreeWalker 도입

---

## 참고 문서

- [NVDA_DEEP_ANALYSIS.md](NVDA_DEEP_ANALYSIS.md) - 심층 분석 (800줄)
- [CONTEXT_MENU_IMPROVEMENT_ANALYSIS.md](CONTEXT_MENU_IMPROVEMENT_ANALYSIS.md) - 메뉴 읽기 개선
