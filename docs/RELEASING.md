# 릴리즈 가이드

## 버전 관리

### 버전 정의 위치 (동기화 필수)
- `pyproject.toml`: `version = "X.Y.Z"`
- `src/kakaotalk_a11y_client/__about__.py`: `__version__ = "X.Y.Z"`

### 버전 결정 기준

| 버전 | 조건 | 커밋 타입 |
|------|------|----------|
| PATCH (0.0.x) | 기존 기능 유지보수 | fix, improve, refactor, docs, chore |
| MINOR (0.x.0) | 새 기능 추가 | feat 1개 이상 포함 |
| MAJOR (x.0.0) | 호환성 깨짐 | 설정 형식 변경, API 변경 |

### 릴리즈 트리거

**자동 트리거** (하나라도 해당 시 릴리즈 고려):
- feat 3개 이상 축적
- fix 5개 이상 축적
- 보안/안정성 중요 수정

**수동 판단**:
- 사용자에게 빨리 전달 필요
- 중요 버그 수정

### 커밋 후 릴리즈 확인 (Claude 규칙)

feat/fix/improve 커밋 후:
1. 마지막 버전 태그 이후 feat/fix 개수 확인
2. 트리거 충족 시 → "릴리즈할까?" 제안
3. 버전 자동 결정: feat 있으면 Minor, 없으면 Patch

## CHANGELOG 작성 규칙

### 버전 요약
버전 제목 바로 아래에 한 줄 요약 작성. 사용자 관점에서 핵심 개선사항 전달.

**작성 규칙:**
- 기술 용어 금지: 리팩토링, 최적화, 모듈화 → 사용자가 느끼는 변화로
- 형식: "[무엇이] [어떻게 됐다]"
- 예시:
  - Bad: "FocusChanged 핸들러 최적화"
  - Good: "방향키 탐색 반응 속도 향상"

```markdown
## [0.3.2] - 2026-01-04

메시지 읽기 안정성 개선.

### Changed
...
```

### 포함 대상
- feat: 새 기능 (Added)
- fix: 사용자 영향 버그 수정 (Fixed)
- improve: 기능 개선 (Changed)
- docs (사용자 대상): USER_GUIDE.md, UPDATER.md, ARCHITECTURE.md, UIA_GUIDE.md, KAKAO_UIA_QUIRKS.md, nvda_uia_patterns.md

### 제외 대상
- docs (개발자 대상): BUILD.md, RELEASING.md, TOOLS_GUIDE.md, *_ANALYSIS.md, AI_*.md, 카카오톡_*프롬프트.md, DOCUMENT_STYLE_GUIDE.md, CLAUDE.md, CONTRIBUTING.md
- chore, refactor: 사용자 영향 없음
- 빌드/릴리즈 스크립트 수정

### 릴리즈 전 필수 확인
- 테스트 환경 확인 및 문서 업데이트 (README.md, USER_GUIDE.md)
- [Unreleased]에 내용 남아있으면 릴리즈 스크립트가 중단됨

### 테스트 환경 확인
릴리즈 전 현재 테스트 환경을 확인하고 문서 업데이트:

1. **확인 대상**: Windows 버전, NVDA 버전
2. **업데이트 파일**:
   - `README.md`: 테스트 환경 섹션
   - `docs/USER_GUIDE.md`: 테스트 환경 섹션
3. **변경 시**: 새 환경 정보로 두 파일 동시 업데이트

## 릴리즈 스킬

### `/ship [버전]`
전체 릴리즈 플로우 실행 (예: `/ship 0.3.3`)

**버전 인자 있음:**
1. 버전 업데이트 (`pyproject.toml`, `__about__.py`)
2. CHANGELOG `[Unreleased]` → `[X.Y.Z] - 날짜` 변환
3. 빌드 + GitHub Release

**버전 인자 없음:**
- 빌드 + GitHub Release만 (이미 버전 업데이트된 경우)

## 릴리즈 실행

### 사전 조건
1. CHANGELOG.md [Unreleased]에 변경사항 작성
2. 미커밋 변경사항 없음

### 실행

```bash
# 전체 릴리즈 (빌드 + 동기화 + push + GitHub Release)
python scripts/sync_release.py --release

# 동기화만 (테스트용)
python scripts/sync_release.py
```

자동으로 수행되는 작업:
1. PyInstaller 빌드 → `dist/KakaotalkA11y-vX.X.X-win64.zip`
2. release 저장소 동기화
3. client + release 양쪽에 태그 생성
4. release 저장소 push
5. GitHub Release 생성 (CHANGELOG 내용 자동 추출)

## 스크립트 실패 시

스크립트 실패 시 Claude에게 오류 메시지 전달 → 조치 방법 안내받기.

**흔한 실패 원인:**
- release 저장소 없음 → `git clone` 필요
- gh CLI 미설치/미인증 → 수동 Release 생성
- 태그 충돌 → 기존 태그 삭제 후 재시도

## 저장소 구조

| 경로 | 용도 | Git 상태 |
|------|------|----------|
| `C:\project\kakaotalk-a11y-client` | 로컬 개발 (이력 보존) | push 금지 |
| `C:\project\kakaotalk-a11y-release` | GitHub 배포용 | push 허용 |

### release 저장소 없으면

```bash
git clone https://github.com/dnz3d4c/kakaotalk-a11y-client C:/project/kakaotalk-a11y-release
```

### release 제외 파일
- `samples/` - 민감정보 포함 개발용 샘플
- `docs/PROJECT_ANALYSIS.md` - 로컬 개발 전용 분석 문서
- `docs/DOCUMENT_STYLE_GUIDE.md` - 문체 가이드 (main에서만 관리)
- `.claude/skills/` - 로컬 스킬 (배포 불필요)
