#!/usr/bin/env python3
"""커밋 후 릴리즈 체크 훅.

git commit 성공 시 자동으로 릴리즈 트리거 확인.
feat 3개 이상 또는 fix 5개 이상 또는 improve 5개 이상 또는 docs 5개 이상이면 릴리즈 제안.
"""

import json
import re
import subprocess
import sys


def get_latest_version_tag() -> str | None:
    """최신 버전 태그 반환. 없으면 None."""
    try:
        result = subprocess.run(
            ["git", "tag", "--sort=-v:refname"],
            capture_output=True,
            text=True,
            check=True,
        )
        tags = result.stdout.strip().split("\n")
        for tag in tags:
            if re.match(r"^v?\d+\.\d+\.\d+", tag):
                return tag
        return None
    except subprocess.CalledProcessError:
        return None


def count_commits_since_tag(tag: str) -> dict[str, int]:
    """태그 이후 커밋 타입별 개수."""
    try:
        result = subprocess.run(
            ["git", "log", f"{tag}..HEAD", "--oneline", "--format=%s"],
            capture_output=True,
            text=True,
            check=True,
        )
        commits = result.stdout.strip().split("\n")
        counts = {"feat": 0, "fix": 0, "improve": 0, "docs": 0}

        for commit in commits:
            if not commit:
                continue
            # feat(scope): message 또는 feat: message 형식
            match = re.match(r"^(feat|fix|improve|docs)(\([^)]+\))?:", commit)
            if match:
                commit_type = match.group(1)
                counts[commit_type] += 1

        return counts
    except subprocess.CalledProcessError:
        return {"feat": 0, "fix": 0, "improve": 0, "docs": 0}


def main():
    # stdin에서 JSON 읽기
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return  # JSON 파싱 실패 시 무시

    # Bash 도구가 아니면 무시
    if data.get("tool_name") != "Bash":
        return

    # git commit 명령이 아니면 무시
    command = data.get("tool_input", {}).get("command", "")
    if not command.startswith("git commit"):
        return

    # 커밋 실패 시 무시 (에러 메시지 포함)
    result = data.get("tool_result", "")
    if "error" in result.lower() or "nothing to commit" in result.lower():
        return

    # 최신 태그 찾기
    tag = get_latest_version_tag()
    if not tag:
        print("릴리즈 체크: 버전 태그 없음")
        return

    # 커밋 카운트
    counts = count_commits_since_tag(tag)

    # 결과 출력
    feat = counts["feat"]
    fix = counts["fix"]
    improve = counts["improve"]
    docs = counts["docs"]

    status = f"릴리즈 체크 ({tag} 이후): feat {feat}/3, fix {fix}/5, improve {improve}/5, docs {docs}/5"

    # 트리거 충족 여부
    if feat >= 3:
        print(f"{status} → feat 트리거 충족! 릴리즈 고려")
    elif fix >= 5:
        print(f"{status} → fix 트리거 충족! 릴리즈 고려")
    elif improve >= 5:
        print(f"{status} → improve 트리거 충족! 릴리즈 고려")
    elif docs >= 5:
        print(f"{status} → docs 트리거 충족! 릴리즈 고려")
    else:
        print(status)


if __name__ == "__main__":
    main()
