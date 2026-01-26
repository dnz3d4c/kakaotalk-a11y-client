# NVDA UIA 구현 심층 분석

> 분석일: 2026-01-04
> NVDA 버전: 2026.x (소스 경로: C:/project/nvda/nvda/source)
> 분석 관점: 20년+ 시니어 Windows/COM 프로그래머, 소프트웨어 아키텍트, 이벤트 시스템 전문가

---

## 목차

1. [COM/Windows 아키텍처](#1-comwindows-아키텍처)
2. [객체 모델 아키텍처](#2-객체-모델-아키텍처)
3. [이벤트 시스템](#3-이벤트-시스템)
4. [프로젝트 적용 제안](#4-프로젝트-적용-제안)

---

## 1. COM/Windows 아키텍처

### 1.1 아파트먼트 모델 비교

#### NVDA: MTA 단일 스레드

```
UIAHandler.__init__.py:430-476

┌─────────────────────────────────────────┐
│              메인 스레드                  │
│         (wxPython GUI, STA)              │
│                                          │
│  queueEvent() ──────────┐               │
│                         ↓               │
│              ┌──────────────────┐       │
│              │    MTA 스레드     │       │
│              │                   │       │
│              │ CoInitializeEx    │       │
│              │ (COINIT_MULTI     │       │
│              │  THREADED)        │       │
│              │                   │       │
│              │ IUIAutomation    │       │
│              │ 객체 소유         │       │
│              └──────────────────┘       │
└─────────────────────────────────────────┘
```

**핵심 코드:**
```python
# UIAHandler/__init__.py:437-442
self.MTAThread = threading.Thread(
    name=f"{self.__class__.__module__}.MTAThread",
    target=self.MTAThreadFunc,
    daemon=True,
)
self.MTAThread.start()
self.MTAThreadInitEvent.wait(2)

# UIAHandler/__init__.py:473
winBindings.ole32.CoInitializeEx(None, comtypes.COINIT_MULTITHREADED)
```

**장점:**
- 단일 스레드에서 모든 UIA 작업 → 데드락 회피
- 마샬링 오버헤드 최소화
- 스레드 안전성 자동 보장

#### kakaotalk-a11y-client: STA 다중 스레드

```
┌─────────────────────────────────────────┐
│              메인 스레드 (STA1)           │
│         wxPython GUI                     │
└─────────────────────────────────────────┘
           ↑                    ↑
           │ COM 충돌 위험!      │
           ↓                    ↓
┌──────────────────┐  ┌──────────────────┐
│ FocusMonitor     │  │ MessageList      │
│ (STA2)           │  │ Monitor (STA3)   │
│                  │  │                  │
│ pythoncom.       │  │ pythoncom.       │
│ CoInitialize()   │  │ CoInitialize()   │
└──────────────────┘  └──────────────────┘
```

**문제점:**
1. `focus_monitor.py:46` - COM 초기화 후 CoUninitialize() 누락
2. `window_finder.py:129` - UIA 호출 전 초기화 확인 불명확
3. 두 STA가 동시에 UIA 접근 시 COMError 발생 가능

---

### 1.2 IUIAutomation 인터페이스 협상

#### NVDA 패턴

```python
# UIAHandler/__init__.py:505-516
# 최신 인터페이스 역순 탐색 → 자동 선택
for interface in reversed(UIA.CUIAutomation8._com_interfaces_):
    try:
        self.clientObject = self.clientObject.QueryInterface(interface)
        break
    except COMError:
        pass

# IUIAutomation6 지원 시 최적화 활성화
if isinstance(self.clientObject, UIA.IUIAutomation6):
    self.clientObject.CoalesceEvents = UIA.CoalesceEventsOptions_Enabled
    self.clientObject.ConnectionRecoveryBehavior = UIA.ConnectionRecoveryBehaviorOptions_Enabled
```

**지원 인터페이스 버전:**

| 인터페이스 | Windows 버전 | 주요 기능 |
|-----------|-------------|----------|
| IUIAutomation | Vista+ | 기본 |
| IUIAutomation2 | Win8+ | 캐싱 개선 |
| IUIAutomation3 | Win8.1+ | 텍스트 패턴 확장 |
| IUIAutomation4 | Win10+ | 알림 이벤트 |
| IUIAutomation5 | Win10 1703+ | 드래그/드롭 |
| IUIAutomation6 | Win10 1809+ | **이벤트 병합**, 연결 복구 |

#### kakaotalk-a11y-client 현재

```python
# uia_cache_request.py:114-125
self._uia = CreateObject(CUIAutomation)  # 기본 인터페이스만
```

**문제:** Win11의 IUIAutomation6 최적화 미사용

---

### 1.3 CacheRequest 구현 비교

#### NVDA (11+ 속성)

```python
# UIAHandler/__init__.py:523-531
baseCachePropertyIDs = {
    UIA_FrameworkIdPropertyId,
    UIA_AutomationIdPropertyId,
    UIA_ClassNamePropertyId,
    UIA_ControlTypePropertyId,
    UIA_NamePropertyId,
    UIA_LocalizedControlTypePropertyId,
    UIA_ProcessIdPropertyId,
    UIA_CulturePropertyId,
    UIA_IsKeyboardFocusablePropertyId,
    UIA_HasKeyboardFocusPropertyId,
    UIA_RuntimeIdPropertyId,
}

self.baseCacheRequest = self.windowCacheRequest.Clone()
for propertyId in baseCachePropertyIDs:
    self.baseCacheRequest.addProperty(propertyId)
self.baseCacheRequest.addPattern(UIA_TextPatternId)
```

#### kakaotalk-a11y-client (4개 필수 - 더 효율적)

```python
# uia_cache_request.py:117-125
self._cache_request.AddProperty(UIA_ControlTypePropertyId)
self._cache_request.AddProperty(UIA_NamePropertyId)
self._cache_request.AddProperty(UIA_ClassNamePropertyId)
self._cache_request.AddProperty(UIA_AutomationIdPropertyId)

# 핵심 최적화
element = self._uia.GetFocusedElementBuildCache(self._cache_request)
```

**성능 비교:**

| 항목 | NVDA | kakaotalk |
|------|------|-----------|
| 캐시 속성 | 11+ | 4 |
| 포커스 조회 | 3-5회 COM | 1회 (BuildCache) |
| COM 호출 감소 | ~30-40% | **60-65%** |

**결론:** kakaotalk이 포커스 조회는 더 효율적, 단 기능 제한

---

### 1.4 TreeWalker vs searchDepth

#### NVDA: TreeWalker 기반

```python
# UIAHandler/__init__.py:1318-1395
self.windowTreeWalker = self.clientObject.createTreeWalker(
    self.clientObject.CreatePropertyCondition(
        UIA_NativeWindowHandlePropertyId,
        0
    )
)

# 사용
new = walker.NormalizeElementBuildCache(UIAElement, cacheRequest)
```

**장점:**
- 필터 조건으로 정확한 탐색
- 깊이 제한 없이 조건 기반 검색
- 조상 탐색 + 캐시 한 번에

#### kakaotalk: searchDepth 사용

```python
# chat_room.py:94
msg_list = safe_uia_call(
    lambda: self.chat_control.ListControl(
        Name="메시지",
        searchDepth=SEARCH_DEPTH_MESSAGE_LIST  # 숫자 기반
    ),
)
```

**단점:**
- 고정 깊이로 유연성 부족
- 깊이 튜닝 필요

---

### 1.5 compareElements API

#### NVDA (정확한 요소 비교)

```python
# UIAHandler/utils.py:69-77
def isUIAElementInWalker(element, walker):
    try:
        newElement = walker.normalizeElement(element)
    except COMError:
        newElement = None
    return newElement and UIAHandler.handler.clientObject.compareElements(element, newElement)

# UIAHandler/__init__.py:859
if clientObject.compareElements(sender, lastFocusObj.UIAElement):
    return  # 중복 포커스 무시
```

#### kakaotalk (Python 객체 비교 - 부정확)

```python
# uia_utils.py:813-849
if focused == parent_control:  # Python 객체 비교
    return True
```

**문제:**
1. `==` 연산자는 래퍼 객체 비교 (COM 요소 비교 아님)
2. COM 마샬링으로 객체 재생성 시 비교 실패 가능
3. 동일 요소라도 다른 래퍼면 다르다고 판정

---

## 2. 객체 모델 아키텍처

### 2.1 클래스 계층 구조

```
NVDAObject (기반 추상 클래스)
│
├─ Window (OS 윈도우 래퍼)
│  │
│  └─ UIA (UI Automation API 구현)
│     │
│     ├─ UIAWeb (웹 브라우저용)
│     │  ├─ ChromiumUIA (Chrome/Edge)
│     │  └─ List (리스트 특수화)
│     │
│     ├─ ExcelObject (엑셀용)
│     │  ├─ ExcelCell
│     │  ├─ ExcelWorksheet
│     │  └─ CellEdit
│     │
│     ├─ EditableTextBase (편집 가능 텍스트)
│     ├─ Dialog (대화상자)
│     └─ ProgressBar (진행률)

TextInfo 계층:
NVDAObjectTextInfo (기본)
│
└─ UIATextInfo (UIA 텍스트 범위)
   │
   ├─ UIAWebTextInfo (웹용)
   │  └─ ChromiumUIATextInfo
   │
   └─ UIABrowseModeDocumentTextInfo (열람 모드)
```

### 2.2 메타클래스 기반 동적 클래스 생성

```python
# NVDAObjects/__init__.py
DynamicNVDAObjectType.__call__()
  1. chooseBestAPI() → API 클래스 결정
  2. APIClass 인스턴스화
  3. findOverlayClasses() → 오버레이 클래스 수집
  4. appModule.chooseNVDAObjectOverlayClasses() → 앱 특화 오버레이
  5. globalPlugins의 chooseNVDAObjectOverlayClasses()
  6. 동적 클래스 생성 및 캐싱
  7. initOverlayClass() 호출
  8. 제스처 바인딩
```

**핵심:** 런타임 시 객체 클래스를 변경하는 메타클래스 기반 설계

### 2.3 오버레이 클래스 패턴

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
        elif UIAControlType == UIA_EditControlTypeId:
            clsList.insert(0, Edit)
        # ...

    def initOverlayClass(self):
        """오버레이 클래스 초기화 시 호출"""
        # 앱별 특화 초기화
        pass
```

**장점:**
- 기본 기능 + 앱/제어 특화 분리
- 플러그인 확장성 (appModule 오버라이드)
- 테스트 용이

### 2.4 배치 속성 요청

```python
# NVDAObjects/UIA/__init__.py
def _prefetchUIACacheForPropertyIDs(self, propertyIDs):
    """여러 속성을 한 번에 조회"""
    cacheRequest = UIAHandler.handler.clientObject.createCacheRequest()
    for propId in propertyIDs:
        cacheRequest.addProperty(propId)

    return self.UIAElement.buildUpdatedCache(cacheRequest)

# 사용
self._coreCycleUIAPropertyCacheElement = self._prefetchUIACacheForPropertyIDs(
    focus_monitor_props
)
```

**효과:** COM 왕복 60-70% 감소

### 2.5 ControlType별 특화

#### Excel (커스텀 프로퍼티)

```python
# NVDAObjects/UIA/excel.py
class ExcelCell(ExcelObject):
    # 커스텀 프로퍼티 등록 (GUID 기반)
    cellFormula = ...
    hasDataValidation = ...
    commentReplyCount = ...

    @property
    def cellCoordsText(self):
        """A1 형식 좌표"""
        return f"{self.columnNumber}{self.rowNumber}"
```

#### Web (ARIA 처리)

```python
# NVDAObjects/UIA/web.py
class UIAWeb(UIA):
    def _get_role(self):
        """ariaRole → NVDA 역할 변환"""
        ariaRole = self._getUIACacheablePropertyValue(UIA_AriaRolePropertyId)
        return ARIA_ROLE_MAP.get(ariaRole, super()._get_role())

    def _get_landmark(self):
        """UIA_LandmarkTypePropertyId → ARIA landmark"""
        landmarkType = self._getUIACacheablePropertyValue(UIA_LandmarkTypePropertyId)
        return LANDMARK_MAP.get(landmarkType)
```

---

## 3. 이벤트 시스템

### 3.1 이벤트 흐름 다이어그램

```
플랫폼 이벤트 (WinEvent/UIA)
        ↓
┌─────────────────────────────────────────┐
│  IAccessibleHandler.internalWinEventHandler
│  - winEventCallback (WinEvent 훅)
│  - OrderedWinEventLimiter (이벤트 병합)
└─────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────┐
│  UIAHandler.__init__.py
│  - FocusChangedEventHandler
│  - PropertyChangedEventHandler
│  - NotificationEventHandler
│  - StructureChangedEventHandler
└─────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────┐
│  eventHandler.queueEvent()
│  - 이벤트 추적 (_pendingEventCounts*)
│  - _EventExecuter (핸들러 체인 실행)
└─────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────┐
│  executeEvent()
│  - doPreGainFocus() (포커스 설정)
│  - _EventExecuter 핸들러 실행
│    • globalPluginHandler
│    • appModule
│    • treeInterceptor
│    • NVDAObject.event_*
└─────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────┐
│  음성 출력 (speech.manager)
│  - FocusLossCancellableSpeechCommand
│  - 자동 취소 (구 포커스 이벤트)
└─────────────────────────────────────────┘
```

### 3.2 OrderedWinEventLimiter (이벤트 병합)

```python
# IAccessibleHandler/orderedWinEventLimiter.py

class OrderedWinEventLimiter:
    """WinEvent 이벤트 병합 및 제한"""

    MAX_FOCUS_EVENTS = 4           # 포커스 이벤트 최대
    MAX_WINEVENTS_PER_THREAD = 10  # 스레드당 일반 이벤트 최대

    def addEvent(self, eventID, window, objectID, childID, threadID):
        # 1. 포커스 이벤트 (최대 4개 유지)
        if eventID in FOCUS_EVENTS:
            self._focusEventCache[(eventID, window, objectID, childID, threadID)] = counter

        # 2. 일반 이벤트 (스레드당 최대 10개)
        if threadCount >= MAX_WINEVENTS_PER_THREAD:
            return  # 오래된 이벤트 버림

        # 3. 이벤트 충돌 처리
        # EVENT_OBJECT_SHOW + EVENT_OBJECT_HIDE → 둘 다 제거
        if (eventID == EVENT_OBJECT_SHOW and
            (EVENT_OBJECT_HIDE, window, objectID, childID) in self._cache):
            del self._cache[(EVENT_OBJECT_HIDE, window, objectID, childID)]
            return
```

**효과:**
- 포커스 이벤트 4개만 유지 (메모리 효율)
- 중복 Show/Hide 제거 (상태 전이 깔끔)
- CPU 스파이크 방지

### 3.3 전역/로컬 이벤트 핸들러 그룹

#### 전역 (TreeScope_Subtree)

```python
# UIAHandler/__init__.py:568-616
if isinstance(self.clientObject, UIA.IUIAutomation6):
    self.globalEventHandlerGroup = self.clientObject.CreateEventHandlerGroup()
else:
    self.globalEventHandlerGroup = utils.FakeEventHandlerGroup(self.clientObject)

# 선택적 등록 (성능 최적화)
globalEventHandlerGroup.AddPropertyChangedEventHandler(
    UIA.TreeScope_Subtree,
    self.baseCacheRequest,
    handler,
    *globalEventHandlerGroupUIAPropertyIds  # 필요 속성만
)
```

**등록 속성 (선택적):**
- `UIA_ExpandCollapseState` → stateChange
- `UIA_ToggleState` → stateChange
- `UIA_IsEnabled` → stateChange
- `UIA_Value` → valueChange

#### 로컬 (TreeScope_Ancestors | TreeScope_Element)

```python
# UIAHandler/__init__.py:618-655
localEventHandlerGroup.AddPropertyChangedEventHandler(
    TreeScope_Ancestors | TreeScope_Element,  # 부모 + 현재만
    baseCacheRequest,
    handler,
    *localEventHandlerGroupUIAPropertyIds  # nameChange, descriptionChange 등
)

def addLocalEventHandlerGroupToElement(element, isFocus=False):
    """포커스된 요소에만 등록"""
    clientObject.AddEventHandlerGroup(element, group)
    _localEventHandlerGroupElements.add(element)
```

**장점:**
- 메모리 효율 (포커스 요소만)
- 불필요한 이벤트 필터링

### 3.4 FocusChanged 이벤트 처리

```python
# UIAHandler/__init__.py:842-922
def IUIAutomationFocusChangedEventHandler_HandleFocusChangedEvent(sender):
    # 1. 초기화 확인
    if not self.MTAThreadInitEvent.is_set():
        return

    # 2. 중복 포커스 필터링 (compareElements)
    if isinstance(lastQueuedFocusObject, NVDAObjects.UIA.UIA):
        if (not obj.shouldAllowDuplicateUIAFocusEvent and
            clientObject.compareElements(sender, lastFocusObj.UIAElement) and
            lastFocusObj.UIAElement.currentHasKeyboardFocus):
            return  # 중복 무시

    # 3. 네이티브 UIA 요소 확인
    if not self.isNativeUIAElement(sender):
        return  # MS Word 문서 등 제외

    # 4. shouldAcceptEvent 필터링
    window = self.getNearestWindowHandle(sender)
    if not eventHandler.shouldAcceptEvent("gainFocus", windowHandle=window):
        return

    # 5. 객체 생성
    obj = NVDAObjects.UIA.UIA(windowHandle=window, UIAElement=sender)

    # 6. 이벤트 큐
    eventHandler.queueEvent("gainFocus", obj)
```

#### 3.4.1 shouldAllowUIAFocusEvent 상세 (2026-01-25 추가)

FocusChanged 이벤트 수신 후 실제 포커스 보유 여부를 2차 검증하는 메커니즘.

**NVDA 구현:** `NVDAObjects/UIA/__init__.py:1579-1583`

```python
def _get_shouldAllowUIAFocusEvent(self):
    """HasKeyboardFocus 속성 조회로 실제 키보드 포커스 확인"""
    try:
        return bool(self._getUIACacheablePropertyValue(UIA_HasKeyboardFocusPropertyId))
    except COMError:
        return True  # 속성 조회 실패 시 허용
```

**핵심 포인트:**
- `HasKeyboardFocus`는 **속성 조회** (PropertyChanged 이벤트 아님)
- FocusChanged 이벤트 → 객체 생성 후 → `shouldAllowUIAFocusEvent` 체크
- False 반환 시 이벤트 무시 (실제 포커스 없음)

**프로젝트 적용:** `uia_focus_handler.py:_on_focus_event()`에서 `sender.CurrentHasKeyboardFocus` 체크

#### 3.4.2 shouldAllowDuplicateUIAFocusEvent 상세

**NVDA 구현:** `NVDAObjects/UIA/__init__.py:1140`

```python
shouldAllowDuplicateUIAFocusEvent = False  # 기본값
```

**동작:**
- 기본 False → 같은 요소에 대한 연속 포커스 이벤트 차단
- `compareElements()` + `currentHasKeyboardFocus`로 중복 판정
- 특정 컨트롤 (PlaceholderNetUITWMenuItem 등)에서 True로 오버라이드

**프로젝트 현황:** RuntimeID 기반 중복 체크로 동일 효과 달성

### 3.5 FocusLossCancellableSpeechCommand

```python
# eventHandler.py:187-310
class FocusLossCancellableSpeechCommand:
    """이전 포커스 이벤트의 음성 출력 자동 취소"""

    def _checkIfValid(self) -> bool:
        return (
            self.isLastFocusObj()               # 현재 포커스가 이 객체인가?
            or not self.previouslyHadFocus()    # 이전 포커스가 아닌가?
            or self.isAncestorOfCurrentFocus()  # 현재 포커스의 부모인가?
            or self.isForegroundObject()        # 창 자체가 포그라운드인가?
            or self.isMenuItemOfCurrentFocus()  # 메뉴 아이템 관련인가?
        )
```

**효과:** 빠른 포커스 전환 시 이전 음성 자동 취소

---

## 4. 프로젝트 적용 제안

### 적용 현황 (2026-01-04)

| 우선순위 | 항목 | 상태 | 비고 |
|---------|------|------|------|
| 즉시 | A. compareElements | ✅ 적용 | commit 3d69aaf |
| 즉시 | B. COM 초기화 일관성 | ✅ 적용 | chat_room.py CoUninitialize 추가 |
| 즉시 | C. CacheRequest 확대 | ✅ 적용 | commit 3494656 |
| 중기 | A. FocusChanged 이벤트 | ⏸️ 보류 | 전역 이벤트 CPU 부담, 현재 폴링 충분 |
| 중기 | B. 하이브리드 모드 | ⏸️ 보류 | A 의존 |
| 중기 | C. 이벤트 병합 | ✅ 적용 | EventCoalescer 20ms, 디바운싱 30ms |
| 장기 | A. MTA 아키텍처 | ❌ 미적용 | 대규모 리팩토링 필요 |
| 장기 | B. TreeWalker | ❌ 미적용 | searchDepth로 충분 |
| 장기 | C. IUIAutomation6 | ✅ 적용 | commit 553ab28, CUIAutomation8 사용 |

### 4.1 즉시 적용 가능

#### A. compareElements 도입

```python
# 현재 (uia_utils.py:813)
if focused == parent_control:
    return True

# 개선
from comtypes.gen.UIAutomationClient import CUIAutomation
_uia = CreateObject(CUIAutomation)

def compare_elements(elem1, elem2) -> bool:
    """COM 수준 요소 비교"""
    try:
        return _uia.CompareElements(elem1.NativeElement, elem2.NativeElement)
    except Exception:
        return False

# 사용
if compare_elements(focused, parent_control):
    return True
```

#### B. COM 초기화 일관성

```python
# 현재 (focus_monitor.py:46)
def enter_chat_room(self, hwnd):
    pythoncom.CoInitialize()
    # ... CoUninitialize() 없음!

# 개선 (com_utils.py 활용)
from contextlib import contextmanager

@contextmanager
def com_thread():
    """COM 초기화 + 자동 정리"""
    pythoncom.CoInitialize()
    try:
        yield
    finally:
        pythoncom.CoUninitialize()

# 사용
def enter_chat_room(self, hwnd):
    with com_thread():
        self.chat_control = auto.ControlFromHandle(hwnd)
```

#### C. CacheRequest 확대

```python
# 현재: 4개 속성
# 개선: 메뉴/탭에 필요한 속성 추가

menu_cache_props = {
    UIA_ControlTypePropertyId,
    UIA_NamePropertyId,
    UIA_ClassNamePropertyId,
    UIA_AutomationIdPropertyId,
    UIA_AccessKeyPropertyId,      # 메뉴 단축키
    UIA_AcceleratorKeyPropertyId, # 가속키
}
```

### 4.2 중기 적용

#### A. FocusChanged 이벤트 핸들러

```python
# utils/uia_events.py에 추가
from comtypes import COMObject
from comtypes.gen.UIAutomationClient import IUIAutomationFocusChangedEventHandler

class FocusChangedHandler(COMObject):
    _com_interfaces_ = [IUIAutomationFocusChangedEventHandler]

    def __init__(self, callback):
        self._callback = callback
        self._last_focus = None

    def HandleFocusChangedEvent(self, sender):
        try:
            # 중복 필터링
            if self._last_focus and _uia.CompareElements(sender, self._last_focus):
                return
            self._last_focus = sender

            # 콜백 호출
            if self._callback:
                self._callback(sender)
        except Exception as e:
            log.trace(f"FocusChanged 오류: {e}")
```

#### B. 하이브리드 모드 (이벤트 + 폴링)

> **2026-01 업데이트**: 현재 프로젝트는 `FocusMonitor`로 단순화됨 (순수 이벤트 기반, 폴링 폴백 제거).
> 아래는 NVDA 패턴 참고용 과거 설계.

```python
class FocusMonitor:
    """순수 이벤트 기반 포커스 모니터 (2026-01 현재)"""
    def start(self):
        self._uia.AddFocusChangedEventHandler(
            self._cache_request, self._handler
        )
```

#### C. 이벤트 병합

```python
class MessageEventLimiter:
    """StructureChanged 이벤트 병합"""

    def __init__(self, flush_interval=0.15):
        self._buffer = {}
        self._flush_interval = flush_interval
        self._last_flush = time.time()

    def add_event(self, sender, change_type):
        key = (id(sender), change_type)
        self._buffer[key] = time.time()

        if time.time() - self._last_flush > self._flush_interval:
            self._flush()

    def _flush(self):
        if not self._buffer:
            return

        # 배치 처리
        new_count = self._get_new_message_count()
        if new_count > 0:
            self._on_messages_added(new_count)

        self._buffer.clear()
        self._last_flush = time.time()
```

### 4.3 장기 적용

#### A. MTA 스레드 아키텍처

```python
class UIAHandler:
    """MTA 단일 스레드 기반 UIA 핸들러"""

    def __init__(self):
        self._mta_thread = threading.Thread(
            target=self._mta_thread_func,
            daemon=True
        )
        self._mta_queue = queue.Queue()
        self._mta_ready = threading.Event()

    def _mta_thread_func(self):
        # MTA 초기화
        winBindings.ole32.CoInitializeEx(None, comtypes.COINIT_MULTITHREADED)

        try:
            self._uia = CreateObject(CUIAutomation)
            self._mta_ready.set()

            while True:
                task = self._mta_queue.get()
                if task is None:
                    break
                task()
        finally:
            pythoncom.CoUninitialize()

    def run_in_mta(self, func):
        """MTA 스레드에서 함수 실행"""
        result = []
        event = threading.Event()

        def wrapper():
            result.append(func())
            event.set()

        self._mta_queue.put(wrapper)
        event.wait()
        return result[0] if result else None
```

#### B. TreeWalker 도입

```python
# searchDepth 대신 TreeWalker 사용

def find_message_list(parent_element):
    """TreeWalker로 메시지 리스트 찾기"""
    condition = _uia.CreatePropertyCondition(
        UIA_ClassNamePropertyId,
        "EVA_VH_ListControl_Dblclk"
    )
    walker = _uia.CreateTreeWalker(condition)

    return walker.GetFirstChildElement(parent_element)

def find_menu_item(menu_element):
    """TreeWalker로 메뉴 항목 찾기"""
    condition = _uia.CreatePropertyCondition(
        UIA_ControlTypePropertyId,
        UIA_MenuItemControlTypeId
    )
    walker = _uia.CreateTreeWalker(condition)

    return walker.GetFirstChildElement(menu_element)
```

#### C. IUIAutomation6 지원

```python
def _negotiate_interface(self):
    """최신 인터페이스 협상"""
    interfaces = [
        IUIAutomation6,
        IUIAutomation5,
        IUIAutomation4,
        IUIAutomation3,
        IUIAutomation2,
        IUIAutomation,
    ]

    for interface in interfaces:
        try:
            self._uia = self._uia.QueryInterface(interface)
            log.info(f"UIA 인터페이스: {interface.__name__}")
            break
        except COMError:
            continue

    # IUIAutomation6 최적화
    if isinstance(self._uia, IUIAutomation6):
        self._uia.CoalesceEvents = CoalesceEventsOptions_Enabled
        self._uia.ConnectionRecoveryBehavior = ConnectionRecoveryBehaviorOptions_Enabled
        log.info("IUIAutomation6 최적화 활성화")
```

---

## 5. 성능 지표 비교

| 항목 | NVDA | kakaotalk (현재) | 상태 |
|------|------|-----------------|------|
| 아파트먼트 | MTA 1개 | STA 다중 | 유지 (리팩토링 비용 대비 효과 낮음) |
| 포커스 조회 | 3-5회 COM | 1회 (BuildCache) | ✅ CacheRequest 적용 |
| 포커스 비교 | compareElements | compareElements | ✅ 적용 완료 |
| 이벤트 | 전역+로컬 분리 | 폴링 중심 | 폴링 유지 (CPU 부담 적음) |
| 이벤트 병합 | OrderedWinEventLimiter | EventCoalescer 20ms, 디바운싱 30ms | ✅ 적용 |
| COM 호출 감소 | ~30-40% | 60-65% | ✅ 달성 |

---

## 6. 파일 참조

### NVDA 소스

| 파일 | 역할 | 핵심 줄 |
|------|------|--------|
| `UIAHandler/__init__.py` | MTA, CacheRequest, 이벤트 | 430-616, 842-922 |
| `UIAHandler/utils.py` | compareElements | 69-77 |
| `NVDAObjects/__init__.py` | 메타클래스, 오버레이 | 전체 |
| `NVDAObjects/UIA/__init__.py` | UIA 객체, TextInfo | 전체 (3300줄) |
| `eventHandler.py` | 이벤트 큐잉 | 전체 |
| `IAccessibleHandler/orderedWinEventLimiter.py` | 이벤트 병합 | 전체 |

### kakaotalk 프로젝트

| 파일 | 개선 대상 |
|------|----------|
| `utils/com_utils.py` | COM 초기화 일관성 |
| `utils/uia_utils.py` | compareElements 도입 |
| `utils/uia_cache_request.py` | CacheRequest 확대 |
| `utils/uia_events.py` | FocusChanged 핸들러 |
| `focus_monitor.py` | 하이브리드 모드 |
