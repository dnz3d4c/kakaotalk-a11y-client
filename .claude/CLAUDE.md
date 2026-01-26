# 프로젝트 지침

> **글로벌 지침(`~/.claude/CLAUDE.md`) 우선**. 이 문서는 프로젝트 특화 내용만 보충.

## 코드 수정 전 체크리스트

### 필수 확인 사항
1. **관련 함수 전체 읽기** - 호출하는 쪽, 호출되는 쪽 모두
2. **비활성화된 코드 확인** - `pass`, 빈 `return`, 주석 처리된 코드
3. **조건문 분기 확인** - 어떤 조건에서 실행되는지

### 특히 주의
- `pass`로 비어있는 함수 확인 (주석에 "비활성화됨" 등 표시 있을 수 있음)
- `enable()` 같은 활성화 함수가 실제로 뭔가를 하는지 확인

## Docstring 스타일

### 원칙
- 함수명/타입힌트로 알 수 있는 건 생략
- 한 줄로 충분하면 한 줄로
- Args/Returns 섹션은 복잡한 경우만
- "왜(why)" 설명, "무엇(what)"은 코드가 설명

### 작성 기준
| 상황 | docstring |
|------|-----------|
| 함수명이 명확 | 생략 또는 한 줄 |
| 비직관적 동작/부작용 | 반드시 명시 |
| 복잡한 파라미터 | Args 섹션 |
| 외부 API | 상세 설명 |

### 예시
```python
# Bad - 뻔한 내용 반복
def speak(text: str) -> bool:
    """텍스트를 음성으로 출력합니다.

    Args:
        text: 출력할 텍스트
    Returns:
        성공 여부
    """

# Good - 핵심만
def speak(text: str) -> bool:
    """음성 + 점자 출력. interrupt=True면 음성만."""

# Good - 비직관적 동작 설명
def cleanup():
    """리소스 정리. 반드시 finally에서 호출할 것."""
```

## 코드 추가 전 아키텍처 체크리스트

상세 규칙: [ARCHITECTURE_RULES.md](.claude/guides/ARCHITECTURE_RULES.md)

### 새 파일 추가 시
- [ ] 계층 확인 (GUI/Application/Domain/Infrastructure)
- [ ] 의존 방향 확인 (상위 → 하위만)
- [ ] TYPE_CHECKING 가드로 순환 import 방지

### 새 스레드 추가 시
- [ ] `pythoncom.CoInitialize()` 호출 (UIA 사용 시)
- [ ] `finally`에서 `pythoncom.CoUninitialize()`
- [ ] `daemon=True` 설정

### UIA 코드 추가 시
- [ ] `safe_uia_call()` 래핑
- [ ] `searchDepth` 명시 (최대 6)
- [ ] 반복 접근 시 캐시 사용
- [ ] 처음 작업 시 [UIA_GUIDE.md](docs/UIA_GUIDE.md), [KAKAO_UIA_QUIRKS.md](docs/KAKAO_UIA_QUIRKS.md) 읽기
- [ ] NVDA 패턴 적용 시 [nvda_uia_patterns.md](docs/nvda_uia_patterns.md) 참고

### 이벤트/콜백 추가 시
- [ ] GUI 업데이트는 `wx.CallAfter()` 사용
- [ ] 에러 핸들링 포함
- [ ] 폴백 전략 고려

## 디버깅 원칙

### 로그 먼저 확인
```
문제 발생 시:
1. 로그에서 마지막으로 실행된 코드 확인
2. 예상 로그 vs 실제 로그 비교
3. 로그가 안 찍히면 → 해당 코드가 실행 안 된 것
```

### 작은 단위 수정
- 한 번에 하나만 수정
- 수정 → 테스트 → 로그 확인 → 다음 수정
- 여러 개 동시 수정 금지

## Edit 도구 오류 대응

> 기본 규칙은 글로벌 지침 참조. 아래는 프로젝트 특화 우회 방법.

