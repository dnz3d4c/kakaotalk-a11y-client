# 카카오톡 접근성 클라이언트 - UIA 분석 도구 프롬프트

> **활용 배경**: 성능 병목 원인 파악을 위해 분석 도구가 필요했음. 기존에 어떤 도구가 있는지 파악하고, 부족한 부분만 개발하도록 "기존 먼저 확인 → 필요시 신규 개발" 프로세스로 지시.

**목적**: UIA 탐색/이벤트/프로파일링 도구 점검 및 개발
**대상**: Claude Code
**우선순위**: 기존 도구 활용 극대화 → 부족한 부분만 신규 개발

---

## 배경

카카오톡 PC 접근성 클라이언트 개발 중입니다. 현재 프로파일러와 로깅 시스템이 구현되어 있으며, 실사용 테스트 단계에서 병목 지점 발견 및 개선에 활용합니다.

---

## Phase 1: 기존 도구 현황 파악

### 지시사항

프로젝트 소스코드를 탐색하여 다음 카테고리별 기존 구현 상태를 파악하라.

```
1. UIA 트리 탐색 도구
2. UIA 이벤트 수신 도구  
3. 성능 프로파일러
4. 로깅 시스템
5. 분석/리포트 도구
```

### 확인 항목

| 카테고리 | 확인 파일 | 확인 내용 |
|----------|----------|----------|
| UIA 트리 탐색 | `utils/uia_utils.py` | `dump_tree()`, `get_children_recursive()` 존재 여부 |
| UIA 이벤트 | `main.py`, `utils/*.py` | 이벤트 핸들러 등록 코드 존재 여부 |
| 프로파일러 | `utils/profiler.py` | `UIAProfiler`, `@profile` 데코레이터 |
| 로깅 | `utils/profiler.py`, `config.py` | 로그 파일 경로, 로깅 레벨 |
| 분석 도구 | `scripts/`, `tools/` | 로그 분석 스크립트 존재 여부 |

### 출력 형식

```markdown
## 기존 도구 현황

### 1. UIA 트리 탐색
- **파일**: 
- **함수**: 
- **상태**: [구현됨/미구현/부분구현]
- **기능**: 

### 2. UIA 이벤트 수신
- **파일**: 
- **함수**: 
- **상태**: 
- **기능**: 

(이하 동일 형식)
```

---

## Phase 2: 도구별 분석 및 개선 검토

### 2.1 UIA 트리 탐색 도구

#### 필수 기능

| 기능 | 설명 | 활용 시나리오 |
|------|------|---------------|
| 트리 덤프 | UIA 요소 계층 구조 출력 | 카카오톡 UI 구조 파악 |
| 필터링 덤프 | 특정 조건 요소만 출력 | 빈 ListItem 분포 확인 |
| 비교 덤프 | 두 시점 트리 비교 | 동적 UI 변화 추적 |
| 실시간 인스펙션 | 포커스 요소 정보 출력 | 탐색 중 현재 위치 확인 |

#### 검토 항목

```
□ dump_tree() 함수가 max_depth, filter 옵션 지원하는가?
□ 파일 출력 기능 있는가?
□ ClassName, AutomationId, ControlType 모두 출력하는가?
□ BoundingRectangle(좌표) 출력 옵션 있는가?
□ 빈 Name 요소 강조 표시하는가?
```

#### 개선이 필요한 경우 구현 가이드

