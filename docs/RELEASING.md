# 릴리즈 가이드

## 버전 체계

Semantic Versioning (MAJOR.MINOR.PATCH)

## 릴리즈 체크리스트

1. 버전 업데이트: `__about__.py`, `pyproject.toml`
2. CHANGELOG.md 업데이트
3. PyInstaller 빌드: `uv run python scripts/build.py`
4. client 저장소 커밋
5. release 저장소 동기화 및 커밋
6. 태그 생성: `git tag -a vX.X.X -m "vX.X.X"`
7. push: `git push origin main && git push origin vX.X.X`
8. GitHub Releases 생성: `gh release create vX.X.X --generate-notes`

## 배포

- GitHub Releases에 zip 파일 첨부
- 파일명: `KakaotalkA11y-vX.X.X-win64.zip`
