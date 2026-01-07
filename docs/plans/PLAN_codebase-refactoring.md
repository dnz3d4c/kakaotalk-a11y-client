# Implementation Plan: 코드베이스 리팩토링

**Status**: 🔄 In Progress
**Started**: 2026-01-07
**Last Updated**: 2026-01-07
**Phase 1**: ✅ Complete (91 tests passed)

---

**CRITICAL INSTRUCTIONS**: After completing each phase:
1. Check off completed task checkboxes
2. Run all quality gate validation commands
3. Verify ALL quality gate items pass
4. Update "Last Updated" date above
5. Document learnings in Notes section
6. Only then proceed to next phase

**DO NOT skip quality gates or proceed with failing checks**

---

## Overview

### Feature Description
UIA 로직 분리 작업 후 전체 코드베이스 점검 및 리팩토링. God Class 해소, 하드코딩 상수 분리, 모듈 책임 명확화.

### Success Criteria
- [ ] 모든 파일 300줄 이하 유지
- [ ] 하드코딩된 상수 config.py로 중앙 집중화
- [ ] 기존 import 경로 호환성 유지
- [ ] 전체 테스트 통과
- [ ] 프로그램 정상 동작

### User Impact
- 코드 유지보수성 향상
- 테스트 용이성 증가
- 설정 변경 용이성

---

## Architecture Decisions

| Decision | Rationale | Trade-offs |
|----------|-----------|------------|
| 기능별 파일 분리 | 단일 책임 원칙, 테스트 용이성 | 파일 수 증가 (48 → 60개) |
| re-export로 호환성 유지 | 기존 import 경로 유지 | 약간의 간접 참조 |
| config.py 중앙 집중화 | 설정 변경 용이 | config 의존성 증가 |

---

## Dependencies

### Required Before Starting
- [ ] 현재 테스트 통과 상태 확인
- [ ] 프로그램 정상 동작 확인

### External Dependencies
- 없음 (내부 리팩토링)

---

## Test Strategy

### Testing Approach
리팩토링이므로 TDD 대신 기존 테스트 유지 + 회귀 테스트 중심

### Test Pyramid for This Feature
| Test Type | Coverage Target | Purpose |
|-----------|-----------------|---------|
| **Unit Tests** | 기존 유지 | 분리된 모듈 개별 테스트 |
| **Integration Tests** | 기존 유지 | 모듈 간 연동 검증 |
| **Manual Tests** | 전체 기능 | 프로그램 동작 확인 |

### Validation Commands
```bash
# 테스트 실행
uv run pytest tests/unit/

# 프로그램 실행 테스트
uv run kakaotalk-a11y --debug
```

---

## Implementation Phases

### Phase 1: 하드코딩 상수 분리
**Goal**: 15곳의 하드코딩된 값을 config.py로 중앙 집중화
**Status**: Pending

#### Tasks

- [ ] **Task 1.1**: config.py에 상수 추가
  - File: `src/kakaotalk_a11y_client/config.py`
  - 추가할 상수:
    ```python
    # UIA 이벤트 설정
    TIMING_EVENT_PUMP_INTERVAL = 0.05

    # 성능 임계값
    PERF_SLOW_THRESHOLD_MS = 100
    PERF_COMPARISON_THRESHOLD_PCT = 20.0

    # 캐시 설정
    CACHE_DEFAULT_TTL = 1.0

    # 탐색 설정
    SEARCH_MAX_SECONDS_LIST = 0.5
    SEARCH_MAX_SECONDS_FALLBACK = 0.3

    # 템플릿 매칭
    CV_NMS_THRESHOLD = 0.3

    # 포커스 모니터
    TIMING_MAX_WARMUP = 5.0
    TIMING_NAVIGATION_GRACE = 1.0
    ```

- [ ] **Task 1.2**: detector.py 수정
  - File: `src/kakaotalk_a11y_client/detector.py:75`
  - 변경: `nms_threshold=0.3` → `nms_threshold=CV_NMS_THRESHOLD`