```python
# 우회 스크립트 예시
target = 'path/to/file.py'
with open(target, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace(old_code, new_code)
with open(target, 'w', encoding='utf-8') as f:
    f.write(content)
```

## 프로젝트 구조

- `src/kakaotalk_a11y_client/` - 메인 소스
  - `main.py` - 진입점, 전체 조율
  - `navigation/` - 탐색 모듈
    - `chat_room.py` - 채팅방 메시지 탐색
    - `message_monitor.py` - 새 메시지 자동 읽기
- `scripts/` - 유틸리티 스크립트

## 버전 관리

버전 정의 위치:
- `pyproject.toml`: `version = "X.Y.Z"`
- `src/kakaotalk_a11y_client/__about__.py`: `__version__ = "X.Y.Z"`

릴리즈: `/ship X.Y.Z` 스킬 사용 (버전 업데이트 + 빌드 + GitHub Release)

### 중요 규칙
- **버전 커밋은 `/ship`만 생성** - 수동으로 `chore(version)` 커밋 금지
- **feat/fix 커밋 후 CHANGELOG 업데이트** - `[Unreleased]` 섹션에 추가
- 개발 중에는 버전 유지, 릴리즈 시점에 `/ship`이 버전 + CHANGELOG 동시 처리

상세 릴리즈 가이드: [RELEASING.md](docs/RELEASING.md)

## 캐시 삭제 (기능 변경/추가 후 필수)

코드 수정 후 테스트 전 **반드시** 파이썬 캐시 삭제.

**정책:**
- 프로젝트 폴더(`C:\project\kakaotalk-a11y\client`) 한정 → 권한 문제 없음
- 프로그램 실행 중이면 자동 종료 후 삭제

```powershell
# PowerShell - Python 종료 + 캐시 삭제 (권장)
powershell.exe -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; Get-ChildItem -Path 'C:\project\kakaotalk-a11y\client' -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
```

```bash
# Bash/Git Bash
find /c/project/kakaotalk-a11y/client -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find /c/project/kakaotalk-a11y/client -type f -name "*.pyc" -delete 2>/dev/null
```

**캐시 문제 증상:**
- 코드 수정했는데 이전 동작 유지
- import 오류 (삭제한 모듈 참조)
- 예상과 다른 함수 실행

## 실행 방법 (Windows PowerShell)

```powershell
# 일반 실행
uv run kakaotalk-a11y

# 디버그 모드 (CLI 옵션)
uv run kakaotalk-a11y --debug              # DEBUG 레벨 (상태 변경 로그)
uv run kakaotalk-a11y --debug --trace      # TRACE 레벨 (고빈도 루프 로그 포함)
uv run kakaotalk-a11y --debug-profile      # 프로파일러만
uv run kakaotalk-a11y --debug --debug-dump-on-start # 시작 시 트리 덤프

# 이벤트 모니터 (확장)
uv run kakaotalk-a11y --debug --debug-events                    # 기본 (Focus+Structure)
uv run kakaotalk-a11y --debug --debug-events=all                # 모든 이벤트
uv run kakaotalk-a11y --debug --debug-events=focus,property     # 선택적 이벤트
uv run kakaotalk-a11y --debug --debug-events --debug-events-filter=ListItemControl  # 필터링
uv run kakaotalk-a11y --debug --debug-events --debug-events-format=json  # JSON 출력
uv run kakaotalk-a11y --debug --debug-events-suggest            # 권장 이벤트 모드

# 디버그 모드 (환경변수 - 레거시)
$env:DEBUG=1; uv run kakaotalk-a11y  # DEBUG 레벨
$env:DEBUG=2; uv run kakaotalk-a11y  # TRACE 레벨

# 디버그 로그 확인
Get-Content C:\project\kakaotalk-a11y\client\logs\debug.log -Tail 50

# UTF-8 로그 확인 (한글 깨짐 방지)
powershell.exe -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Content 'C:\project\kakaotalk-a11y\client\logs\debug.log' -Encoding UTF8 -Tail 50"

# 프로파일 로그 확인
Get-Content C:\project\kakaotalk-a11y\client\logs\profile_*.log -Tail 50
```

