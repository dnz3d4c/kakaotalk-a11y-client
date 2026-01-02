# 자동 업데이터

GitHub 릴리스 기반 자동 업데이트 시스템.

## 동작 방식

### 업데이트 확인 시점
1. **자동**: 앱 시작 5초 후 백그라운드에서 확인
2. **수동**: 트레이 메뉴 → "업데이트 확인"

### 업데이트 흐름

```
[앱 시작] ──5초──> [GitHub API 호출]
                        │
                  (새 버전 발견)
                        ▼
              [업데이트 알림 대화상자]
                    Yes │ No
                        ▼
              [릴리스 노트 대화상자]
                   확인 │ 취소
                        ▼
              [다운로드 진행률 대화상자]
                   완료 │ 취소 → [임시파일 정리]
                        ▼
              [재시작 확인 대화상자]
                        ▼
              [batch 스크립트 실행]
                   - 기존 프로세스 종료 대기
                   - 파일 복사
                   - 임시파일 정리
                   - 새 버전 실행
```

## 모듈 구조

```
src/kakaotalk_a11y_client/
  updater/
    __init__.py         # 공개 API (check_for_update, start_download, apply_and_restart)
    github_client.py    # GitHub API 호출, 다운로드
    version.py          # 버전 비교 (semver)
    installer.py        # 압축 해제, batch 스크립트 생성/실행
  gui/
    update_dialogs.py   # wxPython 대화상자 3종
```

## 핵심 함수

### `updater.check_for_update() -> UpdateInfo | None`
GitHub API로 최신 릴리스 확인. 새 버전이 있으면 `UpdateInfo` 반환.

### `updater.start_download(info, progress_cb) -> Path | None`
에셋 다운로드. `progress_cb(downloaded, total) -> bool`로 진행률 전달, False 반환 시 취소.

### `updater.apply_and_restart(zip_path) -> bool`
압축 해제 후 batch 스크립트로 업데이트 적용. 성공 시 앱 종료.

## 기술 결정

| 항목 | 결정 | 이유 |
|------|------|------|
| HTTP | urllib (표준) | 의존성 추가 없음 |
| exe 교체 | batch 스크립트 | 별도 updater.exe 불필요 |
| 에셋 형식 | zip | Python zipfile로 해제 |

## 파일 경로

| 용도 | 경로 |
|------|------|
| 다운로드 | `%TEMP%\kakaotalk_a11y_update\update.zip` |
| 압축 해제 | `%TEMP%\kakaotalk_a11y_extract\` |
| batch 스크립트 | `%TEMP%\kakaotalk_a11y_update\update.bat` |

## 에러 처리

| 상황 | 처리 |
|------|------|
| 네트워크 오류 | 로그 warning, 무시 |
| API rate limit | 로그, 다음 실행 시 재시도 |
| 다운로드 취소 | 임시파일 정리 |
| 압축 해제 실패 | 에러 대화상자 |
| batch 실행 실패 | 수동 설치 안내 |

## 릴리스 에셋 규칙

파일명 패턴: `KakaotalkA11y-vX.X.X-win64.zip`

zip 내부 구조:
```
KakaotalkA11y.exe
_internal/
  (의존성 파일들)
```

## 개발 환경

개발 환경(PyInstaller 빌드 아님)에서는 업데이터가 비활성화된다.
`is_frozen()` 함수로 빌드 환경 여부 확인.