```python
# utils/uia_inspector.py (신규 또는 기존 확장)

"""
UIA 트리 인스펙션 도구 - 카카오톡 전용

목적:
- 카카오톡 UI 구조 파악
- 빈 ListItem 분포 확인  
- 탐색 경로 최적화 근거 수집

중요:
- 이 도구는 카카오톡 창만 대상으로 함
- 다른 프로그램 트리 탐색 불가 (의도적 제한)
- 카카오톡 창이 없으면 에러 발생

기존 dump_tree()와의 차이:
- 카카오톡 창 자동 탐색 및 한정
- 프로파일러 연동 (탐색 시간 측정)
- 필터링/강조 기능 강화
- JSON 출력 지원 (분석 스크립트 연동)
"""

from typing import Optional, List, Callable, Dict, Any
import uiautomation as auto
import json
from pathlib import Path
from datetime import datetime

# 카카오톡 창 식별 정보
KAKAO_WINDOW_NAMES = ['카카오톡']
KAKAO_WINDOW_CLASSES = ['EVA_Window_Dblclk', 'EVA_Window']


class KakaoNotFoundError(Exception):
    """카카오톡 창을 찾을 수 없을 때 발생"""
    pass


class UIAInspector:
    """UIA 트리 인스펙션 도구 - 카카오톡 전용"""
    
    def __init__(self, profiler=None):
        self.profiler = profiler
        self.output_dir = Path.home() / '.kakaotalk_a11y' / 'inspections'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._kakao_window: Optional[auto.WindowControl] = None
    
    def _find_kakao_window(self, force_refresh: bool = False) -> auto.WindowControl:
        """
        카카오톡 메인 창 찾기
        
        Args:
            force_refresh: 캐시 무시하고 다시 찾기
        
        Returns:
            카카오톡 WindowControl
        
        Raises:
            KakaoNotFoundError: 카카오톡 창이 없을 때
        """
        if self._kakao_window and not force_refresh:
            if self._kakao_window.Exists(timeout=0.1):
                return self._kakao_window
        
        # 이름으로 찾기
        for name in KAKAO_WINDOW_NAMES:
            window = auto.WindowControl(searchDepth=1, Name=name)
            if window.Exists(timeout=1):
                self._kakao_window = window
                return window
        
        # 클래스로 찾기 (이름이 다를 경우 대비)
        for class_name in KAKAO_WINDOW_CLASSES:
            window = auto.WindowControl(searchDepth=1, ClassName=class_name)
            if window.Exists(timeout=1):
                self._kakao_window = window
                return window
        
        raise KakaoNotFoundError(
            "카카오톡 창을 찾을 수 없습니다. "
            "카카오톡이 실행 중인지 확인하세요."
        )
    
    def get_kakao_window(self) -> auto.WindowControl:
        """카카오톡 창 반환 (외부 접근용)"""
        return self._find_kakao_window()
    
    def dump_tree(
        self,
        start_from: Optional[auto.Control] = None,
        max_depth: int = 6,
        filter_fn: Optional[Callable[[auto.Control], bool]] = None,
        include_coords: bool = False,
        highlight_empty: bool = True,
        output_format: str = 'text'  # 'text' | 'json'
    ) -> str:
        """
        카카오톡 UIA 트리 덤프
        
        Args:
            start_from: 탐색 시작 요소 (None이면 카카오톡 메인 창)
                        ※ 반드시 카카오톡 창 내부 요소여야 함
            max_depth: 최대 깊이
            filter_fn: 필터 함수 (True면 출력)
            include_coords: BoundingRectangle 포함 여부
            highlight_empty: Name 빈 요소 강조
            output_format: 출력 형식
        
        Returns:
            덤프 결과 문자열 또는 JSON
        
        Raises:
            KakaoNotFoundError: 카카오톡 창이 없을 때
            ValueError: start_from이 카카오톡 창 외부 요소일 때
        """
        kakao = self._find_kakao_window()
        
        if start_from is None:
            root = kakao
        else:
            # start_from이 카카오톡 창 내부인지 검증
            if not self._is_descendant_of_kakao(start_from, kakao):
                raise ValueError(
                    "start_from은 카카오톡 창 내부 요소여야 합니다. "
                    "이 도구는 카카오톡 전용입니다."
                )
            root = start_from
        
        # 덤프 실행
        # ... 구현 ...
        pass
    
    def _is_descendant_of_kakao(
        self, 
        control: auto.Control, 
        kakao: auto.WindowControl
    ) -> bool:
        """control이 카카오톡 창의 하위 요소인지 확인"""
        # 카카오톡 창의 BoundingRectangle 내에 있는지 확인
        # 또는 부모 체인을 따라가서 카카오톡 창에 도달하는지 확인
        try:
            kakao_rect = kakao.BoundingRectangle
            control_rect = control.BoundingRectangle
            # 좌표 기반 검증 (간단한 방법)
            return (kakao_rect.left <= control_rect.left and
                    kakao_rect.top <= control_rect.top and
                    kakao_rect.right >= control_rect.right and
                    kakao_rect.bottom >= control_rect.bottom)
        except:
            return False
    
    def dump_to_file(
        self,
        filename_prefix: str = 'kakao_dump',
        start_from: Optional[auto.Control] = None,
        **kwargs
    ) -> Path:
        """카카오톡 트리를 파일로 덤프 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{filename_prefix}_{timestamp}'
        # ...
        pass
    
    def compare_trees(
        self,
        tree1_path: Path,
        tree2_path: Path
    ) -> Dict[str, Any]:
        """두 카카오톡 덤프 파일 비교"""
        pass
    
    def realtime_inspect(
        self,
        interval_ms: int = 500,
        duration_sec: int = 30
    ):
        """
        카카오톡 내 실시간 포커스 요소 인스펙션
        
        개발/디버깅 용도:
        - 카카오톡 내 현재 포커스 요소 정보 실시간 출력
        - 탐색 중 어떤 요소에 있는지 확인
        
        주의:
        - 카카오톡이 활성 창일 때만 동작
        - 다른 프로그램으로 포커스 이동 시 무시
        """
        pass
    
    def dump_chat_list(self, **kwargs) -> str:
        """채팅 목록 영역만 덤프 (편의 함수)"""
        kakao = self._find_kakao_window()
        # 채팅 목록 컨트롤 찾기
        chat_list = kakao.ListControl(searchDepth=5)  # 실제 탐색 로직
        return self.dump_tree(start_from=chat_list, **kwargs)
    
    def dump_chat_room(self, **kwargs) -> str:
        """채팅방 메시지 영역만 덤프 (편의 함수)"""
        kakao = self._find_kakao_window()
        # 메시지 목록 컨트롤 찾기
        # ...
        pass
```

