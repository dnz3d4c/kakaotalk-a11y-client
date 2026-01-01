# 프로파일러 분석 결과

> **참고**: 이 문서의 context_menu 관련 데이터는 과거 기록입니다.
> context_menu.py는 2025-12-31에 폐기되었으며, 현재는 NVDA 네이티브 동작에 위임됩니다.

## 측정 환경
- 분석 로그 수: 150개
- 총 작업 유형: 16개

## 병목 지점 Top 10 (평균 시간 기준)

| 순위 | 작업 | 호출수 | 평균(ms) | 최소(ms) | 최대(ms) |
|------|------|--------|----------|----------|----------|
| 1 | find_context_menu | 4 | 16500.9 | 9164.2 | 37735.8 |
| 2 | context_menu.context_menu.find_eva_menu_deep | 58 | 2052.0 | 332.4 | 30713.6 |
| 3 | context_menu.find_menu_from_focus | 367 | 2031.0 | 0.5 | 32409.2 |
| 4 | context_menu.context_menu.find_menu_from_focus | 62 | 1390.7 | 0.6 | 22116.6 |
| 5 | context_menu.find_eva_menu_deep | 236 | 765.7 | 215.8 | 30341.9 |
| 6 | right_click | 210 | 562.0 | 551.7 | 572.8 |
| 7 | context_menu.find_eva_menu_in_windows | 235 | 560.9 | 90.4 | 9206.6 |
| 8 | context_menu.right_click | 5 | 557.6 | 553.2 | 560.5 |
| 9 | context_menu.context_menu.find_generic_menu | 58 | 448.5 | 12.2 | 574.8 |
| 10 | context_menu.find_generic_menu | 232 | 320.5 | 18.4 | 2478.5 |

## SLOW 작업 (100ms 이상)

| 작업 | 발생 횟수 | 평균(ms) | 최대(ms) |
|------|----------|----------|----------|
| find_context_menu | 4 | 16500.9 | 37735.8 |
| context_menu.find_menu_from_focus | 180 | 4135.9 | 32409.2 |
| context_menu.context_menu.find_eva_menu_deep | 58 | 2052.0 | 30713.6 |
| context_menu.find_eva_menu_deep | 236 | 765.7 | 30341.9 |
| context_menu.context_menu.find_menu_from_focus | 24 | 3585.1 | 22116.6 |
| context_menu.find_eva_menu_in_windows | 232 | 566.9 | 9206.6 |
| find_all_descendants | 1 | 2758.1 | 2758.1 |
| context_menu.find_generic_menu | 215 | 343.6 | 2478.5 |
| context_menu.context_menu.find_generic_menu | 56 | 464.0 | 574.8 |
| right_click | 210 | 562.0 | 572.8 |

## 빈 항목(empty) 통계

- 총 ListItems 호출: 4013회
- 80% 이상 빈 항목: 28회 (0.7%)
- 평균 빈 항목 비율: 2.5%

## 메뉴 찾기 재시도 통계

- 총 시도: 145회
- 평균 재시도: 1.2회
- 최대 재시도: 5회

| 시도 횟수 | 발생 빈도 |
|----------|----------|
| 1 | 135 |
| 3 | 3 |
| 4 | 5 |
| 5 | 2 |

## 개선 제안

### 1. find_menu_from_focus 최적화 (최우선)
**문제**: 평균 2초, 최대 32초 소요
**원인 추정**:
- 포커스 부모 탐색 루프에서 무한 루프에 가까운 상황 발생
- UIA 요소 접근 시 블로킹 호출

**개선안**:
- 타임아웃 추가 (최대 500ms)
- 부모 탐색 깊이 제한 (5단계 → 3단계)
- 캐시 적용 (최근 성공한 메뉴 경로 저장)

### 2. EVA_Menu 검색 최적화
**문제**: `find_eva_menu_deep` 평균 765ms, 최대 30초
**원인**: `searchDepth=10`과 `maxSearchSeconds=0.15`가 충돌 (깊이 우선 탐색이 시간 제한을 초과)

**개선안**:
- searchDepth 줄이기 (10 → 5)
- 검색 전에 캐시된 창 핸들로 직접 접근 시도

### 3. 프로파일러 스레드 안전성
**문제**: `context_menu.context_menu.xxx` 형태의 중복 컨텍스트 이름
**원인**: `_context_stack`이 싱글톤에서 전역 공유

**개선안**:
- ThreadLocal 사용하여 스레드별 컨텍스트 스택 분리
- 또는 컨텍스트 사용 중지하고 개별 measure만 사용

### 4. 우클릭 대기 시간 (정상)
- 평균 562ms는 Windows 시스템 응답 시간
- 개선 불가 (정상 동작)

## 우선순위
1. find_menu_from_focus 타임아웃 추가 (가장 효과적)
2. EVA_Menu 검색 searchDepth 줄이기
3. 프로파일러 스레드 안전성 수정

## 참고: 양호한 항목
- ListItems 필터링: 평균 빈 항목 2.5%, 가상 스크롤 영향 미미
- 메뉴 재시도: 93% (135/145)가 1회에 성공