### 로그 레벨

| 레벨 | 용도 |
|------|------|
| TRACE | 고빈도 루프 로그 (포커스 모니터 상태, 메뉴 모드 진입/종료) |
| DEBUG | 상태 변경, 주요 이벤트 (채팅방 진입, 정리 시작/완료) |
| INFO | 모드 전환, 로그 파일 경로 |
| WARNING | 복구 가능한 문제 |
| ERROR | 치명적 오류 |

### 디버깅 상황별 권장 옵션

- **일반 문제**: `--debug` (DEBUG 이상)
- **포커스 추적 문제**: `--debug --trace` (TRACE 포함)
- **성능 분석**: `--debug-profile`

### 디버그 단축키 (--debug 모드에서만)
- `Ctrl+Shift+D`: UIA 트리 덤프
- `Ctrl+Shift+P`: 프로파일 요약
- `Ctrl+Shift+R`: 이벤트 모니터 토글
- `Ctrl+Shift+S`: 디버그 상태 확인
- `Ctrl+Shift+1`: 탐색 테스트
- `Ctrl+Shift+2`: 메시지 테스트

### 디버그 출력 위치
- 덤프/리포트/프로파일: `logs/` (프로젝트 폴더 내)

**주의**: `DEBUG=1 uv run ...` 형식은 Linux/bash 전용. Windows에서는 `$env:DEBUG=1;` 사용.

## 저장소 분리 전략

- `kakaotalk-a11y/client`: 로컬 개발용 (push 금지)
- `kakaotalk-a11y/release`: GitHub 배포용

상세: [RELEASING.md](docs/RELEASING.md)

---

## 새 UI 기능 분석 자동 제안

상세 절차: [EVENT_ANALYSIS_WORKFLOW.md](.claude/guides/EVENT_ANALYSIS_WORKFLOW.md)

### 트리거 조건
다음 상황에서 표준 분석 절차 자동 제안:
- "기능 구현", "기능 추가" 언급
- "UI 분석", "이벤트 추적" 언급
- 구체적 UI 동작 설명 (예: "@ 입력하면 목록이 나옴")
- 새 UI 요소 접근성 지원 요청

### 자동 제안 워크플로우

**Step 1**: 기능 유형 파악 → 권장 이벤트 조합 안내
```
이 기능은 [팝업/목록/입력] 유형으로 보임.
권장 분석:
1. 트리 덤프: Ctrl+Shift+D (해당 UI 상태에서)
2. 이벤트: --debug-events=[권장조합]
```

**Step 2**: 분석 결과 요청
```
다음 정보 공유해줘:
- 트리 덤프에서 [대상] 부분
- 이벤트 로그 (핵심 동작 재현 시)
```

**Step 3**: 결과 해석 + 구현 전략 제안
- 덤프/로그 분석
- 기존 패턴과 비교
- 구현 방향 제안

### 기능 유형별 권장 이벤트

| 유형 | 권장 이벤트 | 명령어 |
|------|------------|--------|
| 팝업/드롭다운 | structure, focus | `--debug-events=structure,focus` |
| 목록 항목 추가/제거 | structure | `--debug-events=structure` |
| 입력/편집 | property, focus | `--debug-events=property,focus` |
| 체크박스/토글 | property | `--debug-events=property` |
| 포커스 이동만 | focus | `--debug-events=focus` |
| **미지의 케이스** | all | `--debug-events=all` |

### 미지의 케이스 대응

기존 패턴과 매칭 안 되면 Phase 0 (탐색적 분석) 먼저:
1. `--debug-events=all`로 전체 이벤트 수집
2. 트리 덤프로 구조 파악
3. 새 패턴 발견 시 `KAKAO_UIA_QUIRKS.md`에 문서화
4. 필요시 SmartListFilter/핸들러 확장

### 예시: 멘션 기능

