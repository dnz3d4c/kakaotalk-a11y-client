"""
카카오톡 접근성 클라이언트 성능 벤치마크
- 적용 전/후 비교용
- 동일 조건에서 반복 측정

사용법:
    측정: uv run python tests/performance_benchmark.py measure <label>
    비교: uv run python tests/performance_benchmark.py compare <baseline.json> <after.json>
"""
import time
import json
import statistics
from datetime import datetime
from pathlib import Path
import sys

import uiautomation as auto

# 측정 결과 저장 경로
RESULTS_DIR = Path.home() / '.kakaotalk_a11y' / 'benchmarks'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


class PerformanceBenchmark:
    """성능 벤치마크 클래스"""

    def __init__(self, label: str = "baseline"):
        self.label = label
        self.results = {
            "label": label,
            "timestamp": datetime.now().isoformat(),
            "metrics": {}
        }

    def measure(self, name: str, func, iterations: int = 10):
        """함수 실행 시간 측정 (여러 번 반복)"""
        times = []
        errors = 0

        for i in range(iterations):
            try:
                start = time.perf_counter()
                func()
                elapsed_ms = (time.perf_counter() - start) * 1000
                times.append(elapsed_ms)
            except Exception as e:
                errors += 1
                print(f"  {name} 측정 {i+1} 실패: {e}")

        if times:
            self.results["metrics"][name] = {
                "iterations": iterations,
                "errors": errors,
                "min_ms": round(min(times), 2),
                "max_ms": round(max(times), 2),
                "avg_ms": round(statistics.mean(times), 2),
                "median_ms": round(statistics.median(times), 2),
                "stdev_ms": round(statistics.stdev(times), 2) if len(times) > 1 else 0,
            }
            print(f"  {name}: avg={self.results['metrics'][name]['avg_ms']}ms, errors={errors}")
        else:
            self.results["metrics"][name] = {"error": "all iterations failed"}
            print(f"  {name}: 모든 측정 실패")

    def save(self):
        """결과 JSON 저장"""
        filename = f"{self.label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = RESULTS_DIR / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"\n결과 저장: {filepath}")
        return filepath


def find_kakao_window():
    """카카오톡 메인 창 찾기"""
    # 창 이름이 '카카오톡' 또는 'KakaoTalk Dialog'일 수 있음
    kakao = auto.WindowControl(searchDepth=1, Name='카카오톡')
    if not kakao.Exists(maxSearchSeconds=0.5):
        kakao = auto.WindowControl(searchDepth=1, Name='KakaoTalk Dialog')
    return kakao


