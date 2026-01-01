# 카카오톡 UIA 특이점 및 대응

카카오톡 PC 클라이언트에서 발견된 UIA 관련 문제점과 대응 방안입니다.
NVDA 소스코드의 workaround 주석 스타일(#숫자:)을 적용했습니다.

**관련 코드**: `src/kakaotalk_a11y_client/utils/uia_workarounds.py`

---

## #KAKAO-001: 빈 ListItem 대량 발생

### 현상
- 메시지 리스트(`EVA_VH_ListControl_Dblclk`)에 Name이 없는 ListItem 100개 이상 발생
- 가상 스크롤 구현으로 인해 화면 밖 항목은 placeholder로 존재

### 영향
- 전체 항목 순회 시 성능 저하
- 스크린 리더에서 불필요한 "빈 목록 항목" 읽기

### 대응
- `SmartListFilter` 클래스로 빈 항목 필터링
- 연속 빈 항목 15개 발견 시 조기 종료
- 이전 유효 범위 캐싱으로 시작점 최적화

### 코드 위치
- `utils/uia_utils.py:SmartListFilter`

---

## #KAKAO-002: Chromium 광고 영역 UIA 불안정

### 현상
- `Chrome_WidgetWin_*`, `Chrome_RenderWidgetHostHWND` 클래스에서 UIA 접근 불안정
- COMError 또는 긴 지연 발생

### 영향
- 탐색 성능 저하
- 간헐적 크래시

### 대응
- `KAKAO_BAD_UIA_CLASSES`에 등록
- 탐색 시 해당 클래스 제외
- `is_good_uia_element()` 함수로 필터링

### 코드 위치
- `utils/uia_utils.py:KAKAO_BAD_UIA_CLASSES`

---

## #KAKAO-003: AutomationId 불규칙

### 현상
- AutomationId가 숫자만(예: "123456")
- 동일 내용의 여러 요소에 같은 ID
- 빈값 혼재

### 영향
- AutomationId 기반 검색 불안정
- 요소 식별 어려움

### 대응
- AutomationId 의존 최소화
- Name + ControlType 조합 사용
- 부모-자식 관계 기반 탐색

### 코드 위치
- 전체 탐색 코드

---

## #KAKAO-004: ClassName 대부분 없음

### 현상
- 대다수 컨트롤의 ClassName이 빈 문자열
- EVA_* 클래스만 신뢰 가능

### 영향
- ClassName 기반 필터링 제한적

### 대응
- EVA_* 클래스 목록 관리 (`KAKAO_GOOD_UIA_CLASSES`)
- Name + ControlType 우선 사용

### 코드 위치
- `utils/uia_utils.py:KAKAO_GOOD_UIA_CLASSES`

---

## 권장 사항

### 탐색 순서
1. Name 확인
2. ControlType 확인
3. ClassName (EVA_* 만)
4. 부모-자식 관계
5. AutomationId (최후 수단)

### 성능 최적화
- `searchDepth` 최소화 (기본 6 이하)
- 빈 항목 조기 필터링
- TTL 캐싱 활용 (0.5초)

### 에러 처리
- 모든 UIA 호출에 COMError 처리
- 실패 시 기본값 반환
- 로깅으로 문제 추적

---

## 버전 정보

- 카카오톡 PC 버전: 3.x.x
- 테스트 일자: 2025-01
- NVDA 참고 버전: 2024.x