**사용자**: "멘션 기능 구현하려고 함. @ 입력하면 멘션 목록 나옴"

**Claude 응답**:
```
팝업/드롭다운 유형. 다음 분석 진행해:

1. 트리 덤프:
   - 채팅방에서 @ 입력
   - Ctrl+Shift+D
   - 멘션 목록 관련 요소 공유

2. 이벤트 추적:
   uv run kakaotalk-a11y --debug --debug-events=structure,focus

   재현:
   - @ 입력 (목록 출현)
   - 방향키로 항목 이동
   - Enter로 선택

결과 공유하면 해석 + 구현 방향 제안할게.
```

---

## 문서 업데이트 자동화

작업 완료 후 해당 트리거에 맞는 문서를 자동으로 업데이트.

### 트리거별 필수 업데이트

| 트리거 | 문서 | 체크 |
|--------|------|------|
| **릴리즈 준비** | CHANGELOG.md | 변경사항 추가 |
| | README.md | 버전 번호 (있으면) |
| | USER_GUIDE.md | 기능 변경 반영 |
| **아키텍처 변경** | ARCHITECTURE.md | 모듈 구조, 계층도 |
| | BUILD.md | 빌드 방식 변경 |
| **지침 변경** | CLAUDE.md | 새 규칙 추가 |
| | CONTRIBUTING.md | 기여 규칙 |

### 수동 관리 문서 (거의 안 바뀜)
- `UIA_*.md`, `NVDA_*.md` - 참고 문서
- `AI_*.md` - 프롬프트 예시
- `DOCUMENT_STYLE_GUIDE.md` - 문체 수정 이력

---

## AI 문체 다듬기 이력 관리

사용자가 문서의 AI 말투를 다듬는 작업 시 자동으로 이력 기록.

### 트리거 조건
- "AI 말투", "문체 수정", "자연스럽게 다듬어" 등 키워드 포함
- 교과서식 표현(`**역할**:`, `**결론**:` 등) → 자연스러운 문장 변환
- 명사형(~함, ~됨) → 경어체(~합니다) 변환

### 수행 절차
1. 문서 수정 완료
2. `docs/DOCUMENT_STYLE_GUIDE.md`에 수정 이력 추가
3. 형식: 기존 패턴 따름 (날짜-문서명 섹션 + 수정 전/후 표)

### 이력 기록 형식
```markdown
## YYYY-MM 문서명 문체 개선

| 위치 | 수정 전 | 수정 후 |
|------|---------|---------|
| N행 | `원본 텍스트` | `수정된 텍스트` |
```

---

## 플랜 작성 규칙

> 상세 템플릿: `~/.claude/templates/plan_template.md`

### 필수 포함 항목
- **사용자 효과**: Before/After 형식 (커밋 메시지 사전 정의)
- **수정 파일 목록**: 경로 + 변경 범위
- **검증 방법**: 테스트 시나리오

### 복잡한 작업 시 추가
- 의존성 분석 (병렬 그룹)
- 실행 계획 (에이전트 개수, 스킬)

---

## Git 규칙

상세 지침: [CONTRIBUTING.md](.claude/guides/CONTRIBUTING.md)

### 요약
- 커밋 형식: `<타입>: <설명>`
- 타입: feat, fix, improve, refactor, docs, chore
- improve: 근본 원인 분석 후 최선책 적용 (fix와 구분)
- 하나의 논리적 변경 = 하나의 커밋
- 코드 변경 시 관련 문서도 업데이트

### 브랜치
- 현재: main 직접 커밋
- 필요시: feat/, fix/, refactor/ 브랜치 사용

### 커밋 후 릴리즈 확인 (필수)
feat/fix/improve/docs 커밋 후:
1. 마지막 버전 태그 이후 feat/fix/docs 개수 확인
2. 트리거 충족 시 → 사용자에게 "릴리즈할까?" 제안
   - feat 3개 이상 또는 fix 5개 이상 또는 docs 5개 이상