- [ ] **Task 1.3**: focus_monitor.py 수정
  - File: `src/kakaotalk_a11y_client/focus_monitor.py:133, 272`
  - 변경: `max_warmup=5.0` → `TIMING_MAX_WARMUP`
  - 변경: `grace_period=1.0` → `TIMING_NAVIGATION_GRACE`

- [ ] **Task 1.4**: navigation/message_monitor.py 수정
  - File: `src/kakaotalk_a11y_client/navigation/message_monitor.py:100, 147`
  - 변경: `maxSearchSeconds=0.5` → `SEARCH_MAX_SECONDS_LIST`
  - 변경: `maxSearchSeconds=0.3` → `SEARCH_MAX_SECONDS_FALLBACK`

- [ ] **Task 1.5**: utils 모듈 수정
  - Files:
    - `utils/uia_events.py:190, 512` → `TIMING_EVENT_PUMP_INTERVAL`
    - `utils/uia_cache.py:133` → `CACHE_DEFAULT_TTL`
    - `utils/profiler.py:94, 206` → `PERF_*` 상수

#### Quality Gate

**Build & Tests**:
- [ ] `uv run pytest tests/unit/` 통과
- [ ] `uv run kakaotalk-a11y --debug` 정상 실행

**Validation Commands**:
```bash
uv run pytest tests/unit/
uv run kakaotalk-a11y --debug
```

---

### Phase 2: uia_utils.py 분해
**Goal**: 734줄 파일을 4개 모듈로 분리
**Status**: Pending

#### Tasks

- [ ] **Task 2.1**: uia_reliability.py 생성
  - File: `src/kakaotalk_a11y_client/utils/uia_reliability.py` (신규)
  - 이동할 코드:
    - `KAKAO_GOOD_UIA_CLASSES`
    - `KAKAO_BAD_UIA_CLASSES`
    - `KAKAO_IGNORE_PATTERNS`
    - `is_good_uia_element()`
    - `should_use_uia_for_window()`
  - 예상: ~70줄

- [ ] **Task 2.2**: uia_exceptions.py 생성
  - File: `src/kakaotalk_a11y_client/utils/uia_exceptions.py` (신규)
  - 이동할 코드:
    - `safe_uia_call()`
    - `handle_uia_errors()` 데코레이터
    - `get_children_safe()`
    - `get_focused_safe()`
    - `get_parent_safe()`
  - 예상: ~60줄

- [ ] **Task 2.3**: uia_tree_dump.py 생성
  - File: `src/kakaotalk_a11y_client/utils/uia_tree_dump.py` (신규)
  - 이동할 코드:
    - `dump_tree()`
    - `dump_element_details()`
    - `dump_tree_json()`
    - `compare_trees()`
    - `format_tree_diff()`
  - 예상: ~320줄

- [ ] **Task 2.4**: uia_utils.py 축소 + re-export
  - File: `src/kakaotalk_a11y_client/utils/uia_utils.py`
  - 유지할 코드:
    - `SmartListFilter` 클래스
    - `get_children_filtered()`
    - `find_all_descendants()`
    - `find_first_descendant()`
    - `get_children_recursive()`
    - `is_focus_in_control()`
    - `is_focus_in_message_list()`
  - 상단에 re-export 추가:
    ```python
    from .uia_reliability import (
        is_good_uia_element, should_use_uia_for_window,
        KAKAO_GOOD_UIA_CLASSES, KAKAO_BAD_UIA_CLASSES,
    )
    from .uia_exceptions import (
        safe_uia_call, handle_uia_errors,
        get_children_safe, get_focused_safe, get_parent_safe,
    )
    ```
  - 예상: ~280줄

- [ ] **Task 2.5**: utils/__init__.py 업데이트
  - File: `src/kakaotalk_a11y_client/utils/__init__.py`
  - 새 모듈 export 추가

#### Quality Gate

