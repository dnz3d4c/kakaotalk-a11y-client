# UIA 분석 도구 사용 가이드

개발과 디버깅에 필요한 UIA 분석 도구들을 정리했습니다.

## 목차

1. [UIA 트리 덤프](#1-uia-트리-덤프)
2. [트리 스냅샷 비교](#2-트리-스냅샷-비교)
3. [프로파일러 로그 분석](#3-프로파일러-로그-분석)
4. [성능 비교 리포트](#4-성능-비교-리포트)
5. [UIA 이벤트 테스트](#5-uia-이벤트-테스트)

---

## 1. UIA 트리 덤프

### 기본 사용법

```powershell
# 채팅 목록 덤프
uv run python scripts/dump_uia.py chat_list

# 메뉴 구조 덤프 (4초 대기)
uv run python scripts/dump_uia.py menu

# 현재 포커스 요소 덤프
uv run python scripts/dump_uia.py focus
```

### 코드에서 사용

```python
from kakaotalk_a11y_client.utils.uia_utils import dump_tree, dump_tree_json

# 기본 텍스트 덤프
result = dump_tree(element, max_depth=5)

# 좌표 포함
result = dump_tree(element, include_coords=True)
# 출력: [ListItemControl] Name='홍길동' Class=... (100,200,300,400)

# 빈 Name 강조
result = dump_tree(element, highlight_empty=True)
# 출력: [ListItemControl] Name='<EMPTY>' Class=...

# 필터링 (ListItem만)
result = dump_tree(
    element,
    filter_fn=lambda c: c.ControlTypeName == "ListItemControl"
)

# JSON 형식
tree_dict = dump_tree_json(element, max_depth=5, include_coords=True)
```

### dump_tree 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| element | Control | 필수 | 덤프할 UIA 요소 |
| max_depth | int | 5 | 최대 탐색 깊이 |
| file | file | None | 파일 객체 (동시 저장) |
| print_output | bool | False | 콘솔 출력 여부 |
| include_coords | bool | False | BoundingRectangle 출력 |
| highlight_empty | bool | False | 빈 Name을 `<EMPTY>`로 표시 |
| filter_fn | Callable | None | 필터 함수 (True면 출력) |

---

## 2. 트리 스냅샷 비교

UI 변화를 추적할 때 사용. 두 시점의 트리를 비교하여 추가/삭제/변경된 요소 확인.

### 스냅샷 저장

```powershell
# 첫 번째 스냅샷 (3초 대기 후 저장)
uv run python scripts/dump_uia.py snapshot
# -> uia_snapshot_20251231_143000.json 생성

# UI 조작 (메시지 보내기, 스크롤 등)

# 두 번째 스냅샷
uv run python scripts/dump_uia.py snapshot
# -> uia_snapshot_20251231_143100.json 생성
```

### 스냅샷 비교

```powershell
uv run python scripts/dump_uia.py compare uia_snapshot_20251231_143000.json uia_snapshot_20251231_143100.json
```

### 출력 예시

```markdown
# UIA 트리 비교 결과

## 요약
- 이전 트리: 150개 요소
- 현재 트리: 153개 요소
- 추가: 5개
- 삭제: 2개
- 변경: 1개

## 추가된 요소
+ [ListItemControl] Name='새 메시지입니다'
+ [TextControl] Name='오후 2:31'

## 삭제된 요소
- [ListItemControl] Name='<EMPTY>'
```

### 코드에서 사용

```python
from kakaotalk_a11y_client.utils.uia_utils import (
    dump_tree_json, compare_trees, format_tree_diff
)
import json

# 스냅샷 저장
tree1 = dump_tree_json(element)
with open('snapshot1.json', 'w') as f:
    json.dump(tree1, f)

# (UI 변화 후)
tree2 = dump_tree_json(element)

# 비교
diff = compare_trees(tree1, tree2)
print(format_tree_diff(diff))

# diff 구조:
# {
#     'added': [...],
#     'removed': [...],
#     'changed': [...],
#     'unchanged': 145,
#     'summary': {...}
# }
```

---

## 3. 프로파일러 로그 분석

DEBUG 모드로 실행 시 생성되는 프로파일 로그 분석.

### 로그 생성

```powershell
# DEBUG 모드로 실행
$env:DEBUG=1; uv run kakaotalk-a11y

# 로그 위치: %TEMP%/kakaotalk_a11y_profile_*.log
```

### 분석 실행

```powershell
# 기본 분석
uv run python scripts/analyze_profile.py

# 작업명 필터링
uv run python scripts/analyze_profile.py --filter context_menu

# 시간 범위 필터링
uv run python scripts/analyze_profile.py --time 10:00-10:30

# 조합 사용
uv run python scripts/analyze_profile.py --filter menu --time 09:00-12:00

# 시간대별 분석 버킷 크기 조절 (기본 5분)
uv run python scripts/analyze_profile.py --bucket 10
```

### 출력 파일

- `docs/PROFILER_ANALYSIS.md` - 마크다운 리포트

### 리포트 내용

1. **병목 지점 Top 10** - 평균 시간 기준
2. **SLOW 작업** - 100ms 이상 작업
3. **빈 항목 통계** - 가상 스크롤 영향 확인
4. **재시도 통계** - 메뉴 찾기 안정성
5. **시간대별 성능** - 시간에 따른 성능 변화
6. **개선 제안** - 자동 생성

### 시간대별 분석 예시

```markdown
## 시간대별 성능

| 시간대 | 평균(ms) | SLOW 횟수 | 총 작업수 |
|--------|----------|-----------|----------|
| 10:00-10:05 | 45.2 | 2 | 150 |
| 10:05-10:10 | 120.5 | 15 | 180 |  # 성능 저하 감지
| 10:10-10:15 | 48.1 | 3 | 160 |
```

---

## 4. 성능 비교 리포트

최적화 전/후 성능 비교.

### 리포트 JSON 생성

```python
from kakaotalk_a11y_client.utils.profiler import profiler

# 테스트 실행 후
profiler.save_report()
# -> %TEMP%/report_20251231_143000.txt
# -> %TEMP%/report_20251231_143000.json
```

### 두 리포트 비교

```python
from pathlib import Path
from kakaotalk_a11y_client.utils.profiler import UIAProfiler

baseline = Path("report_before.json")
current = Path("report_after.json")

report = UIAProfiler.generate_comparison_report(baseline, current)
print(report)
```

### 비교 리포트 예시

```markdown
# 성능 비교 리포트

- 기준: report_before.json
- 현재: report_after.json
- 임계값: ±20%

## 개선된 항목

| 작업 | 이전(ms) | 현재(ms) | 변화 |
|------|----------|----------|------|
| find_menu | 150.0 | 80.0 | -46.7% |
| get_children | 45.0 | 30.0 | -33.3% |

## 저하된 항목

| 작업 | 이전(ms) | 현재(ms) | 변화 |
|------|----------|----------|------|
| refresh_messages | 50.0 | 120.0 | +140.0% |

## 요약

- 개선: 5개
- 저하: 1개
- 변화 없음: 12개
```

---

## 5. UIA 이벤트 테스트

카카오톡의 UIA 이벤트 지원 여부 확인 (분석용).

### 실행

```powershell
# 카카오톡 채팅방 열고 실행
uv run python scripts/test_uia_events.py
```

### 테스트 과정

1. 채팅방 창 자동 탐색
2. 메시지 목록 찾기
3. 60초간 300ms 폴링으로 변화 감지
4. 결과 저장

### 출력 파일

- `docs/UIA_EVENT_TEST_RESULT.md`

### 결론

카카오톡은 UIA 이벤트(StructureChanged, PropertyChanged)를 발생시키지 않음.
따라서 메시지 변화 감지는 **폴링 방식** 사용 필수.

- 권장 폴링 간격: 300~500ms
- 현재 구현: `message_monitor.py` (500ms)

---

## 실제 사용 예시

### 시나리오 1: 빈 항목 분포 확인

```powershell
# 트리 덤프 (빈 항목 강조)
uv run python scripts/dump_uia.py chat_list
# 파일에서 <EMPTY> 검색
```

또는 코드에서:

```python
result = dump_tree(chat_list, highlight_empty=True)
empty_count = result.count("<EMPTY>")
print(f"빈 항목: {empty_count}개")
```

### 시나리오 2: 메뉴 항목 구조 파악

```powershell
# 1. 카카오톡에서 우클릭 메뉴 열기
# 2. 4초 안에 실행
uv run python scripts/dump_uia.py menu
# 3. menu_dump_*.txt 파일 확인
```

### 시나리오 3: 최적화 효과 측정

```powershell
# 1. 최적화 전 테스트
$env:DEBUG=1; uv run kakaotalk-a11y
# (테스트 후 종료)
# report_*.json 파일 저장

# 2. 최적화 후 테스트
# (코드 수정)
$env:DEBUG=1; uv run kakaotalk-a11y
# (테스트 후 종료)

# 3. 비교
# Python에서 generate_comparison_report() 사용
```

### 시나리오 4: 동적 UI 변화 추적

```powershell
# 1. 채팅방 열기
uv run python scripts/dump_uia.py snapshot

# 2. 메시지 보내기/받기

# 3. 다시 스냅샷
uv run python scripts/dump_uia.py snapshot

# 4. 비교
uv run python scripts/dump_uia.py compare snapshot1.json snapshot2.json
```

---

## 주의사항

1. **DEBUG 모드**: 프로파일러 로그는 `$env:DEBUG=1` 설정 시에만 생성됨
2. **카카오톡 전용**: 모든 도구는 카카오톡 창만 대상으로 함
3. **분석 용도**: 이벤트 테스트 결과와 관계없이 프로덕션에서는 폴링 방식 유지
4. **파일 위치**:
   - 프로파일 로그: `%TEMP%/kakaotalk_a11y_profile_*.log`
   - 리포트: `%TEMP%/report_*.json`
   - 분석 결과: `docs/PROFILER_ANALYSIS.md`
