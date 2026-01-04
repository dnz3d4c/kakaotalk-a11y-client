# 릴리즈 가이드

## 사전 조건

1. 버전 업데이트 완료
   - `pyproject.toml`
   - `src/kakaotalk_a11y_client/__about__.py`
2. CHANGELOG.md 업데이트 완료
3. client 저장소에 커밋 완료

## 릴리즈 실행

```bash
python scripts/sync_release.py --release
```

자동으로 수행되는 작업:
1. PyInstaller 빌드 → `dist/KakaotalkA11y-vX.X.X-win64.zip`
2. release 저장소 동기화
3. 커밋/태그/push
4. GitHub Release 생성 (CHANGELOG 내용 자동 추출)

## 스크립트 실패 시

스크립트 실패 시 Claude에게 오류 메시지 전달 → 조치 방법 안내받기.

**흔한 실패 원인:**
- release 저장소 없음 → `git clone` 필요
- gh CLI 미설치/미인증 → 수동 Release 생성
- 태그 충돌 → 기존 태그 삭제 후 재시도

## 주의사항

- client 저장소는 push 금지 (로컬 이력 보존용)
- release 저장소가 없으면: `git clone https://github.com/dnz3d4c/kakaotalk-a11y-client C:/project/kakaotalk-a11y-release`
