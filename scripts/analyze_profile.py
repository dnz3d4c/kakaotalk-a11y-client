#!/usr/bin/env python3
"""프로파일러 로그 분석 스크립트

logs/*.log 파일들을 분석하여 성능 통계를 추출한다.

사용법:
    python scripts/analyze_profile.py
    python scripts/analyze_profile.py --filter context_menu
    python scripts/analyze_profile.py --time 10:00-10:30
    python scripts/analyze_profile.py --filter context_menu --time 10:00-10:30
"""

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json


@dataclass
class OperationStats:
    """작업별 통계"""
    name: str
    times: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.times)

    @property
    def avg(self) -> float:
        return sum(self.times) / len(self.times) if self.times else 0

    @property
    def min_time(self) -> float:
        return min(self.times) if self.times else 0

    @property
    def max_time(self) -> float:
        return max(self.times) if self.times else 0

    @property
    def total(self) -> float:
        return sum(self.times)


def parse_timestamp(line: str) -> Optional[datetime]:
    """로그 라인에서 타임스탬프 추출"""
    # 형식: 2025-12-30 21:08:58,194 | ...
    match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+", line)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return None


def parse_time_range(time_str: str) -> Optional[Tuple[dt_time, dt_time]]:
    """시간 범위 문자열 파싱 (예: '10:00-10:30')"""
    if not time_str:
        return None
    match = re.match(r"(\d{1,2}:\d{2})-(\d{1,2}:\d{2})", time_str)
    if match:
        try:
            start = datetime.strptime(match.group(1), "%H:%M").time()
            end = datetime.strptime(match.group(2), "%H:%M").time()
            return (start, end)
        except ValueError:
            pass
    return None


def is_in_time_range(ts: datetime, time_range: Optional[Tuple[dt_time, dt_time]]) -> bool:
    """타임스탬프가 시간 범위 내인지 확인"""
    if not time_range:
        return True
    start, end = time_range
    ts_time = ts.time()
    return start <= ts_time <= end


def parse_log_files(
    log_dir: Path,
    filter_pattern: Optional[str] = None,
    time_range: Optional[Tuple[dt_time, dt_time]] = None
) -> Dict[str, OperationStats]:
    """로그 파일들 파싱

    Args:
        log_dir: 로그 디렉토리 경로
        filter_pattern: 작업명 필터 (부분 일치)
        time_range: 시간 범위 필터 (start_time, end_time)
    """
    stats: Dict[str, OperationStats] = {}

    # 시간 측정 패턴: "2025-12-30 21:08:58,194 | SLOW: operation took 123.4ms"
    # 또는 "2025-12-30 21:08:58,194 | operation: 123.4ms"
    slow_pattern = re.compile(r"\| SLOW: (.+?) took (\d+\.?\d*)ms")
    normal_pattern = re.compile(r"\| ([^|]+?): (\d+\.?\d*)ms$")

    log_files = sorted(log_dir.glob("profile_*.log"))
    print(f"분석할 로그 파일: {len(log_files)}개")

    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    # 타임스탬프 추출
                    ts = parse_timestamp(line)

                    # 시간 범위 필터
                    if ts and time_range and not is_in_time_range(ts, time_range):
                        continue

                    # SLOW 패턴 먼저 시도
                    match = slow_pattern.search(line)
                    if match:
                        name = match.group(1).strip()
                        time_ms = float(match.group(2))
                    else:
                        # 일반 패턴 시도
                        match = normal_pattern.search(line)
                        if match:
                            name = match.group(1).strip()
                            time_ms = float(match.group(2))
                        else:
                            continue

                    # 작업명 필터
                    if filter_pattern and filter_pattern.lower() not in name.lower():
                        continue

                    if name not in stats:
                        stats[name] = OperationStats(name=name)
                    stats[name].times.append(time_ms)
                    if ts:
                        stats[name].timestamps.append(ts)
        except Exception as e:
            print(f"오류 ({log_file.name}): {e}")

    return stats


