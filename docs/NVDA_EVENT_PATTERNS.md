# NVDA 이벤트 핸들링 패턴 적용

이 문서는 NVDA 소스코드에서 가져온 이벤트 핸들링 패턴과 프로젝트 적용 내역을 설명한다.

## 적용된 패턴

### 1. FocusChanged 이벤트 등록

**NVDA 참조**: `UIAHandler/__init__.py:842-922`

**이전 방식**:
- 0.1초 폴링으로 `GetFocusedControl()` 호출
- CPU 사용량 높음

**현재 방식**:
- `AddFocusChangedEventHandler()`로 이벤트 등록
- 포커스 변경 시에만 콜백 호출
- 순수 이벤트 기반 (폴링 폴백 제거됨, 2026-01)

**위치**: `src/kakaotalk_a11y_client/utils/uia_events.py`
- `FocusMonitor`: 이벤트 기반 포커스 모니터
- `FocusChangedHandler`: COM 콜백 핸들러

**효과**:
- CPU 사용량 70-80% 감소 (예상)
- 포커스 변경 즉시 감지

---

### 2. CompareElements + 중복 필터링

**NVDA 참조**: `UIAHandler/__init__.py:872-881`

```python
# NVDA 원본
if (
    not lastFocusObj.shouldAllowDuplicateUIAFocusEvent
    and self.clientObject.compareElements(sender, lastFocusObj.UIAElement)
    and lastFocusObj.UIAElement.currentHasKeyboardFocus
):
    return  # 중복 무시
```

**적용 방식**:
```python
# _on_focus_event()에서
if self._last_focus_element:
    is_same = self._uia.CompareElements(sender, self._last_focus_element)
    if is_same:
        return  # 중복 무시
```

**위치**: `src/kakaotalk_a11y_client/utils/uia_events.py:280-288`

**효과**:
- 동일 요소의 중복 포커스 이벤트 제거
- RuntimeId 기반 정확한 비교 (Python 객체 비교보다 정확)
- TTS 끊김 방지

---

### 3. 카카오톡 창 필터링

**NVDA 참조**: `eventHandler.py:shouldAcceptEvent()`

**원리**:
- FocusChanged는 글로벌 이벤트 (모든 앱의 포커스 변경 수신)
- 불필요한 이벤트는 핸들러에서 즉시 무시

**적용 방식**:
```python
# _on_focus_event()에서
hwnd = sender.CurrentNativeWindowHandle
if hwnd and not (is_kakaotalk_window(hwnd) or is_kakaotalk_menu_window(hwnd)):
    return  # 카카오톡 창 외 무시
```

**위치**: `src/kakaotalk_a11y_client/utils/uia_events.py:274-278`

**효과**:
- CPU 스파이크 방지
- 불필요한 처리 제거

---

### 4. 포커스 리다이렉트

**NVDA 참조**: `eventHandler.py:330-333`

```python
# NVDA 원본
if isGainFocus and obj.focusRedirect:
    obj = obj.focusRedirect
```

**적용 시나리오**:
1. **컨텍스트 메뉴 열기 → 첫 번째 메뉴 항목 읽기**
   - 메뉴 컨테이너가 포커스면 첫 번째 MenuItem 찾아서 읽기

**위치**: `src/kakaotalk_a11y_client/focus_monitor.py:176-182`

**효과**:
- 메뉴 열릴 때 즉시 첫 항목(답장) 읽기
- 사용자 경험 개선

---

### 5. 이벤트 스레드 + 메시지 펌프

**NVDA 참조**: `UIAHandler/__init__.py:437-559`

**원리**:
- COM 이벤트는 등록한 스레드에서만 수신 가능
- pythoncom.CoInitialize() 필수
- pythoncom.PumpWaitingMessages()로 이벤트 펌프

**적용 방식**:
```python
def _event_loop(self):
    pythoncom.CoInitialize()
    try:
        self._uia.AddFocusChangedEventHandler(None, self._event_handler)
        while self._running:
            pythoncom.PumpWaitingMessages()
            time.sleep(0.05)
    finally:
        pythoncom.CoUninitialize()
```

**위치**: `src/kakaotalk_a11y_client/utils/uia_events.py:212-251`

---

## 미적용 패턴 (향후 고려)

### isPendingEvents 중복 방지

**NVDA 참조**: `appModules/explorer.py:105-106`

```python
if eventHandler.isPendingEvents("gainFocus"):
    return  # 대기 중인 이벤트 있으면 무시
```

현재는 compareElements로 대체.

### 로컬 이벤트 핸들러 동적 등록

**NVDA 참조**: `NVDAObjects/UIA/__init__.py:1571-1577`

```python
def event_gainFocus(self):
    UIAHandler.handler.addLocalEventHandlerGroupToElement(self.UIAElement, isFocus=True)
```

포커스된 요소에만 세부 이벤트 등록. 현재는 불필요.

---

## 참조 파일

| 패턴 | NVDA 파일 | 라인 |
|------|----------|------|
| FocusChanged 핸들러 | UIAHandler/__init__.py | 842-922 |
| compareElements | UIAHandler/__init__.py | 872-881 |
| focusRedirect | eventHandler.py | 330-333 |
| isPendingEvents | appModules/explorer.py | 105-106 |
| 로컬 이벤트 핸들러 | NVDAObjects/UIA/__init__.py | 1571-1577 |
