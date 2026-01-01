# NVDA UIA 패턴 레퍼런스

NVDA 스크린 리더 소스코드에서 추출한 UIA 구현 패턴.
카카오톡 접근성 클라이언트 적용 참고용.

**소스 위치**: `c:/project/nvda/nvda/source`

---

## 1. UIA 신뢰도 판단 패턴

### 발견 위치
- `UIAHandler/__init__.py:89-119` (goodUIAWindowClassNames, badUIAWindowClassNames)
- `UIAHandler/__init__.py:1152-1301` (_isUIAWindowHelper)
- `appModuleHandler.py:792-809` (isGoodUIAWindow, isBadUIAWindow)

### 핵심 코드
```python
# UIAHandler/__init__.py 라인 89-119
goodUIAWindowClassNames = (
    "RAIL_WINDOW",  # WDAG (Windows Defender Application Guard)
    "Microsoft.UI.Content.DesktopChildSiteBridge",  # WinUI 3
)

badUIAWindowClassNames = (
    "Microsoft.IME.CandidateWindow.View",
    "SysTreeView32",
    "WuDuiListView",
    "ComboBox",
    "Edit",
    "FoxitDocWnd",  # #8944: Foxit UIA 구현 불완전
    "MozillaWindowClass",  # #113: Firefox는 IA2가 더 나음
)
```

### 판단 순서
1. `goodUIAWindowClassNames`에 있으면 → True
2. `appModule.isGoodUIAWindow()` 확인
3. `badUIAWindowClassNames`에 있으면 → False
4. `appModule.isBadUIAWindow()` 확인
5. 특수 케이스 처리 (Office, Excel, Chrome, Console)
6. `UiaHasServerSideProvider()` API 호출

### 카카오톡 적용 방안
```python
KAKAO_GOOD_UIA_CLASSES = [
    "EVA_Window",
    "EVA_Window_Dblclk",
    "EVA_VH_ListControl_Dblclk",
    "EVA_Menu",
]

KAKAO_BAD_UIA_CLASSES = [
    "Chrome_WidgetWin_0",  # 광고 웹뷰
    "Chrome_WidgetWin_1",
    "Chrome_RenderWidgetHostHWND",
]

def is_good_uia_element(control) -> bool:
    class_name = control.ClassName or ""
    if class_name in KAKAO_BAD_UIA_CLASSES:
        return False
    return True
```

---

## 2. CacheRequest 패턴

### 발견 위치
- `UIAHandler/__init__.py:59-71` (baseCachePropertyIDs)
- `UIAHandler/__init__.py:523-531` (baseCacheRequest 생성)
- `NVDAObjects/UIA/__init__.py:99-146` (controlFieldUIACacheRequest)

### 핵심 코드
```python
# UIAHandler/__init__.py 라인 59-71
baseCachePropertyIDs = {
    UIA.UIA_FrameworkIdPropertyId,
    UIA.UIA_AutomationIdPropertyId,
    UIA.UIA_ClassNamePropertyId,
    UIA.UIA_ControlTypePropertyId,
    UIA.UIA_ProviderDescriptionPropertyId,
    UIA.UIA_ProcessIdPropertyId,
    UIA.UIA_IsTextPatternAvailablePropertyId,
    UIA.UIA_IsContentElementPropertyId,
    UIA.UIA_IsControlElementPropertyId,
    UIA.UIA_NamePropertyId,
    UIA.UIA_LocalizedControlTypePropertyId,
}

# 초기화
self.baseCacheRequest = self.windowCacheRequest.Clone()
for propertyId in baseCachePropertyIDs:
    self.baseCacheRequest.addProperty(propertyId)
```

### 핵심 로직
- 자주 사용하는 속성을 한 번에 캐시로 요청
- 개별 `currentProperty` 호출보다 빠름
- 트리 탐색 시 `BuildCache` 메서드 사용

### 카카오톡 적용 방안
> **Phase 2 이후 별도 진행** (comtypes 직접 사용 필요, 충돌 가능성)

---

## 3. 이벤트 핸들링 패턴

### 발견 위치
- `UIAHandler/__init__.py:305-312` (COM 인터페이스 선언)
- `UIAHandler/__init__.py:733-836` (HandleAutomationEvent)
- `UIAHandler/__init__.py:842-922` (HandleFocusChangedEvent)
- `UIAHandler/__init__.py:924-1018` (HandlePropertyChangedEvent)

