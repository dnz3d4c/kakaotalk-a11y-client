# 릴리즈 가이드

## 버전 체계

Semantic Versioning (MAJOR.MINOR.PATCH)

## 릴리즈 체크리스트

### 1. 버전 업데이트

- `src/kakaotalk_a11y_client/__about__.py`
- `pyproject.toml`

### 2. CHANGELOG.md 업데이트

간결하게 작성 (CONTRIBUTING.md 참조)

### 3. PyInstaller 빌드

```
uv run python scripts/build.py
```

결과물: `KakaotalkA11y-vX.X.X-win64.zip`

### 4. client 저장소 커밋

```
git add -A
git commit -m "release: vX.X.X"
```

### 5. release 저장소 동기화

```
uv run python scripts/sync_release.py
```

release 저장소에서:
```
cd C:\project\kakaotalk-a11y-release
git add -A
git commit -m "release: vX.X.X"
```

제외 목록은 `scripts/sync_release.py` 참조

### 6. 태그 생성 (release 저장소)

```
git tag -a vX.X.X -m "vX.X.X"
```

### 7. push (release 저장소)

```
git push origin main
git push origin vX.X.X
```

### 8. GitHub Releases 생성

```
gh release create vX.X.X dist/KakaotalkA11y-vX.X.X-win64.zip --notes "변경사항"
```

또는 CHANGELOG에서 해당 버전 섹션 복사하여 `--notes-file` 사용

## 주의사항

- client 저장소는 push 금지 (로컬 이력 보존용)
- 태그는 release 저장소에서만 생성
