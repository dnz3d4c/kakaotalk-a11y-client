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
| MTA 아키텍처 | ✅ 단일 MTA | STA 다중 | ✅ 의도적 차이 (조사 완료: MTA 전환 불필요) |
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
3. **장기**: ~~MTA 전환~~ (조사 완료: 현재 STA 다중 스레드가 더 적합. 각 이벤트 스레드가 독립 STA로 안정적, 스레드 간 COM 객체 교환 없음), TreeWalker 도입

---

## 12. 적용 가능한 appModules 패턴

> NVDA appModules에서 추출한 패턴 중 kakaotalk-a11y에 적용 가능한 기법.
> 상세 레퍼런스: [C:/project/a11yDocs/NVDA_Addon_개발_가이드.md](file:///C:/project/a11yDocs/NVDA_Addon_%EA%B0%9C%EB%B0%9C_%EA%B0%80%EC%9D%B4%EB%93%9C.md)

### 12.1 event_NVDAObject_init: 이름 정규화

**NVDA 패턴** (`appModules/v2rayN.py`)

객체 초기화 시점에 Name 속성을 정규화. 읽기 전에 전처리하여 일관된 형식으로 출력.

```python
def event_NVDAObject_init(self, obj):
    if obj.role == controlTypes.Role.LISTITEM:
        # 특정 패턴 변환
        obj.name = self.normalize_name(obj.name)
```

**kakaotalk-a11y 적용 예시**: 광고 항목 이름 정규화

```python
# 현재: "(광고)" 텍스트가 ListItem Name 끝에 포함
# 적용 후: 광고임을 먼저 알려줌 (스크린리더 사용성)

def normalize_ad_name(name: str) -> str:
    """광고 항목 이름 정규화 - 접두사로 광고 표시"""
    if "(광고)" in name:
        return f"[광고] {name.replace('(광고)', '').strip()}"
    return name

# 예시 변환:
# "선물하기 (광고)" → "[광고] 선물하기"
# "컬리 (광고)" → "[광고] 컬리"
```

**적용 위치**: `focus_monitor.py` `_speak_item()` 메서드

---

### 12.2 Overlay Class: 메시지 유형별 커스텀 읽기

**NVDA 패턴** (`NVDAObjects/UIA/__init__.py`)

ControlType별로 오버레이 클래스를 삽입하여 동작 커스터마이징.

```python
@classmethod
def findOverlayClasses(cls, obj, clsList):
    UIAControlType = obj.UIAElement.cachedControlType
    if UIAControlType == UIA_ListItemControlTypeId:
        clsList.insert(0, CustomListItem)
```

**kakaotalk-a11y 적용 예시**: 메시지 유형별 접두사 추가

```python
# 현재: 모든 메시지를 동일하게 Name 그대로 읽음
# 적용 후: 유형별 접두사로 메시지 유형 먼저 안내

MESSAGE_TYPE_MARKERS = {
    "[사진]": "[사진 메시지]",
    "[이모티콘]": "[이모티콘]",
    "[스티커]": "[스티커]",
    "[파일]": "[파일 공유]",
    "[음성]": "[음성 메시지]",
}

def wrap_message_by_type(text: str) -> str:
    """메시지 유형 감지 + 접두사 포장"""
    for marker, prefix in MESSAGE_TYPE_MARKERS.items():
        if marker in text:
            return prefix + " " + text.replace(marker, "").strip()
    return text

# 예시 변환:
# "[사진] 홍길동, 오후 2:30" → "[사진 메시지] 홍길동, 오후 2:30"
# "[이모티콘] 하트, 홍길동" → "[이모티콘] 하트, 홍길동"
```

**적용 위치**: `focus_monitor.py` `_speak_item()` 메서드

---

### 12.3 증분 알림: lync.py 패턴

**NVDA 패턴** (`appModules/lync.py`)

채팅 창에서 전체 텍스트 대신 새로 추가된 부분만 읽기.

```python
# lync.py 핵심 로직
def event_liveRegionChange(self, obj, nextHandler):
    text = obj.name
    # 정규식으로 새 메시지 부분만 추출
    match = re.search(r"새 메시지: (.+)", text)
    if match:
        ui.message(match.group(1))
    else:
        nextHandler()
```

**kakaotalk-a11y 적용 예시**: 메시지 목록 증분 읽기

```python
# 현재: 새 메시지 도착 시 전체 메시지 또는 마지막 메시지 읽기
# 적용 후: 이전 상태 대비 새로 추가된 메시지만 읽기

class IncrementalMessageReader:
    """증분 메시지 읽기 - 이전 상태 대비 새 메시지만 추출"""
    _last_lines: list[str] = []

    @classmethod
    def get_new_content(cls, full_text: str) -> str:
        lines = full_text.split("\n")
        if len(lines) > len(cls._last_lines):
            new_lines = lines[len(cls._last_lines):]
            cls._last_lines = lines
            return "\n".join(new_lines)
        cls._last_lines = lines
        return full_text  # 전체가 바뀐 경우

# 예시:
# 이전: ["안녕", "반가워"]
# 현재: ["안녕", "반가워", "뭐해?"]
# 결과: "뭐해?" (새 메시지만)
```

**적용 위치**: `navigation/message_monitor.py`

---

### 12.4 W10/11 레퍼런스 모듈

> `C:/project/nvda/nvda/source/appModules/` 기준

| 모듈 | 핵심 패턴 | 학습 포인트 |
|------|----------|------------|
| **explorer.py** | Overlay 9개 + isGoodUIAWindow | W11 Shell 요소 감지, 버전별 분기 |
| **calculator.py** | event_nameChange + 캐시 | UIA 알림 필터링, 중복 방지 |
| **notepad.py** | event_UIA_elementSelected | W11 Notepad 탭 전환 감지 |
| **lync.py** | 라이브 리전 + 정규식 | 채팅 메시지 파싱, 증분 알림 |
| **foobar2000.py** | Gesture + NamedTuple | 상태 표시줄 파싱, 시간 형식 |
| **excel.py** | focusRedirect + 재시도 | CellEdit 찾기, 이벤트 계류 체크 |
| **devenv.py** | COM 자동화 + TextInfo | Visual Studio DTE, 스레드 캐싱 |
| **eclipse.py** | 자동완성 + 이벤트 무시 | 깊은 포커스 계층 탐색 |
| **kindle.py** | IA2Attributes + 페이지 턴 | 하이퍼텍스트 재귀 탐색 |
| **logonui.py** | 포커스 리다이렉트 | 로그인 화면, 버전별 윈도우 클래스 |

---

## 13. standalone vs NVDA 메커니즘 비교 (2026-02 심층 분석)

> kakaotalk-accessible-nvda 62줄 vs standalone 10,923줄 비교에서 도출된 분석.
> 3가지 핵심 패턴의 메커니즘 차이를 문서화.

### 13.1 shouldAllowUIAFocusEvent vs HasKeyboardFocus 미체크

**NVDA 메커니즘**:
- `UIAHandler/__init__.py:912`에서 `obj.shouldAllowUIAFocusEvent` 체크
- 기본 구현(`NVDAObjects/UIA/__init__.py:1579-1583`): `HasKeyboardFocus` UIA 속성 조회
- False면 포커스 이벤트 드롭 (항목을 읽지 않음)
- 카카오톡 메뉴 항목은 `HasKeyboardFocus=False` → NVDA 기본으로는 못 읽음
- 애드온이 `shouldAllowUIAFocusEvent = True`로 게이트 우회

**standalone 메커니즘**:
- HasKeyboardFocus 체크 자체가 파이프라인에 없음
- 모든 FocusChanged 이벤트를 hwnd 필터 → RuntimeID 중복 → Chrome_* 필터만 통과시킴
- 게이트가 없으니 우회도 필요 없음

**차이점**: 기능적으로 동등하나 메커니즘이 다름. NVDA는 선택적 우회(요소 타입별), standalone은 무조건 수용. standalone에서 카카오톡 내부 거짓 포커스 이벤트가 발생하면 필터링 못 함. 현재까지 관찰된 문제 없음.

---

### 13.2 isGoodUIAWindow → True vs EVA_* 접두사 인식

**NVDA 메커니즘**:
- `isGoodUIAWindow(hwnd) → True` — kakaotalk.exe의 **모든** 윈도우에 무조건 UIA
- 새 윈도우 클래스 자동 커버

**standalone 메커니즘 (2026-02 개선)**:
- `is_kakaotalk_window()`: EVA_* 접두사 기반 인식
- Chrome_* 명시적 제외
- 기능적으로 NVDA와 동등해짐

**이전 한계**: EVA_Window_Dblclk, EVA_Menu 2개 클래스만 하드코딩 → 새 클래스 추가 시 코드 수정 필요했음 (EVA_Menu 추가할 때 겪은 문제). 접두사 기반으로 변경하여 해결.

---

### 13.3 _get_states SELECTED→FOCUSED 트릭

**NVDA 메커니즘**:
- `KakaoListItem._get_states()`: SELECTED 상태 있으면 FOCUSED 추가
- 영향 범위: speech output 정확성 (`processAndLabelStates`에서 상태 발화 결정)
- `shouldAllowUIAFocusEvent`, `hasFocus`, `doPreGainFocus`에는 영향 없음
- 진짜 focus 관리는 `event_UIA_elementSelected → queueEvent("gainFocus")`가 담당

**standalone 메커니즘**:
- UIA 상태(states) 자체를 사용하지 않음
- Name과 RuntimeId만으로 중복 감지 및 발화
- "선택됨"/"선택 해제됨" 상태 정보 발화 없음

**사용자가 NVDA에서 느끼는 "더 나은 포커스 관리"의 실제 원인**:

_get_states 트릭 자체보다, gainFocus 파이프라인의 풍부함이 핵심:
- `focusEntered`: 새 컨테이너 진입 시 "목록" 같은 컨텍스트 발화
- `cancelSpeech`: 빠른 탐색 시 이전 발화 자동 취소
- braille/navigator 동기화

standalone이 이 차이를 줄이려면 gainFocus 파이프라인 구현이 필요하나, 대규모 아키텍처 변경으로 현재 범위 밖.

---

## 참고 문서

- [NVDA_DEEP_ANALYSIS.md](NVDA_DEEP_ANALYSIS.md) - 심층 분석 (800줄)
- [CONTEXT_MENU_IMPROVEMENT_ANALYSIS.md](CONTEXT_MENU_IMPROVEMENT_ANALYSIS.md) - 메뉴 읽기 개선