### 핵심 코드
```python
# 이벤트 핸들러 인터페이스
class UIAHandler(COMObject):
    _com_interfaces_ = [
        UIA.IUIAutomationEventHandler,
        UIA.IUIAutomationFocusChangedEventHandler,
        UIA.IUIAutomationPropertyChangedEventHandler,
        UIA.IUIAutomationNotificationEventHandler,
    ]

# 포커스 변경 이벤트
def HandleFocusChangedEvent(self, sender):
    # 1. 초기화 완료 확인
    if not self.MTAThreadInitEvent.is_set():
        return
    # 2. 네이티브 UIA 요소인지 확인
    if not self.isNativeUIAElement(sender):
        return
    # 3. 중복 이벤트 필터링
    if self.clientObject.compareElements(sender, lastFocusObj.UIAElement):
        return
    # 4. NVDA 객체 생성 및 이벤트 큐잉
    obj = NVDAObjects.UIA.UIA(windowHandle=window, UIAElement=sender)
    eventHandler.queueEvent("gainFocus", obj)
```

### 핵심 로직
- MTA 스레드에서 실행 → 스레드 안전 필수
- 중복 이벤트 필터링
- 이벤트 실패 시 폴링으로 폴백

### 카카오톡 적용 방안
```python
class HybridFocusMonitor:
    """이벤트 기반 + 폴링 폴백"""
    def __init__(self):
        self.use_events = True
        self.event_failure_count = 0
        self.MAX_EVENT_FAILURES = 3

    def on_event_failure(self):
        self.event_failure_count += 1
        if self.event_failure_count >= self.MAX_EVENT_FAILURES:
            self.use_events = False  # 폴링으로 전환
```

---

## 4. 앱별 Workaround 패턴

