# UI/이벤트 분석 표준 절차

새 UI 기능 구현 시 Claude가 따르는 표준 분석 프로세스.

---

## Phase 0: 탐색적 분석 (미지의 케이스)

기존 패턴과 매칭 안 되거나 처음 보는 UI/이벤트인 경우.

### 실행
```powershell
# 모든 이벤트 수집
uv run kakaotalk-a11y --debug --debug-events=all --debug-events-format=json

# 전체 트리 덤프 (깊이 제한 없이)
# 실행 후 Ctrl+Shift+D
```

### 확인할 것
- 어떤 이벤트가 발생하는지 전체 파악
- ControlType이 기존과 다른지
- 이벤트 순서/빈도 패턴

### 새 패턴 발견 시
1. `KAKAO_UIA_QUIRKS.md`에 문서화 (#KAKAO-XXX)
2. 필요시 SmartListFilter 확장
3. 필요시 새 이벤트 핸들러 타입 추가

---

## Phase 1: UI 구조 파악

### 실행
1. 기능 관련 UI 상태 만들기 (예: @ 입력 → 멘션 목록)
2. 트리 덤프 생성:
   ```powershell
   uv run kakaotalk-a11y --debug --debug-dump-on-start
   # 또는 실행 중 Ctrl+Shift+D
   ```

### 확인할 것
- ControlType, Name, ClassName
- 부모-자식 관계 (어느 창 안에 있는지)
- AutomationId (있으면 우선 사용)

### 결과 공유 형식
```
팝업/목록 발견:
- ControlType: [값]
- Name: [값]
- ClassName: [값]
- 부모: [부모 정보]
- 자식 항목 수: [개수]
```

---

## Phase 2: 이벤트 추적

### 기능 유형별 권장 이벤트

| 유형 | 권장 이벤트 | 명령어 |
|------|------------|--------|
| 팝업/드롭다운 | structure, focus | `--debug-events=structure,focus` |
| 목록 항목 추가/제거 | structure | `--debug-events=structure` |
| 입력/편집 | property, focus | `--debug-events=property,focus` |
| 체크박스/토글 | property | `--debug-events=property` |
| 포커스 이동만 | focus | `--debug-events=focus` |
| **미지의 케이스** | all | `--debug-events=all` |

### 실행
```powershell
# 예: 팝업 분석
uv run kakaotalk-a11y --debug --debug-events=structure,focus --debug-events-format=json

# 특정 ControlType만 필터
uv run kakaotalk-a11y --debug --debug-events=focus --debug-events-filter=ListItemControl
```

### 재현 시나리오
1. 기능 트리거 (예: @ 입력)
2. 상호작용 (방향키, 클릭 등)
3. 완료 (선택, 취소 등)

### 결과 공유 형식
```
이벤트 로그:
[시간] STRUCTURE: ChildAdded on [부모] - [자식 정보]
[시간] FOCUS: [요소 정보]
...
```

---

## Phase 3: 기존 패턴 참조

### 유사 기능 매핑

| 새 기능 유형 | 참조할 코드 |
|-------------|------------|
| 팝업 메뉴 | `focus_monitor.py` 메뉴 모드 |
| 실시간 목록 | `message_monitor.py` |
| 목록 탐색 | `chat_room.py` |
| 포커스 추적 | `focus_monitor.py` |

### 확인할 것
- 이벤트 기반 vs 폴링?
- 캐싱 전략?
- 에러 처리 패턴?

---

## Phase 4: 구현 전략 결정

### 결정 항목
1. **감지 방식**: 이벤트 / 폴링 / 하이브리드
2. **캐싱**: 필요 여부, TTL
3. **타이밍**: Grace period 필요?
4. **폴백**: 실패 시 대응

---

## 결과 해석 지원

### 트리 덤프 해석
Claude에게 덤프 일부 공유 시:
- 해당 UI 요소의 역할 추론
- 탐색 경로 제안 (어떤 속성으로 찾을지)
- 기존 패턴과 유사성 분석

### 이벤트 로그 해석
Claude에게 로그 공유 시:
- 이벤트 발생 순서 분석
- 필요한 이벤트 타입 추천
- 디바운싱/필터링 필요 여부 판단

---

## 미지의 케이스 판단 기준

다음 중 하나라도 해당하면 Phase 0부터 시작:

1. **ControlType 불명**: 기존에 처리하지 않은 타입
2. **이벤트 패턴 불명**: 어떤 이벤트가 발생하는지 모름
3. **부모-자식 관계 불명**: 별도 창인지, 인라인 팝업인지 모름
4. **SmartListFilter 미적용**: 빈 항목 필터링 필요 여부 불명

### 미지 → 기존 패턴 전환 조건
- Phase 0에서 수집한 정보로 유형 파악 완료
- 기존 매핑 테이블에 매칭되는 패턴 발견
- 필요시 문서 업데이트 후 Phase 1-4 진행
