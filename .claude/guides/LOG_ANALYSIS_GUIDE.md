# 로그 분석 가이드

"로그 분석해줘" 요청 시 이 가이드를 따른다.

**핵심 원칙**: debug.log만 보지 말고 전체 로그 유형 분석

---

## 1. 로그 유형별 역할

| 유형 | 파일 패턴 | 내용 | 우선순위 |
|------|----------|------|---------|
| debug.log | `debug.log`, `.1`, `.2`, `.3` | 실행 흐름, 상태 변경, 에러 | 1 (항상 먼저) |
| auto_slow_* | `auto_slow_*.json` + `.context.json` | 느린 작업 시 UIA 트리 | 2 (성능 문제) |
| auto_empty_* | `auto_empty_*.json` + `.context.json` | 빈 리스트 시 UIA 트리 | 3 (기능 오작동) |
| profile_* | `profile_*.log` | 성능 측정 상세 | 4 (최적화 시) |

---

## 2. 분석 플로우

### Phase 1: 로그 현황 파악

```powershell
# 로그 폴더 통계
ls logs/*.json | Measure-Object
ls logs/*.log | Measure-Object

# auto_slow 개수
ls logs/auto_slow*.json | Measure-Object

# auto_empty 개수
ls logs/auto_empty*.json | Measure-Object
```

### Phase 2: debug.log 분석

**목적**: 전체 실행 흐름 파악, 에러 시점 특정

**핵심 패턴**:
| 패턴 | 의미 | 조치 |
|------|------|------|
| `[ERROR:*]` | 치명적 오류 | 스택트레이스 확인 |
| `[WARNING:*]` | 복구된 문제 | 빈도 확인 |
| `SLOW:` | 500ms 초과 | auto_slow 덤프 확인 |
| `nav_mode=False` | 채팅방 진입 실패 | 포커스 상태 확인 |
| `Connection lost` | 카톡 연결 끊김 | 재연결 로직 확인 |

**명령어**:
```powershell
# 에러/경고만
Select-String -Path logs/debug.log -Pattern "\[ERROR\]|\[WARNING\]"

# 특정 시간대
Select-String -Path logs/debug.log -Pattern "^08:47:"

# 최근 100줄
Get-Content logs/debug.log -Tail 100 -Encoding UTF8
```

### Phase 3: 시간대 상관관계 분석

**목적**: debug.log 문제 시점과 auto_* 파일 매칭

**파일명 규칙**:
- `auto_slow_[작업명]_HHMMSS_HHMMSS.json`
- 첫 번째 HHMMSS = 작업 시작
- 두 번째 HHMMSS = 덤프 생성
- debug.log 타임스탬프와 1-2초 내 매칭

**예시**:
```
debug.log: 08:47:30 [DEBUG:Profiler] SLOW: chat_room.refresh_messages took 1013ms
→ 찾을 파일: auto_slow_chat_room.refresh_messages_084730_*.json
```

### Phase 4: 패턴 분석

**목적**: 반복 발생 문제 식별

```powershell
# 시간대별 auto_slow 분포 (앞 4자리 = HHMM)
ls logs/auto_slow*.json | ForEach-Object {
    if ($_.Name -match '_(\d{6})_') { $matches[1].Substring(0,4) }
} | Group-Object | Sort-Object Name
```

특정 시간대에 집중 발생 → 해당 시간대 debug.log 집중 분석

---

## 3. 로그 유형별 상세 분석

### context.json 분석

```json
{
  "operation": "chat_room.refresh_messages",
  "elapsed_ms": 1013.309,
  "threshold_ms": 500
}
```

**분석 포인트**:
- `elapsed_ms / threshold_ms` → 초과 정도
- `operation` → 어떤 작업이 느린지
- 같은 operation 반복 → 근본 원인

### auto_*.json (UIA 트리) 분석

**확인 항목**:
1. 최상위 윈도우 상태 (팝업, 로그인 다이얼로그 등)
2. Children 깊이와 개수 → 트리 복잡도
3. 특이 요소 (에러 다이얼로그, 빈 목록)

### profile_*.log 분석

```
2026-01-16 08:47:30,941 | SLOW: chat_room.refresh_messages took 1001.9ms
2026-01-16 08:47:31,234 | ListItems: total=100, empty=85 (85%), valid=15
```

**분석 포인트**:
- SLOW 경고 빈도
- 작업별 평균 시간
- ListItems empty 비율 → 빈 항목 많으면 UIA 문제

---

## 4. 문제 유형별 분석 전략

### 성능 문제 ("느려요")

1. debug.log에서 SLOW 경고 시간 확인
2. profile_*.log에서 작업별 시간 확인
3. 같은 시간대 auto_slow_* 파일 매칭
4. UIA 트리 복잡도 분석
5. 반복 패턴 확인 (시간대 클러스터링)

### 기능 오작동 ("동작 안 해요")

1. debug.log에서 ERROR/WARNING 확인
2. 해당 시간대 auto_empty_* 확인
3. UIA 트리에서 예상 요소 존재 여부
4. 카톡 상태 확인 (팝업, 로그아웃 등)

### 프리징/멈춤 ("멈춰요")

1. debug.log 마지막 기록 시간
2. 해당 시간 직전 작업 확인
3. auto_slow 덤프에서 당시 상태
4. COM 에러, 무한 루프 가능성

---

## 5. 분석 체크리스트

### 필수 확인 (모든 분석)
- [ ] logs/ 폴더 파일 개수 및 최신 수정 시간
- [ ] debug.log 최근 세션 시작 시간
- [ ] ERROR/WARNING 레벨 로그 존재 여부
- [ ] SLOW 경고 개수

### 성능 문제 시 추가
- [ ] auto_slow_* 파일 개수
- [ ] 시간대 클러스터링 (특정 시간에 집중?)
- [ ] profile_*.log 작업별 통계
- [ ] 가장 느린 작업 Top 5

### 기능 문제 시 추가
- [ ] auto_empty_* 파일 확인
- [ ] 해당 시간대 debug.log 상태
- [ ] UIA 트리에서 예상 요소 존재 여부

---

## 6. 분석 보고 형식

```markdown
## 로그 분석 결과

### 현황
- 분석 기간: YYYY-MM-DD HH:MM ~ HH:MM
- debug.log 크기: X.X MB
- auto_slow 덤프: N개
- auto_empty 덤프: N개

### 발견된 문제
1. [심각도] 문제 요약
   - 발생 시간: HH:MM:SS
   - 관련 로그: [파일명]
   - 원인 추정: ...

### 권장 조치
1. ...
```