def get_timeline_analysis(
    stats: Dict[str, OperationStats],
    bucket_minutes: int = 5
) -> List[Dict]:
    """시간대별 성능 분석

    Args:
        stats: 작업별 통계
        bucket_minutes: 시간 버킷 크기 (분)

    Returns:
        [{'time': '10:00-10:05', 'avg_ms': 45.2, 'slow_count': 2, 'total_ops': 15}, ...]
    """
    # 모든 측정값을 타임스탬프와 함께 수집
    all_measurements: List[Tuple[datetime, float]] = []
    for op in stats.values():
        for i, t in enumerate(op.times):
            if i < len(op.timestamps):
                all_measurements.append((op.timestamps[i], t))

    if not all_measurements:
        return []

    # 시간순 정렬
    all_measurements.sort(key=lambda x: x[0])

    # 버킷으로 그룹화
    buckets: Dict[str, List[float]] = defaultdict(list)
    for ts, time_ms in all_measurements:
        # 버킷 시작 시간 계산
        bucket_start_min = (ts.minute // bucket_minutes) * bucket_minutes
        bucket_start = ts.replace(minute=bucket_start_min, second=0, microsecond=0)
        bucket_end_min = bucket_start_min + bucket_minutes
        if bucket_end_min >= 60:
            bucket_end = bucket_start.replace(hour=bucket_start.hour + 1, minute=0)
        else:
            bucket_end = bucket_start.replace(minute=bucket_end_min)

        bucket_key = f"{bucket_start.strftime('%H:%M')}-{bucket_end.strftime('%H:%M')}"
        buckets[bucket_key].append(time_ms)

    # 결과 생성
    result = []
    for time_range, times in sorted(buckets.items()):
        slow_count = sum(1 for t in times if t > 100)
        result.append({
            "time": time_range,
            "avg_ms": sum(times) / len(times),
            "slow_count": slow_count,
            "total_ops": len(times)
        })

    return result


def parse_list_items(log_dir: Path) -> Dict[str, Dict]:
    """ListItems 통계 파싱"""
    list_stats = {
        "total_calls": 0,
        "empty_ratios": [],
        "high_empty_count": 0,  # 80% 이상
        "by_context": defaultdict(list),
    }

    # ListItems: total=11, empty=0 (0%), valid=11, took 3.4ms
    pattern = re.compile(r"ListItems: total=(\d+), empty=(\d+) \((\d+)%\)")

    for log_file in sorted(log_dir.glob("profile_*.log")):
        try:
            current_context = ""
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    # 컨텍스트 추출 (context_menu.xxx 형태)
                    if "context_menu" in line:
                        current_context = "context_menu"
                    elif "find_all_descendants" in line and "context_menu" not in line:
                        current_context = "chat_list"

                    match = pattern.search(line)
                    if match:
                        total = int(match.group(1))
                        empty = int(match.group(2))
                        ratio = int(match.group(3))

                        list_stats["total_calls"] += 1
                        list_stats["empty_ratios"].append(ratio)

                        if ratio >= 80:
                            list_stats["high_empty_count"] += 1

                        list_stats["by_context"][current_context].append({
                            "total": total,
                            "empty": empty,
                            "ratio": ratio
                        })
        except Exception:
            pass

    return list_stats


def parse_retry_stats(log_dir: Path) -> Dict[str, Dict]:
    """재시도 통계 파싱"""
    retry_stats = {
        "attempts": [],
        "by_attempt": defaultdict(int),
    }

    # 메뉴 찾기 성공: attempt=1
    pattern = re.compile(r"메뉴 찾기 성공: attempt=(\d+)")

    for log_file in sorted(log_dir.glob("profile_*.log")):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    match = pattern.search(line)
                    if match:
                        attempt = int(match.group(1))
                        retry_stats["attempts"].append(attempt)
                        retry_stats["by_attempt"][attempt] += 1
        except Exception:
            pass

    return retry_stats


def generate_report(stats: Dict[str, OperationStats],
                   list_stats: Dict,
                   retry_stats: Dict,
                   timeline: Optional[List[Dict]] = None,
                   filter_info: Optional[str] = None) -> str:
    """마크다운 리포트 생성"""
    lines = [
        "# 프로파일러 분석 결과",
        "",
        "## 측정 환경",
        f"- 분석 로그 수: {len(list(Path('logs').glob('profile_*.log')))}개",
        f"- 총 작업 유형: {len(stats)}개",
    ]

    if filter_info:
        lines.append(f"- 필터: {filter_info}")

    lines.extend([
        "",
        "## 병목 지점 Top 10 (평균 시간 기준)",
        "",
        "| 순위 | 작업 | 호출수 | 평균(ms) | 최소(ms) | 최대(ms) |",
        "|------|------|--------|----------|----------|----------|",
    ]

    # 평균 시간 기준 정렬
    sorted_stats = sorted(stats.values(), key=lambda x: x.avg, reverse=True)

    for i, op in enumerate(sorted_stats[:10], 1):
        lines.append(
            f"| {i} | {op.name} | {op.count} | {op.avg:.1f} | {op.min_time:.1f} | {op.max_time:.1f} |"
        )

    # SLOW 작업만 필터링
    lines.extend([
        "",
        "## SLOW 작업 (100ms 이상)",
        "",
        "| 작업 | 발생 횟수 | 평균(ms) | 최대(ms) |",
        "|------|----------|----------|----------|",
    ])

    slow_ops = [(name, op) for name, op in stats.items()
                if any(t > 100 for t in op.times)]
    slow_ops.sort(key=lambda x: x[1].max_time, reverse=True)

    for name, op in slow_ops[:10]:
        slow_times = [t for t in op.times if t > 100]
        lines.append(
            f"| {name} | {len(slow_times)} | {sum(slow_times)/len(slow_times):.1f} | {max(slow_times):.1f} |"
        )

    # 빈 항목 통계
    lines.extend([
        "",
        "## 빈 항목(empty) 통계",
        "",
        f"- 총 ListItems 호출: {list_stats['total_calls']}회",
        f"- 80% 이상 빈 항목: {list_stats['high_empty_count']}회 ({list_stats['high_empty_count']/list_stats['total_calls']*100:.1f}%)" if list_stats['total_calls'] > 0 else "- 데이터 없음",
    ])

    if list_stats["empty_ratios"]:
        avg_empty = sum(list_stats["empty_ratios"]) / len(list_stats["empty_ratios"])
        lines.append(f"- 평균 빈 항목 비율: {avg_empty:.1f}%")

    # 재시도 통계
    lines.extend([
        "",
        "## 메뉴 찾기 재시도 통계",
        "",
    ])

    if retry_stats["attempts"]:
        avg_attempt = sum(retry_stats["attempts"]) / len(retry_stats["attempts"])
        max_attempt = max(retry_stats["attempts"])
        lines.append(f"- 총 시도: {len(retry_stats['attempts'])}회")
        lines.append(f"- 평균 재시도: {avg_attempt:.1f}회")
        lines.append(f"- 최대 재시도: {max_attempt}회")
        lines.append("")
        lines.append("| 시도 횟수 | 발생 빈도 |")
        lines.append("|----------|----------|")
        for attempt, count in sorted(retry_stats["by_attempt"].items()):
            lines.append(f"| {attempt} | {count} |")
    else:
        lines.append("- 데이터 없음")

    # 시간대별 분석
    if timeline:
        lines.extend([
            "",
            "## 시간대별 성능",
            "",
            "| 시간대 | 평균(ms) | SLOW 횟수 | 총 작업수 |",
            "|--------|----------|-----------|----------|",
        ])
        for bucket in timeline:
            lines.append(
                f"| {bucket['time']} | {bucket['avg_ms']:.1f} | {bucket['slow_count']} | {bucket['total_ops']} |"
            )

    # 개선 제안
    lines.extend([
        "",
        "## 개선 제안",
        "",
    ])

    # 가장 느린 작업 기반 제안
    if sorted_stats:
        top_slow = sorted_stats[0]
        if "find_menu_from_focus" in top_slow.name:
            lines.append("1. **find_menu_from_focus 최적화**: 포커스 부모 탐색 시 타임아웃 추가 또는 캐싱 적용")
        if "find_eva_menu" in top_slow.name:
            lines.append("2. **EVA_Menu 검색 최적화**: searchDepth 줄이거나 캐싱 적용")
        if "right_click" in top_slow.name:
            lines.append("3. **우클릭 대기 시간**: Windows API 응답 시간으로 개선 어려움 (정상)")

    if list_stats["high_empty_count"] > list_stats["total_calls"] * 0.1:
        lines.append(f"4. **가상 스크롤 최적화**: 빈 항목이 {list_stats['high_empty_count']/list_stats['total_calls']*100:.1f}%로 높음, SmartListFilter 튜닝 필요")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="프로파일러 로그 분석",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/analyze_profile.py
  python scripts/analyze_profile.py --filter context_menu
  python scripts/analyze_profile.py --time 10:00-10:30
  python scripts/analyze_profile.py --filter menu --time 09:00-12:00
        """
    )
    parser.add_argument(
        "--filter", "-f",
        help="작업명 필터 (부분 일치)",
        default=None
    )
    parser.add_argument(
        "--time", "-t",
        help="시간 범위 필터 (예: 10:00-10:30)",
        default=None
    )
    parser.add_argument(
        "--bucket",
        type=int,
        default=5,
        help="시간대별 분석 버킷 크기 (분, 기본값: 5)"
    )
    args = parser.parse_args()

    log_dir = Path(__file__).parent.parent / "logs"

    if not log_dir.exists():
        print(f"로그 디렉토리 없음: {log_dir}")
        sys.exit(1)

    # 필터 정보 구성
    filter_parts = []
    if args.filter:
        filter_parts.append(f"작업명='{args.filter}'")
    if args.time:
        filter_parts.append(f"시간={args.time}")
    filter_info = ", ".join(filter_parts) if filter_parts else None

    # 시간 범위 파싱
    time_range = parse_time_range(args.time) if args.time else None
    if args.time and not time_range:
        print(f"시간 범위 형식 오류: {args.time} (예: 10:00-10:30)")
        sys.exit(1)

    print("=== 프로파일러 로그 분석 ===\n")
    if filter_info:
        print(f"필터: {filter_info}\n")

    # 파싱
    print("1. 작업별 시간 측정 파싱...")
    stats = parse_log_files(log_dir, args.filter, time_range)
    print(f"   {len(stats)}개 작업 유형 발견")

    print("2. ListItems 통계 파싱...")
    list_stats = parse_list_items(log_dir)
    print(f"   {list_stats['total_calls']}회 호출")

    print("3. 재시도 통계 파싱...")
    retry_stats = parse_retry_stats(log_dir)
    print(f"   {len(retry_stats['attempts'])}회 메뉴 찾기 기록")

    print("4. 시간대별 분석...")
    timeline = get_timeline_analysis(stats, args.bucket)
    print(f"   {len(timeline)}개 시간대")

    # 리포트 생성
    print("\n5. 리포트 생성...")
    report = generate_report(stats, list_stats, retry_stats, timeline, filter_info)

    # 출력 및 저장
    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(exist_ok=True)

    output_file = docs_dir / "PROFILER_ANALYSIS.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n리포트 저장됨: {output_file}")
    print("\n" + "=" * 50)
    print(report)


if __name__ == "__main__":
    main()
