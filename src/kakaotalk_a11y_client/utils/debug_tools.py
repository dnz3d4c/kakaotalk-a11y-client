# SPDX-License-Identifier: MIT
# Copyright 2025-2026 dnz3d4c
"""디버그 도구 통합 관리. 에러/느린 작업 발생 시 자동 덤프."""

import json
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import uiautomation as auto

from .debug_config import debug_config
from .profiler import profiler
from .uia_utils import dump_tree_json


class KakaoNotFoundError(Exception):
    pass


class DebugToolManager:

    def __init__(self):
        self._session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self._session_start = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self._dump_count = 0
        self._issues: list[dict] = []
        self._last_dump_times: dict[str, float] = {}
        self._cleanup_done = False

    @contextmanager
    def debug_operation(
        self,
        operation_name: str,
        auto_dump_on_error: bool = True,
        auto_dump_on_slow: bool = True
    ):
        """작업 시간 측정 + 에러/느린 작업 시 자동 트리 덤프."""
        if not debug_config.enabled:
            yield
            return

        start_time = datetime.now()
        error_occurred = False

        try:
            with profiler.measure(operation_name):
                yield
        except Exception as e:
            error_occurred = True

            if auto_dump_on_error and debug_config.auto_dump_on_error:
                self._auto_dump(
                    trigger=f'error_{operation_name}',
                    context={
                        'operation': operation_name,
                        'error': str(e),
                        'traceback': traceback.format_exc()
                    }
                )
            raise
        finally:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

            # 느린 작업 덤프
            if (not error_occurred and
                auto_dump_on_slow and
                debug_config.auto_dump_on_slow and
                elapsed_ms > debug_config.slow_threshold_ms):

                self._auto_dump(
                    trigger=f'slow_{operation_name}',
                    context={
                        'operation': operation_name,
                        'elapsed_ms': elapsed_ms,
                        'threshold_ms': debug_config.slow_threshold_ms
                    }
                )

    def _find_kakao_window(self) -> auto.Control:
        root = auto.GetRootControl()
        for win in root.GetChildren():
            name = win.Name or ''
            cls = win.ClassName or ''
            if 'EVA' in cls or '카카오톡' in name:
                return win
        raise KakaoNotFoundError("카카오톡 창을 찾을 수 없습니다")

    def dump_to_file(
        self,
        filename_prefix: str = 'manual',
        include_coords: bool = True,
        max_depth: int = 6
    ) -> Path:
        """카카오톡 UIA 트리를 JSON 파일로 저장."""
        kakao = self._find_kakao_window()

        tree = dump_tree_json(kakao, max_depth=max_depth, include_coords=include_coords)

        timestamp = datetime.now().strftime('%H%M%S')
        filename = f'{filename_prefix}_{timestamp}.json'
        dump_path = debug_config.debug_output_dir / filename

        dump_path.write_text(
            json.dumps(tree, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        self._dump_count += 1
        return dump_path

    def _auto_dump(self, trigger: str, context: dict):
        if not self._cleanup_done:
            self._cleanup_done = True
            self.cleanup_old_dumps()

        # 쿨다운 체크
        now = time.monotonic()
        cooldown = debug_config.dump_cooldown_seconds
        last_time = self._last_dump_times.get(trigger, 0)
        if now - last_time < cooldown:
            return
        self._last_dump_times[trigger] = now

        try:
            timestamp = datetime.now().strftime('%H%M%S')
            filename = f'auto_{trigger}_{timestamp}'

            dump_path = self.dump_to_file(
                filename_prefix=filename,
                include_coords=True
            )

            # 컨텍스트 정보도 저장
            context_path = dump_path.with_suffix('.context.json')
            context_path.write_text(
                json.dumps(context, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )

            # 이슈 기록
            self._issues.append({
                'trigger': trigger,
                'time': datetime.now().isoformat(),
                'dump_path': str(dump_path),
                **context
            })

            print(f"[DEBUG] 자동 덤프: {dump_path}")
        except KakaoNotFoundError:
            print("[DEBUG] 자동 덤프 실패: 카카오톡 창 없음")
        except Exception as e:
            print(f"[DEBUG] 자동 덤프 실패: {e}")

    def cleanup_old_dumps(self):
        """오래된 auto_* 덤프 파일 정리."""
        try:
            output_dir = debug_config.debug_output_dir
            if not output_dir.exists():
                return

            dump_files = sorted(
                output_dir.glob('auto_*'),
                key=lambda p: p.stat().st_mtime
            )
            max_files = debug_config.max_dump_files * 2
            if len(dump_files) > max_files:
                to_delete = dump_files[:-max_files]
                for f in to_delete:
                    f.unlink()
                print(f"[DEBUG] 오래된 덤프 {len(to_delete)}개 삭제")
        except Exception:
            pass

    def dump_on_condition(
        self,
        condition_name: str,
        condition_met: bool,
        context: Optional[dict] = None
    ):
        """조건 충족 + auto_analyze_scenarios에 등록된 경우 자동 덤프."""
        if not debug_config.enabled:
            return

        if not condition_met:
            return

        if condition_name not in debug_config.auto_analyze_scenarios:
            return

        self._auto_dump(
            trigger=condition_name,
            context=context or {}
        )

    def log_debug(self, message: str, **kwargs):
        if debug_config.enabled:
            extra = ' | '.join(f'{k}={v}' for k, v in kwargs.items())
            print(f"[DEBUG] {message}" + (f" | {extra}" if extra else ""))

    def generate_session_report(self) -> Optional[Path]:
        """세션 리포트 생성: 프로파일러 요약, 덤프 목록, 에러 내역."""
        if not debug_config.enabled:
            return None

        report_path = (
            debug_config.debug_output_dir /
            f'session_{self._session_id}_report.md'
        )

        dump_list = self._format_dump_list()
        issues_text = self._format_issues()

        report = f"""# 디버그 세션 리포트

## 세션 정보
- 세션 ID: {self._session_id}
- 시작 시각: {self._session_start}
- 종료 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 총 덤프 수: {self._dump_count}

## 프로파일러 요약
{profiler.get_report()}

## 자동 덤프 목록
{dump_list}

## 발생한 문제
{issues_text}
"""

        report_path.write_text(report, encoding='utf-8')
        print(f"[DEBUG] 세션 리포트 저장: {report_path}")
        return report_path

    def _format_dump_list(self) -> str:
        try:
            dumps = list(debug_config.debug_output_dir.glob(f'auto_*'))
            if not dumps:
                return "- 자동 덤프 없음"

            lines = []
            for dump in sorted(dumps)[-20:]:  # 최근 20개만
                lines.append(f"- {dump.name}")
            return '\n'.join(lines)
        except Exception:
            return "- 덤프 목록 로드 실패"

    def _format_issues(self) -> str:
        if not self._issues:
            return "- 발생한 문제 없음"

        lines = []
        for issue in self._issues[-10:]:  # 최근 10개
            trigger = issue.get('trigger', 'unknown')
            time = issue.get('time', '')
            error = issue.get('error', '')
            lines.append(f"- [{time}] {trigger}")
            if error:
                lines.append(f"  Error: {error[:100]}")
        return '\n'.join(lines)


# 전역 인스턴스
debug_tools = DebugToolManager()