**Build & Tests**:
- [ ] 기존 import 경로 동작: `from .utils.uia_utils import safe_uia_call`
- [ ] `uv run pytest tests/unit/test_uia_cache.py` 통과
- [ ] 프로그램 정상 실행

**Validation Commands**:
```bash
uv run pytest tests/unit/
uv run kakaotalk-a11y --debug
```

---

### Phase 3: uia_events.py 분해
**Goal**: 711줄 파일을 2개 모듈로 분리
**Status**: Pending

#### Tasks

- [ ] **Task 3.1**: uia_focus_handler.py 생성
  - File: `src/kakaotalk_a11y_client/utils/uia_focus_handler.py` (신규)
  - 이동할 코드:
    - `FocusEvent` dataclass
    - `FocusChangedHandler` COM 객체
    - `FocusMonitor` 클래스
    - `get_focus_monitor()`
    - `start_focus_monitoring()`
    - `stop_focus_monitoring()`
  - 예상: ~280줄

- [ ] **Task 3.2**: uia_message_monitor.py 생성
  - File: `src/kakaotalk_a11y_client/utils/uia_message_monitor.py` (신규)
  - 이동할 코드:
    - `MessageEvent` dataclass
    - `StructureChangedHandler` COM 객체
    - `MessageListMonitor` 클래스
  - 예상: ~380줄

- [ ] **Task 3.3**: uia_events.py 축소 + re-export
  - File: `src/kakaotalk_a11y_client/utils/uia_events.py`
  - re-export만 유지:
    ```python
    from .uia_focus_handler import (
        FocusEvent, FocusMonitor,
        get_focus_monitor, start_focus_monitoring, stop_focus_monitoring,
    )
    from .uia_message_monitor import (
        MessageEvent, MessageListMonitor,
    )
    ```
  - 예상: ~50줄

#### Quality Gate

**Build & Tests**:
- [ ] FocusMonitor 정상 동작
- [ ] MessageListMonitor 정상 동작
- [ ] `uv run pytest tests/unit/` 통과

**Manual Test Checklist**:
- [ ] 카카오톡 포커스 이동 시 음성 출력
- [ ] 새 메시지 도착 시 감지

---

### Phase 4: focus_monitor.py 분해
**Goal**: 418줄 파일을 3개 모듈로 분리
**Status**: Pending

#### Tasks

- [ ] **Task 4.1**: focus_reader.py 생성
  - File: `src/kakaotalk_a11y_client/focus_reader.py` (신규)
  - 새 클래스:
    ```python
    class FocusReader:
        def __init__(self, uia_adapter, speak_callback):
            self._uia = uia_adapter
            self._speak = speak_callback
            self._last_focused_name = None

        def speak_item(self, name, control_type=""): ...
        def speak_current_focus(self): ...
        def speak_last_message(self, list_control): ...
    ```
  - 예상: ~120줄

- [ ] **Task 4.2**: menu_reader.py 생성
  - File: `src/kakaotalk_a11y_client/menu_reader.py` (신규)
  - 새 클래스:
    ```python
    class MenuReader:
        def __init__(self, uia_adapter, speak_callback):
            self._uia = uia_adapter
            self._speak = speak_callback

        def get_first_menu_item_name(self, menu_hwnd): ...
        def read_menu_item(self, control, first_entry): ...
    ```
  - 예상: ~80줄

- [ ] **Task 4.3**: focus_monitor.py에서 위임 패턴 적용
  - File: `src/kakaotalk_a11y_client/focus_monitor.py`
  - 변경:
    - FocusReader, MenuReader 의존성 주입
    - `_speak_*` 메서드 → `self._focus_reader.*` 위임
    - `_get_first_menu_item_name` → `self._menu_reader.*` 위임
  - 예상: ~220줄

#### Quality Gate

**Build & Tests**:
- [ ] Mock 의존성 주입 테스트 통과
- [ ] `uv run pytest tests/unit/test_focus_monitor.py` 통과
- [ ] 포커스 읽기 정상 동작