---

### 2.2 UIA 이벤트 수신 도구

#### 필수 기능

| 기능 | 설명 | 활용 시나리오 |
|------|------|---------------|
| 포커스 변경 이벤트 | 포커스 이동 감지 | 탐색 시 NVDA 읽기 트리거 |
| 구조 변경 이벤트 | 자식 요소 추가/삭제 감지 | 새 메시지 도착 감지 |
| 속성 변경 이벤트 | Name, Value 등 변경 감지 | 메시지 내용 업데이트 감지 |
| 이벤트 로깅 | 수신 이벤트 기록 | 이벤트 타이밍 분석 |

#### 검토 항목

```
□ uiautomation 이벤트 핸들러 사용 중인가?
□ 현재 폴링 방식인가 이벤트 방식인가?
□ 이벤트 수신 시 로깅하고 있는가?
□ 이벤트 오버헤드 측정하고 있는가?
```

#### 개선이 필요한 경우 구현 가이드

```python
# utils/uia_events.py (신규)

"""
UIA 이벤트 모니터링 도구 - 카카오톡 전용

목적:
- 폴링 vs 이벤트 방식 성능 비교 근거 수집
- 카카오톡 이벤트 발생 패턴 파악
- 메뉴 생성 타이밍 정확히 파악

중요:
- 이 도구는 카카오톡 창 내 이벤트만 모니터링
- 다른 프로그램 이벤트는 무시 (의도적 제한)
- 카카오톡 창이 없으면 에러 발생

주의:
- 카카오톡 같은 커스텀 앱은 이벤트가 불안정할 수 있음
- 분석 용도로만 사용, 프로덕션 코드에는 폴링 유지 권장
"""

import uiautomation as auto
from typing import Callable, Optional
from datetime import datetime
import logging
from threading import Thread, Event

# 카카오톡 창 식별 (uia_inspector.py와 공유 가능)
KAKAO_WINDOW_NAMES = ['카카오톡']
KAKAO_WINDOW_CLASSES = ['EVA_Window_Dblclk', 'EVA_Window']


class KakaoNotFoundError(Exception):
    """카카오톡 창을 찾을 수 없을 때 발생"""
    pass


class UIAEventMonitor:
    """UIA 이벤트 모니터링 - 카카오톡 전용"""
    
    def __init__(self, log_to_file: bool = True):
        self.logger = self._setup_logger(log_to_file)
        self._stop_event = Event()
        self._handlers = []
        self._kakao_window: Optional[auto.WindowControl] = None
    
    def _find_kakao_window(self) -> auto.WindowControl:
        """카카오톡 메인 창 찾기"""
        for name in KAKAO_WINDOW_NAMES:
            window = auto.WindowControl(searchDepth=1, Name=name)
            if window.Exists(timeout=1):
                self._kakao_window = window
                return window
        
        for class_name in KAKAO_WINDOW_CLASSES:
            window = auto.WindowControl(searchDepth=1, ClassName=class_name)
            if window.Exists(timeout=1):
                self._kakao_window = window
                return window
        
        raise KakaoNotFoundError(
            "카카오톡 창을 찾을 수 없습니다. "
            "카카오톡이 실행 중인지 확인하세요."
        )
    
    def _is_kakao_element(self, element: auto.Control) -> bool:
        """이 요소가 카카오톡 창 내부인지 확인"""
        if not self._kakao_window:
            return False
        try:
            kakao_rect = self._kakao_window.BoundingRectangle
            elem_rect = element.BoundingRectangle
            return (kakao_rect.left <= elem_rect.left and
                    kakao_rect.top <= elem_rect.top and
                    kakao_rect.right >= elem_rect.right and
                    kakao_rect.bottom >= elem_rect.bottom)
        except:
            return False
    
    def start_focus_monitor(
        self,
        callback: Optional[Callable[[auto.Control], None]] = None
    ):
        """
        카카오톡 내 포커스 변경 이벤트 모니터링 시작
        
        목적:
        - 현재 폴링 방식과 이벤트 방식 비교
        - 포커스 변경 타이밍 정확도 측정
        
        동작:
        - 카카오톡 창 외부로 포커스 이동 시 이벤트 무시
        - 카카오톡 창 내부 포커스 변경만 로깅/콜백
        """
        self._find_kakao_window()  # 카카오톡 확인
        
        def filtered_callback(sender, element):
            # 카카오톡 내부 이벤트만 처리
            if self._is_kakao_element(element):
                self.logger.info(
                    f"[FOCUS] {element.ControlTypeName} | "
                    f"Name: '{element.Name}' | "
                    f"Class: {element.ClassName}"
                )
                if callback:
                    callback(element)
            # else: 카카오톡 외부 이벤트는 무시
        
        # 이벤트 핸들러 등록
        # ...
        pass
    
    def start_structure_monitor(
        self,
        scope: Optional[auto.Control] = None,
        callback: Optional[Callable] = None
    ):
        """
        카카오톡 내 구조 변경 이벤트 모니터링
        
        Args:
            scope: 모니터링 범위 (None이면 카카오톡 전체)
                   ※ 반드시 카카오톡 창 내부 요소여야 함
        
        목적:
        - 새 메시지 도착 이벤트 수신 가능 여부 확인
        - 채팅 목록 업데이트 감지
        """
        kakao = self._find_kakao_window()
        
        if scope is None:
            monitor_scope = kakao
        else:
            if not self._is_kakao_element(scope):
                raise ValueError(
                    "scope는 카카오톡 창 내부 요소여야 합니다."
                )
            monitor_scope = scope
        
        # 이벤트 핸들러 등록
        # ...
        pass
    
    def stop_all(self):
        """모든 이벤트 모니터링 중지"""
        pass
    
    def get_event_log(self) -> list:
        """수신된 카카오톡 이벤트 로그 반환"""
        pass
    
    def analyze_event_timing(self) -> dict:
        """
        카카오톡 이벤트 타이밍 분석
        
        Returns:
            {
                'focus_events': {'count': N, 'avg_interval_ms': M},
                'structure_events': {...},
                'missed_events': [...]  # 예상되었지만 수신 안 된 이벤트
            }
        """
        pass
```

