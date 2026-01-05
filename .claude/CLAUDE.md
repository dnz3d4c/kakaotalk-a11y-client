# 프로젝트 지침

## 코드 수정 전 체크리스트

### 필수 확인 사항
1. **관련 함수 전체 읽기** - 호출하는 쪽, 호출되는 쪽 모두
2. **비활성화된 코드 확인** - `pass`, 빈 `return`, 주석 처리된 코드
3. **조건문 분기 확인** - 어떤 조건에서 실행되는지

### 특히 주의
- `pass`로 비어있는 함수 확인 (주석에 "비활성화됨" 등 표시 있을 수 있음)
- `enable()` 같은 활성화 함수가 실제로 뭔가를 하는지 확인

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

"File has been unexpectedly modified" 발생 시:
1. Python 프로세스 종료 시도 (효과 없을 수 있음)
2. **즉시 fix_*.py 스크립트 방식으로 전환**

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
  - `main.py` - 진입점, 핫키/네비게이션 조율
  - `navigation/` - 탐색 모듈
    - `context_menu.py` - 컨텍스트 메뉴 처리
    - `chat_room.py` - 채팅방 메시지 탐색
  - `keyboard_nav.py` - 키보드 후킹
- `scripts/` - 유틸리티 스크립트

## 버전 관리

버전 정의 위치:
- `pyproject.toml`: `version = "X.Y.Z"`
- `src/kakaotalk_a11y_client/__about__.py`: `__version__ = "X.Y.Z"`

릴리즈: `/ship X.Y.Z` 스킬 사용 (버전 업데이트 + 빌드 + GitHub Release)

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
uv run kakaotalk-a11y --debug --debug-events        # 이벤트 모니터 포함
uv run kakaotalk-a11y --debug --debug-dump-on-start # 시작 시 트리 덤프

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
- `Ctrl+Shift+D`: 즉시 UIA 트리 덤프
- `Ctrl+Shift+P`: 프로파일 요약 출력
- `Ctrl+Shift+R`: 이벤트 모니터 토글

### 디버그 출력 위치
- 덤프/리포트: `~/.kakaotalk_a11y/debug/`
- 프로파일 로그: `%TEMP%/kakaotalk_a11y_profile_*.log`

**주의**: `DEBUG=1 uv run ...` 형식은 Linux/bash 전용. Windows에서는 `$env:DEBUG=1;` 사용.

## 저장소 분리 전략

- `kakaotalk-a11y/client`: 로컬 개발용 (push 금지)
- `kakaotalk-a11y/release`: GitHub 배포용

상세: [RELEASING.md](docs/RELEASING.md)

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
feat/fix/improve 커밋 후:
1. 마지막 버전 태그 이후 feat/fix 개수 확인
2. 트리거 충족 시 → 사용자에게 "릴리즈할까?" 제안
   - feat 3개 이상 또는 fix 5개 이상
3. 미충족 시 → 현재 수치 간단 보고 (예: "feat 1/3, fix 2/5")

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
