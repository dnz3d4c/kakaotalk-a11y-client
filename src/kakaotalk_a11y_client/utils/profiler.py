# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""
UIA 성능 프로파일러
- 각 작업별 소요 시간 측정
- 병목 지점 자동 식별
- 로그 파일: <프로젝트>/logs/profile_*.log (DEBUG 모드에서만)
"""
import os
import time
import logging
import functools
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import json
from datetime import datetime


def _get_project_root() -> Path:
    """프로젝트 루트 디렉토리 반환"""
    # profiler.py 위치: src/kakaotalk_a11y_client/utils/profiler.py
    return Path(__file__).parent.parent.parent.parent


# 프로파일 로거 설정 (초기화 지연)
profile_logger = logging.getLogger('uia_profiler')
_debug_mode = False
log_dir: Optional[Path] = None
_profiler_initialized = False


def init_profiler(enabled: bool = None) -> None:
    """프로파일러 초기화 (main에서 호출)

    Args:
        enabled: True면 로그 활성화, None이면 환경변수 체크 (하위 호환)
    """
    global _debug_mode, log_dir, _profiler_initialized

    if _profiler_initialized:
        return
    _profiler_initialized = True

    # enabled가 None이면 환경변수 체크 (하위 호환)
    if enabled is None:
        enabled = os.environ.get("DEBUG", "0") in ("1", "2")

    _debug_mode = enabled

    if _debug_mode:
        profile_logger.setLevel(logging.DEBUG)
        log_dir = _get_project_root() / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f'profile_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s'))
        profile_logger.addHandler(file_handler)
    else:
        profile_logger.setLevel(logging.CRITICAL + 1)
        profile_logger.addHandler(logging.NullHandler())


@dataclass
class ProfileMetrics:
    """프로파일 메트릭 저장"""
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    samples: List[float] = field(default_factory=list)

    @property
    def avg_time(self) -> float:
        return self.total_time / self.call_count if self.call_count > 0 else 0.0

    def record(self, elapsed: float):
        self.call_count += 1
        self.total_time += elapsed
        self.min_time = min(self.min_time, elapsed)
        self.max_time = max(self.max_time, elapsed)
        # 최근 100개만 유지
        self.samples.append(elapsed)
        if len(self.samples) > 100:
            self.samples.pop(0)


class UIAProfiler:
    """UIA 작업 프로파일러"""

    _instance: Optional['UIAProfiler'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.metrics: Dict[str, ProfileMetrics] = {}
        self.enabled = True
        self.slow_threshold_ms = 100  # 100ms 이상이면 경고
        self._context_stack: List[str] = []

    @contextmanager
    def measure(self, operation: str):
        """컨텍스트 매니저로 시간 측정"""
        if not self.enabled:
            yield
            return

        full_name = f"{'.'.join(self._context_stack)}.{operation}" if self._context_stack else operation
        start = time.perf_counter()

        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000

            if full_name not in self.metrics:
                self.metrics[full_name] = ProfileMetrics()
            self.metrics[full_name].record(elapsed_ms)

            # 느린 작업 경고
            if elapsed_ms > self.slow_threshold_ms:
                profile_logger.warning(f"SLOW: {full_name} took {elapsed_ms:.1f}ms")
            else:
                profile_logger.debug(f"{full_name}: {elapsed_ms:.1f}ms")

    @contextmanager
    def context(self, name: str):
        """중첩 컨텍스트 (예: chat_room.get_messages)"""
        self._context_stack.append(name)
        try:
            yield
        finally:
            self._context_stack.pop()

    def profile_uia_search(self, control_type: str, search_params: dict, result_count: int, elapsed_ms: float):
        """UIA 검색 상세 로깅"""
        params_str = ', '.join(f"{k}={v}" for k, v in search_params.items() if v)
        profile_logger.info(
            f"UIA Search: {control_type}({params_str}) "
            f"-> {result_count} results in {elapsed_ms:.1f}ms"
        )

        # 결과가 많으면 경고
        if result_count > 50:
            profile_logger.warning(f"Large result set: {result_count} items - consider filtering")

    def profile_list_items(self, total: int, empty: int, valid: int, elapsed_ms: float):
        """리스트 아이템 필터링 로깅"""
        empty_ratio = (empty / total * 100) if total > 0 else 0
        profile_logger.info(
            f"ListItems: total={total}, empty={empty} ({empty_ratio:.0f}%), "
            f"valid={valid}, took {elapsed_ms:.1f}ms"
        )

        if empty_ratio > 80:
            profile_logger.warning(f"High empty ratio ({empty_ratio:.0f}%) - virtual scroll detected")

    def get_report(self) -> str:
        """성능 리포트 생성"""
        lines = ["=" * 60, "UIA Performance Report", "=" * 60, ""]

        # 느린 순 정렬
        sorted_metrics = sorted(
            self.metrics.items(),
            key=lambda x: x[1].avg_time,
            reverse=True
        )

        for name, m in sorted_metrics[:20]:  # 상위 20개
            lines.append(
                f"{name}:\n"
                f"  calls: {m.call_count}, avg: {m.avg_time:.1f}ms, "
                f"min: {m.min_time:.1f}ms, max: {m.max_time:.1f}ms"
            )

        return "\n".join(lines)

    def save_report(self, path: Optional[Path] = None):
        """리포트 파일 저장 (DEBUG 모드에서만 동작)"""
        if log_dir is None:
            return None  # DEBUG 모드가 아니면 저장하지 않음
        if path is None:
            path = log_dir / f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'

        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.get_report())

        # JSON으로도 저장 (분석용)
        json_path = path.with_suffix('.json')
        data = {
            name: {
                'call_count': m.call_count,
                'avg_time': m.avg_time,
                'min_time': m.min_time if m.min_time != float('inf') else 0,
                'max_time': m.max_time,
            }
            for name, m in self.metrics.items()
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        return path

    @staticmethod
    def load_report_json(path: Path) -> Dict:
        """JSON 리포트 파일 로드"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def generate_comparison_report(
        baseline_path: Path,
        current_path: Path,
        threshold_percent: float = 20.0
    ) -> str:
        """두 리포트 비교 분석

        Args:
            baseline_path: 기준 리포트 JSON 파일 경로
            current_path: 현재 리포트 JSON 파일 경로
            threshold_percent: 개선/저하 판단 임계값 (%, 기본값 20)

        Returns:
            마크다운 형식 비교 리포트
        """
        baseline = UIAProfiler.load_report_json(baseline_path)
        current = UIAProfiler.load_report_json(current_path)

        # 변경 분류
        improved = []  # 시간 단축
        degraded = []  # 시간 증가
        unchanged = []  # 변화 없음
        new_ops = []  # 새로 추가됨
        removed_ops = []  # 삭제됨

        all_ops = set(baseline.keys()) | set(current.keys())

        for op in all_ops:
            if op not in baseline:
                new_ops.append((op, current[op]))
            elif op not in current:
                removed_ops.append((op, baseline[op]))
            else:
                base_avg = baseline[op]['avg_time']
                curr_avg = current[op]['avg_time']

                if base_avg == 0:
                    if curr_avg > 0:
                        degraded.append((op, base_avg, curr_avg, float('inf')))
                    continue

                change_pct = ((curr_avg - base_avg) / base_avg) * 100

                if change_pct <= -threshold_percent:
                    improved.append((op, base_avg, curr_avg, change_pct))
                elif change_pct >= threshold_percent:
                    degraded.append((op, base_avg, curr_avg, change_pct))
                else:
                    unchanged.append((op, base_avg, curr_avg, change_pct))

        # 리포트 생성
        lines = [
            "# 성능 비교 리포트",
            "",
            f"- 기준: {baseline_path.name}",
            f"- 현재: {current_path.name}",
            f"- 임계값: ±{threshold_percent}%",
            "",
        ]

        # 개선된 항목
        if improved:
            lines.extend([
                "## 개선된 항목",
                "",
                "| 작업 | 이전(ms) | 현재(ms) | 변화 |",
                "|------|----------|----------|------|",
            ])
            for op, base, curr, pct in sorted(improved, key=lambda x: x[3]):
                lines.append(f"| {op} | {base:.1f} | {curr:.1f} | {pct:+.1f}% |")
            lines.append("")

        # 저하된 항목
        if degraded:
            lines.extend([
                "## 저하된 항목",
                "",
                "| 작업 | 이전(ms) | 현재(ms) | 변화 |",
                "|------|----------|----------|------|",
            ])
            for op, base, curr, pct in sorted(degraded, key=lambda x: -x[3]):
                pct_str = f"+{pct:.1f}%" if pct != float('inf') else "NEW"
                lines.append(f"| {op} | {base:.1f} | {curr:.1f} | {pct_str} |")
            lines.append("")

        # 변화 없음
        if unchanged:
            lines.extend([
                "## 변화 없음",
                "",
                f"- {len(unchanged)}개 작업 (±{threshold_percent}% 이내)",
                "",
            ])

        # 새로 추가됨
        if new_ops:
            lines.extend([
                "## 새로 추가됨",
                "",
                "| 작업 | 평균(ms) | 호출수 |",
                "|------|----------|--------|",
            ])
            for op, data in new_ops:
                lines.append(f"| {op} | {data['avg_time']:.1f} | {data['call_count']} |")
            lines.append("")

        # 삭제됨
        if removed_ops:
            lines.extend([
                "## 삭제됨",
                "",
                f"- {len(removed_ops)}개 작업",
                "",
            ])

        # 요약
        lines.extend([
            "## 요약",
            "",
            f"- 개선: {len(improved)}개",
            f"- 저하: {len(degraded)}개",
            f"- 변화 없음: {len(unchanged)}개",
            f"- 새로 추가: {len(new_ops)}개",
            f"- 삭제됨: {len(removed_ops)}개",
        ])

        return "\n".join(lines)


# 싱글톤 인스턴스
profiler = UIAProfiler()


def profile(operation: str = None):
    """데코레이터로 함수 프로파일링"""
    def decorator(func):
        op_name = operation or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with profiler.measure(op_name):
                return func(*args, **kwargs)

        return wrapper
    return decorator


# 편의 함수
def log_slow(message: str, elapsed_ms: float, threshold_ms: float = 100):
    """느린 작업 조건부 로깅"""
    if elapsed_ms > threshold_ms:
        profile_logger.warning(f"{message}: {elapsed_ms:.1f}ms (threshold: {threshold_ms}ms)")