3. 미충족 시 → 현재 수치 간단 보고 (예: "feat 1/3, fix 2/5, docs 1/5")

### 변경 이력 작성

**요약 (사용자용)**: 결과 중심, 한 줄
- "이모지 감지 속도 개선"
- "채팅방 진입 시 오류 수정"

**상세 (개발자용)**: 기술적 내용 OK
- "find_all_descendants 조기종료, searchDepth 15→10"

```markdown
## v0.2.3

### 개선
- 이모지 감지 속도 향상

### 수정
- 특정 상황에서 채팅방 진입 실패하던 문제

### 기타
- opencv-python → headless로 교체
- 구버전 문서 정리

<details>
<summary>상세 변경 로그</summary>

- find_all_descendants 조기종료, searchDepth 15→10
- 포커스 부모 탐색 깊이 제한 20→12
- PACKAGES.md 삭제 (초기 기획 문서)
</details>
```

---

## 로그 분석 가이드

상세 절차: [LOG_ANALYSIS_GUIDE.md](.claude/guides/LOG_ANALYSIS_GUIDE.md)

**핵심**: debug.log만 보지 말고 전체 로그 유형 분석

| 로그 유형 | 용도 | 우선순위 |
|----------|------|---------|
| debug.log | 실행 흐름, 에러 시점 | 1 (항상 먼저) |
| auto_slow_*.json | 느린 작업 시 UIA 상태 | 2 (성능 문제) |
| auto_empty_*.json | 빈 리스트 시 UIA 상태 | 3 (기능 오작동) |
| profile_*.log | 성능 측정 상세 | 4 (최적화 시) |

**필수 분석 항목**:
- 시간대 상관관계 (debug.log 시간 ↔ auto_* 파일명)
- 반복 패턴 (특정 시간대 집중 발생 여부)
- context.json의 operation과 elapsed_ms

---

## 필터링 금지 항목

다음 항목은 사용자가 명시적으로 요청하지 않는 한 **절대 필터링하지 말 것**:
- 카카오톡 상태 메시지 (Connection lost, 연결됨 등)
- 시스템 메시지 (여기까지 읽으셨습니다 등)
- 날짜 구분선 (2026년 1월 22일 수요일 등)

이유: 사용자에게 유용한 정보일 수 있음.

---

## 광고 필터링 규칙

### 필터링 대상
- **Chrome_* 클래스 요소**: `Chrome_WidgetWin_0/1`, `Chrome_RenderWidgetHostHWND` 등
- 광고 웹뷰(AdFit 등)가 이 클래스 사용
- 카카오톡에서 Chrome_* 요소는 사용자에게 유용한 기능 없음 → 완전 무시

### 필터링 대상 아님 (제안 금지)
- **ListItem 광고** (컬리, 카카오톡 선물하기 등)
  - Name에 "(광고)" 포함되어 있어도 필터링 대상 아님
  - 일반 친구/채팅방 목록과 동일한 ListItemControl
  - 사용자가 직접 탐색 중 만나는 항목 → 읽어줘야 함

### 구현 위치
- `uia_workarounds.py`: `should_skip_element()` - 탐색 시 Chrome_* 스킵
- `uia_reliability.py`: `KAKAO_BAD_UIA_CLASSES` - Chrome_* 클래스 목록
- `uia_focus_handler.py`: `_on_focus_event()` - 포커스 이벤트 시 Chrome_* 스킵

---

## 이벤트 핸들러 디버깅 필수 절차

1. **진입 로그 먼저**: 함수 호출 여부 확인
   - 로그가 안 찍히면 함수가 호출 안 되는 것
   - 상위 코드에서 return되고 있음

2. **각 return 지점 로그**: 어디서 빠지는지 추적
   - 디바운싱, 필터링, 창 체크 등 각 단계별 로그

3. **속성 로깅**: 필터링 전에 모든 속성 출력
   - hwnd, 창 클래스, 요소 클래스, 이름



<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

*No recent activity*
</claude-mem-context>