---

### 2.3 프로파일러 개선

#### 현재 구현 확인 항목

```
□ UIAProfiler 클래스 존재하는가?
□ @profile 데코레이터 사용 가능한가?
□ 컨텍스트 매니저(with profiler.measure()) 지원하는가?
□ 로그 파일 자동 생성되는가?
□ SLOW 태그로 100ms 초과 작업 경고하는가?
□ 리포트 생성 기능 있는가?
```

#### 추가 필요 기능 검토

| 기능 | 필요성 | 설명 |
|------|--------|------|
| 호출 스택 추적 | 높음 | 느린 작업이 어디서 호출되었는지 |
| 메모리 프로파일링 | 중간 | 메모리 누수 감지 |
| 실시간 대시보드 | 낮음 | 터미널 기반 실시간 모니터링 |
| 비교 리포트 | 높음 | 개선 전/후 비교 |

#### 개선 구현 가이드

```python
# utils/profiler.py 확장

class UIAProfiler:
    # ... 기존 코드 ...
    
    def generate_comparison_report(
        self,
        baseline_log: Path,
        current_log: Path
    ) -> str:
        """
        개선 전/후 비교 리포트 생성
        
        목적:
        - 최적화 효과 정량적 측정
        - 성능 저하 항목 빠르게 식별
        
        출력:
        - 개선된 항목 (시간 단축)
        - 저하된 항목 (시간 증가)
        - 동일한 항목
        """
        pass
    
    def export_for_analysis(self, output_path: Path):
        """
        분석용 데이터 내보내기 (CSV/JSON)
        
        목적:
        - 외부 도구(Excel, Python 스크립트)에서 분석
        - 장기 트렌드 추적
        """
        pass
```