### 발견 위치
- `UIAHandler/__init__.py` 전체 (# #숫자: 형식 주석)

### 주요 Workaround 사례
```python
# #17407, #17771: WinUI 3 top-level pane window class
"Microsoft.UI.Content.DesktopChildSiteBridge"

# #8944: Foxit UIA 구현 불완전
"FoxitDocWnd"

# #7345: MSAA winEvent를 UIA propertyChange로 매핑 금지
# 원인: 느린 메시지 펌프를 가진 앱에서 클라이언트 응답 불가

# #14067: textChange 성능 문제
# 해결: 글로벌 핸들러에서 제외, 로컬 핸들러에서만 처리

# #3867: comtypes/ctypes 더블프리 버그
# 해결: VARIANT.vt를 VT_EMPTY로 강제 설정
```

### 핵심 로직
- 모든 workaround에 GitHub 이슈 번호 참조
- 버전/앱별 조건부 적용
- 성능 영향 최소화

### 카카오톡 적용 방안
```python
WORKAROUNDS = {
    "KAKAO-001": {
        "description": "빈 ListItem 필터링",
        "affected_class": "EVA_VH_ListControl_Dblclk",
        "solution": "SmartListFilter",
    },
    "KAKAO-002": {
        "description": "메뉴 항목 하드코딩",
        "affected_class": "EVA_Menu",
        "solution": "CHATROOM_MESSAGE_MENU_ITEMS",
    },
}
```

---

## 5. ControlType 처리 패턴

### 발견 위치
- `UIAHandler/__init__.py:155-195` (UIAControlTypesToNVDARoles)

### 핵심 코드
```python
UIAControlTypesToNVDARoles = {
    UIA_ButtonControlTypeId: controlTypes.Role.BUTTON,
    UIA_CalendarControlTypeId: controlTypes.Role.CALENDAR,
    UIA_CheckBoxControlTypeId: controlTypes.Role.CHECKBOX,
    UIA_ComboBoxControlTypeId: controlTypes.Role.COMBOBOX,
    UIA_EditControlTypeId: controlTypes.Role.EDITABLETEXT,
    UIA_HyperlinkControlTypeId: controlTypes.Role.LINK,
    UIA_ImageControlTypeId: controlTypes.Role.GRAPHIC,
    UIA_ListItemControlTypeId: controlTypes.Role.LISTITEM,
    UIA_CustomControlTypeId: controlTypes.Role.UNKNOWN,
    # ... 총 25개 매핑
}
```

### 카카오톡 적용 방안
> 현재 프로젝트에서는 NVDA가 자체 처리하므로 별도 매핑 불필요.
> 직접 TTS 사용 시 참고.

---

## 6. 에러 핸들링 패턴

### 발견 위치
- `UIAHandler/__init__.py:17` (COMError 임포트)
- `UIAHandler/__init__.py` 전체 (366, 684, 710, 882, 946 등)

### 핵심 코드
```python
from comtypes import COMError

# 일반적인 try-except 패턴
try:
    processId = sender.CachedProcessID
except COMError:
    pass  # 기본값 사용

# 캐시 요청 실패
try:
    cacheElement = self.UIAElement.buildUpdatedCache(cacheRequest)
except COMError:
    log.debugWarning("buildUpdatedCache failed")
    return  # 조용히 실패

# 트리 탐색 실패
try:
    parentElement = UIAHandler.handler.baseTreeWalker.GetParentElementBuildCache(...)
except COMError:
    log.debugWarning("Tree walker failed", exc_info=True)
    return None
```

### 핵심 로직
- COM 호출은 항상 COMError 처리 필수
- 캐시 속성 접근 실패: 기본값 반환
- 트리 탐색 실패: None 반환

### 카카오톡 적용 방안
```python
from comtypes import COMError

def safe_uia_call(func, default=None, log_error=True):
    """COMError 안전 래퍼"""
    try:
        return func()
    except COMError as e:
        if log_error:
            profile_logger.warning(f"COMError: {e}")
        return default
    except Exception as e:
        if log_error:
            profile_logger.error(f"UIA Error: {e}")
        return default
```

---

## 7. 성능 최적화 패턴

### 발견 위치
- `UIAHandler/__init__.py:1303-1316` (UIAWindowHandleCache)
- `UIAHandler/__init__.py:514-516` (이벤트 병합)
- `NVDAObjects/UIA/__init__.py:2115-2122` (TreeScope_Children)

### 핵심 코드
```python
# 1. Window Handle 캐싱 (0.5초 TTL)
def isUIAWindow(self, hwnd: int) -> bool:
    now = time.time()
    v = self.UIAWindowHandleCache.get(hwnd, None)
    if not v or (now - v[1]) > 0.5:  # 0.5초 TTL
        v = (self._isUIAWindowHelper(hwnd), now)
        self.UIAWindowHandleCache[hwnd] = v
    return v[0]

# 2. 이벤트 병합 (Windows 10 RS5+)
if isinstance(self.clientObject, UIA.IUIAutomation6):
    self.clientObject.CoalesceEvents = UIA.CoalesceEventsOptions_Enabled

# 3. TreeScope_Children (직접 자식만)
childrenCacheRequest.TreeScope = UIAHandler.TreeScope_Children
```

### 핵심 로직
- **TTL 캐싱**: 0.5초 동안 동일 결과 재사용
- **이벤트 병합**: 중복 이벤트 자동 합침
- **TreeScope 제한**: 전체 Subtree 대신 직접 자식만

### 카카오톡 적용 방안
```python
@dataclass
class CacheEntry:
    value: Any
    timestamp: float
    ttl_seconds: float = 0.5

    @property
    def is_valid(self) -> bool:
        return time.time() - self.timestamp < self.ttl_seconds

class UIACache:
    def __init__(self, default_ttl: float = 0.5):
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry and entry.is_valid:
            return entry.value
        return None
```

---

## 패턴 간 상호관계

```
신뢰도 판단 (1)
    ↓
    → 이벤트 핸들링 (3) → Workaround 적용 (4)
    → CacheRequest (2)  → ControlType 변환 (5)
         ↓
    에러 핸들링 (6) ← 성능 최적화 (7)
```

## 구현 우선순위

1. **에러 핸들링** - 즉시 안정성 향상
2. **TTL 캐싱** - 반복 탐색 제거
3. **UIA 신뢰도 판단** - 불필요 탐색 방지
4. **이벤트 핸들링** - 폴링 대체 (선택적)
5. **Workaround 시스템** - 유지보수성 향상
6. CacheRequest - comtypes 직접 사용 (Phase 2 이후)
7. ControlType 매핑 - NVDA가 처리 (불필요)