def run_benchmark(label: str = "baseline"):
    """전체 벤치마크 실행"""
    print(f"\n{'='*50}")
    print(f"성능 벤치마크: {label}")
    print(f"{'='*50}\n")

    bench = PerformanceBenchmark(label)

    # 카카오톡 창 확인
    kakao = find_kakao_window()
    if not kakao.Exists(maxSearchSeconds=3):
        print("카카오톡이 실행되지 않았습니다")
        return None

    print("카카오톡 발견, 측정 시작...\n")

    # 1. 창 찾기 성능
    print("[1/6] 창 찾기")
    bench.measure("find_main_window",
        lambda: find_kakao_window().Exists(maxSearchSeconds=0.1),
        iterations=20)

    # 2. 포커스 컨트롤 가져오기
    print("[2/6] 포커스 컨트롤")
    bench.measure("get_focused_control",
        lambda: auto.GetFocusedControl(),
        iterations=20)

    # 3. 리스트 자식 요소 가져오기
    print("[3/6] 리스트 자식 요소")
    def get_list_children():
        list_ctrl = kakao.ListControl(searchDepth=6)
        if list_ctrl.Exists(maxSearchSeconds=0.5):
            return list_ctrl.GetChildren()
        return []
    bench.measure("get_list_children", get_list_children, iterations=10)

    # 4. 리스트 자식 필터링 (빈 항목 제외)
    print("[4/6] 리스트 필터링")
    def filter_list_children():
        list_ctrl = kakao.ListControl(searchDepth=6)
        if list_ctrl.Exists(maxSearchSeconds=0.5):
            children = list_ctrl.GetChildren()
            return [c for c in children if c.Name and c.Name.strip()]
        return []
    bench.measure("filter_list_children", filter_list_children, iterations=10)

    # 5. 깊은 탐색 (searchDepth=10)
    print("[5/6] 깊은 탐색")
    bench.measure("deep_search_depth10",
        lambda: kakao.ButtonControl(searchDepth=10, Name='전송').Exists(maxSearchSeconds=0.5),
        iterations=10)

    # 6. 트리 덤프 (depth=3)
    print("[6/6] 트리 덤프")
    def dump_tree_depth3():
        count = 0
        def count_elements(ctrl, depth=0):
            nonlocal count
            if depth > 3:
                return
            count += 1
            for child in ctrl.GetChildren():
                count_elements(child, depth + 1)
        count_elements(kakao)
        return count
    bench.measure("tree_dump_depth3", dump_tree_depth3, iterations=5)

    # 결과 저장
    filepath = bench.save()

    # 요약 출력
    print(f"\n{'='*50}")
    print("측정 요약")
    print(f"{'='*50}")
    for name, data in bench.results["metrics"].items():
        if "avg_ms" in data:
            print(f"  {name}: {data['avg_ms']}ms (+-{data['stdev_ms']})")

    return filepath


def compare_results(baseline_path: str, after_path: str):
    """두 결과 비교"""
    with open(baseline_path, 'r', encoding='utf-8') as f:
        baseline = json.load(f)
    with open(after_path, 'r', encoding='utf-8') as f:
        after = json.load(f)

    print(f"\n{'='*60}")
    print(f"성능 비교: {baseline['label']} vs {after['label']}")
    print(f"{'='*60}\n")

    print(f"{'측정 항목':<30} {'Before':>10} {'After':>10} {'변화':>10} {'판정':>8}")
    print("-" * 70)

    improvements = 0
    regressions = 0

    for name in baseline["metrics"]:
        if name not in after["metrics"]:
            continue

        b = baseline["metrics"][name]
        a = after["metrics"][name]

        if "avg_ms" not in b or "avg_ms" not in a:
            continue

        b_avg = b["avg_ms"]
        a_avg = a["avg_ms"]

        if b_avg > 0:
            change_pct = ((a_avg - b_avg) / b_avg) * 100
        else:
            change_pct = 0

        if change_pct < -5:
            verdict = "개선"
            improvements += 1
        elif change_pct > 5:
            verdict = "저하"
            regressions += 1
        else:
            verdict = "유지"

        print(f"{name:<30} {b_avg:>8.1f}ms {a_avg:>8.1f}ms {change_pct:>+8.1f}% {verdict:>8}")

    print("-" * 70)
    print(f"총평: 개선 {improvements}개, 저하 {regressions}개")

    return {
        "improvements": improvements,
        "regressions": regressions,
    }


def list_benchmarks():
    """저장된 벤치마크 목록 출력"""
    print(f"\n저장된 벤치마크 ({RESULTS_DIR}):\n")
    files = sorted(RESULTS_DIR.glob("*.json"))
    if not files:
        print("  (없음)")
        return
    for f in files:
        print(f"  {f.name}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법:")
        print("  측정: python performance_benchmark.py measure <label>")
        print("  비교: python performance_benchmark.py compare <baseline.json> <after.json>")
        print("  목록: python performance_benchmark.py list")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "measure":
        label = sys.argv[2] if len(sys.argv) > 2 else "baseline"
        run_benchmark(label)

    elif cmd == "compare":
        if len(sys.argv) < 4:
            print("비교할 두 파일 경로 필요")
            sys.exit(1)
        compare_results(sys.argv[2], sys.argv[3])

    elif cmd == "list":
        list_benchmarks()

    else:
        print(f"알 수 없는 명령: {cmd}")
        sys.exit(1)