---

### 2.4 로그 분석 도구

#### 필수 기능

| 기능 | 설명 | 활용 시나리오 |
|------|------|---------------|
| 병목 Top N | 가장 느린 작업 N개 추출 | 최적화 우선순위 결정 |
| 빈 항목 통계 | 빈 ListItem 비율 계산 | 가상 스크롤 영향 파악 |
| 재시도 통계 | 재시도 횟수/성공률 | 메뉴 탐색 안정성 평가 |
| 시간대별 분석 | 시간에 따른 성능 변화 | 메모리 누수 징후 감지 |
| 필터링 검색 | 특정 조건 로그 추출 | 특정 기능 집중 분석 |

#### 검토 항목

```
□ 로그 분석 스크립트가 존재하는가?
□ CLI로 실행 가능한가?
□ 분석 결과를 파일로 저장하는가?
□ 마크다운 리포트 생성하는가?
```

#### 신규 구현이 필요한 경우

```python
# scripts/analyze_profile.py (신규)

"""
프로파일 로그 분석 도구

목적:
- 프로파일러 로그를 자동 분석
- 병목 지점 자동 식별
- 마크다운 리포트 생성

실행:
    python scripts/analyze_profile.py [로그파일경로]
    python scripts/analyze_profile.py --latest  # 최신 로그
    python scripts/analyze_profile.py --compare base.log new.log
"""

import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
from collections import defaultdict

class ProfileAnalyzer:
    """프로파일 로그 분석기"""
    
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.entries = self._parse_log()
    
    def _parse_log(self) -> List[dict]:
        """로그 파일 파싱"""
        pass
    
    def get_slowest_operations(self, n: int = 10) -> List[dict]:
        """
        가장 느린 작업 Top N
        
        Returns:
            [{'operation': '...', 'avg_ms': N, 'max_ms': M, 'count': K}, ...]
        """
        pass
    
    def get_empty_item_stats(self) -> dict:
        """
        빈 항목 통계
        
        Returns:
            {
                'chat_list': {'total': N, 'empty': M, 'ratio': P%},
                'message_list': {...}
            }
        """
        pass
    
    def get_retry_stats(self) -> dict:
        """
        재시도 통계
        
        Returns:
            {
                'context_menu': {
                    'total_attempts': N,
                    'success_rate': P%,
                    'avg_retries': M,
                    'max_retries': K
                }
            }
        """
        pass
    
    def get_timeline_analysis(self, bucket_minutes: int = 5) -> List[dict]:
        """
        시간대별 성능 분석
        
        Returns:
            [{'time': '10:00-10:05', 'avg_ms': N, 'slow_count': M}, ...]
        """
        pass
    
    def generate_report(self, output_path: Optional[Path] = None) -> str:
        """
        마크다운 리포트 생성
        
        Returns:
            마크다운 형식 리포트 문자열
        """
        report = f"""# 프로파일 분석 리포트

## 분석 정보
- 로그 파일: {self.log_path.name}
- 분석 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- 총 로그 수: {len(self.entries)}

## 병목 지점 Top 10
{self._format_slowest_table()}

## 빈 항목 통계
{self._format_empty_stats()}

## 재시도 통계
{self._format_retry_stats()}

## 시간대별 성능
{self._format_timeline()}

## 개선 제안
{self._generate_suggestions()}
"""
        if output_path:
            output_path.write_text(report, encoding='utf-8')
        return report


def main():
    parser = argparse.ArgumentParser(description='프로파일 로그 분석')
    parser.add_argument('log_path', nargs='?', help='로그 파일 경로')
    parser.add_argument('--latest', action='store_true', help='최신 로그 분석')
    parser.add_argument('--compare', nargs=2, help='두 로그 비교')
    parser.add_argument('--output', '-o', help='리포트 출력 경로')
    args = parser.parse_args()
    
    # ... 실행 로직 ...


if __name__ == '__main__':
    main()
```

