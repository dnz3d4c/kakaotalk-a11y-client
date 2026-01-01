#!/bin/bash
# 카카오톡 이모지 클릭커 자동 셋업 스크립트
# Claude Code가 이 스크립트를 실행하면 프로젝트 초기화 완료

set -e

PROJECT_NAME="kakaotalk-emoji-clicker"
PROJECT_DIR="$HOME/projects/$PROJECT_NAME"

echo "=== 카카오톡 이모지 클릭커 프로젝트 셋업 시작 ==="

# 1. 프로젝트 디렉토리 생성
echo "[1/5] 프로젝트 디렉토리 생성..."
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# 2. 압축 파일이 있으면 풀기 (클코가 압축 파일 경로를 인자로 전달)
if [ -n "$1" ] && [ -f "$1" ]; then
    echo "[2/5] 압축 파일 풀기..."
    unzip -o "$1" -d "$PROJECT_DIR"
    # 중첩 폴더 있으면 평탄화
    if [ -d "$PROJECT_DIR/kakaotalk_emoji_clicker" ]; then
        mv "$PROJECT_DIR/kakaotalk_emoji_clicker/"* "$PROJECT_DIR/" 2>/dev/null || true
        rmdir "$PROJECT_DIR/kakaotalk_emoji_clicker" 2>/dev/null || true
    fi
else
    echo "[2/5] 압축 파일 없음, 기존 파일 사용..."
fi

# 3. UV로 프로젝트 초기화 (pyproject.toml 있으면 스킵)
echo "[3/5] UV 환경 설정..."
if [ ! -f "pyproject.toml" ]; then
    uv init --name "$PROJECT_NAME"
fi

# 4. 의존성 설치
echo "[4/5] 패키지 설치..."
uv sync

# 5. 소스 디렉토리 구조 생성
echo "[5/5] 소스 디렉토리 구조 생성..."
mkdir -p src/kakaotalk_emoji_clicker
mkdir -p templates
mkdir -p samples

# __init__.py 생성
touch src/kakaotalk_emoji_clicker/__init__.py

# 샘플 파일 이동
if [ -d "samples" ] && [ "$(ls -A samples 2>/dev/null)" ]; then
    echo "샘플 이미지 확인됨"
fi

echo ""
echo "=== 셋업 완료 ==="
echo "프로젝트 경로: $PROJECT_DIR"
echo ""
echo "다음 단계:"
echo "1. cd $PROJECT_DIR"
echo "2. uv run python -c 'import cv2; print(cv2.__version__)' 로 설치 확인"
echo "3. README.md 읽고 개발 시작"