**Manual Test Checklist**:
- [ ] 채팅방 진입 시 메시지 읽기
- [ ] 메뉴 열림 시 첫 항목 읽기
- [ ] 포커스 이동 시 항목 읽기

---

### Phase 5: hotkey_panel.py 분해
**Goal**: 405줄 파일을 2개 모듈로 분리
**Status**: Pending

#### Tasks

- [ ] **Task 5.1**: hotkey_change_dialog.py 생성
  - File: `src/kakaotalk_a11y_client/gui/hotkey_change_dialog.py` (신규)
  - 이동할 코드:
    - `KEY_CODE_MAP` 상수
    - `format_hotkey()` 함수
    - `HotkeyChangeDialog` 클래스
  - 예상: ~130줄

- [ ] **Task 5.2**: hotkey_panel.py 축소
  - File: `src/kakaotalk_a11y_client/gui/hotkey_panel.py`
  - 변경:
    - import 추가: `from .hotkey_change_dialog import HotkeyChangeDialog, format_hotkey`
    - `HotkeyPanel` 클래스만 유지
  - 예상: ~270줄

#### Quality Gate

**Build & Tests**:
- [ ] GUI 정상 동작
- [ ] 단축키 변경 다이얼로그 동작

**Manual Test Checklist**:
- [ ] 설정 창 열기/닫기
- [ ] 단축키 변경 후 저장
- [ ] 단축키 기본값 복원

---

### Phase 6: 테스트 보강 + 문서
**Goal**: 분리된 모듈 테스트 추가, 문서 업데이트
**Status**: Pending

#### Tasks

- [ ] **Task 6.1**: 새 테스트 파일 추가
  - Files:
    - `tests/unit/test_uia_reliability.py`
    - `tests/unit/test_uia_exceptions.py`
    - `tests/unit/test_focus_reader.py`

- [ ] **Task 6.2**: ARCHITECTURE.md 업데이트
  - File: `docs/ARCHITECTURE.md`
  - 새 모듈 구조 반영

- [ ] **Task 6.3**: CLAUDE.md 업데이트
  - File: `.claude/CLAUDE.md`
  - 새 파일 위치 추가

#### Quality Gate

**Build & Tests**:
- [ ] `uv run pytest tests/` 전체 통과
- [ ] 커버리지 유지 또는 향상

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation Strategy |
|------|-------------|--------|---------------------|
| import 경로 깨짐 | Medium | High | re-export로 호환성 유지 |
| 순환 import | Low | High | TYPE_CHECKING 가드 사용 |
| 런타임 오류 | Low | Medium | 각 Phase별 수동 테스트 |

---

## Rollback Strategy

### If Phase 1 Fails
- config.py 원복
- 각 파일의 하드코딩 값 원복

### If Phase 2-5 Fails
- git stash 또는 git checkout으로 원복
- 분리된 파일 삭제

---

## Progress Tracking

### Completion Status
- **Phase 1**: 0%
- **Phase 2**: 0%
- **Phase 3**: 0%
- **Phase 4**: 0%
- **Phase 5**: 0%
- **Phase 6**: 0%

**Overall Progress**: 0% complete

---

## Notes & Learnings

### Implementation Notes
- (작업 진행하면서 추가)

### Blockers Encountered
- (없음)

---

## References

### Critical Files
- `src/kakaotalk_a11y_client/config.py`
- `src/kakaotalk_a11y_client/utils/uia_utils.py` (734줄)
- `src/kakaotalk_a11y_client/utils/uia_events.py` (711줄)
- `src/kakaotalk_a11y_client/focus_monitor.py` (418줄)
- `src/kakaotalk_a11y_client/gui/hotkey_panel.py` (405줄)

---

## Final Checklist

**Before marking plan as COMPLETE**:
- [ ] All phases completed with quality gates passed
- [ ] Full integration testing performed
- [ ] Documentation updated
- [ ] All import paths verified
- [ ] Program runs normally

---

**Plan Status**: Ready for Review
**Next Action**: Phase 1 시작
**Blocked By**: None