---

## Phase 3: 신규 도구 필요성 판단

Phase 1, 2 결과를 바탕으로 다음 표를 작성하라:

| 도구 | 기존 구현 | 개선 필요 | 신규 개발 필요 | 우선순위 |
|------|----------|----------|---------------|----------|
| UIA 트리 탐색 | □ 있음/없음 | □ 예/아니오 | □ 예/아니오 | |
| UIA 이벤트 수신 | □ | □ | □ | |
| 프로파일러 | □ | □ | □ | |
| 로그 분석 | □ | □ | □ | |

### 신규 개발 결정 기준

**반드시 개발해야 하는 경우:**
- 기존에 없고, 없으면 분석이 불가능한 경우
- 수동 작업으로 대체하면 30분 이상 걸리는 경우

**개발하지 않아도 되는 경우:**
- 기존 도구로 90% 이상 커버 가능
- 일회성 분석이고 수동 작업으로 10분 이내 가능

---

## Phase 4: 도구 개발 실행

신규 개발이 결정된 도구에 대해:

1. **목적 및 필요성 문서화**
   - 왜 이 도구가 필요한가?
   - 없으면 어떤 문제가 있는가?
   - 기존 도구로 대체할 수 없는 이유

2. **인터페이스 설계**
   - CLI 명령어
   - 함수 시그니처
   - 입출력 형식

3. **구현**
   - 코드 작성
   - 테스트

4. **문서화**
   - README 또는 docstring
   - 사용 예시

---

## 최종 산출물

1. **도구 현황 보고서** (`docs/TOOLS_STATUS.md`)
   - 기존 도구 목록
   - 개선 항목
   - 신규 개발 항목

2. **신규/개선 도구 코드**
   - `utils/uia_inspector.py` (필요시)
   - `utils/uia_events.py` (필요시)
   - `scripts/analyze_profile.py` (필요시)

3. **도구 사용 가이드** (`docs/TOOLS_GUIDE.md`)
   - 각 도구별 실행 방법
   - 활용 시나리오
   - 출력 해석 방법

---

## 참고: 기존 프로젝트 구조 (예상)

```
kakaotalk-a11y-client/
├── src/
│   └── kakaotalk_a11y_client/
│       ├── main.py
│       ├── core/
│       ├── navigation/
│       ├── actions/
│       └── utils/
│           ├── profiler.py      # 기존 프로파일러
│           ├── uia_utils.py     # UIA 유틸리티
│           └── ...
├── scripts/                     # 분석 스크립트 (있을 수도)
├── docs/                        # 문서
└── tests/
```

---

## 주의사항

1. **기존 코드 존중**: 이미 잘 동작하는 코드는 건드리지 말 것
2. **점진적 추가**: 한 번에 많이 바꾸지 말고 하나씩 추가
3. **프로파일러 활용**: 새 도구도 프로파일러와 연동하여 성능 측정
4. **로깅 일관성**: 기존 로깅 포맷과 일관되게 유지
