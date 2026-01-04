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

**HybridFocusMonitor** (`uia_events.py:58-256`)
- 이벤트 기반 → 폴링 자동 폴백
- 최대 3회 실패 후 폴링 전환

**MessageListMonitor** (`uia_events.py:369-668`)
- StructureChanged 이벤트 직접 구현
- COM 메시지 펌프 루프

**pause/resume 패턴** (`uia_events.py:442-470`)
- 메뉴 열림 중 CPU 스파이크 방지
- 이벤트 수신은 유지, 콜백만 무시

```python
class HybridFocusMonitor:
    def __init__(self, max_event_failures=3, prefer_events=True):
        self._use_events = prefer_events
        self._event_failure_count = 0

    def start(self, on_focus_changed):
        if self._use_events:
            success = self._start_event_based()
            if not success:
                self._use_events = False  # 폴링 폴백
        if not self._use_events:
            self._start_polling()
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

# 글로벌 캐시 인스턴스
message_list_cache = UIACache(default_ttl=1.0)
menu_cache = UIACache(default_ttl=0.5)
window_cache = UIACache(default_ttl=1.0)
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
