# 스크립트 가이드

개발/디버깅용 스크립트 모음.

## 실행 방법

```powershell
uv run python scripts/스크립트명.py
```

## 스크립트 목록

### 디버깅/분석

| 파일 | 용도 | 실행 예시 |
|------|------|----------|
| `dump_uia.py` | UIA 트리 덤프 | `uv run python scripts/dump_uia.py chat_list` |
| `dump_menu.py` | 컨텍스트 메뉴 구조 덤프 | `uv run python scripts/dump_menu.py` |
| `focus_monitor.py` | 실시간 포커스 변화 기록 | `uv run python scripts/focus_monitor.py` |
| `debug_tools.py` | 통합 디버그 도구 | `uv run python scripts/debug_tools.py --mode focus` |
| `analyze_profile.py` | 프로파일 로그 분석 | `uv run python scripts/analyze_profile.py` |

### GUI 테스트

| 파일 | 용도 | 실행 예시 |
|------|------|----------|
| `test_update_dialogs.py` | 업데이트 대화상자 테스트 | `uv run python scripts/test_update_dialogs.py` |
| `test_tray_menu.py` | 트레이 메뉴 테스트 | `uv run python scripts/test_tray_menu.py` |

### 기능 테스트

| 파일 | 용도 | 실행 예시 |
|------|------|----------|
| `test_chat_navigate.py` | 채팅방 메시지 탐색 테스트 | `uv run python scripts/test_chat_navigate.py` |
| `test_message_monitor.py` | 새 메시지 감지 테스트 | `uv run python scripts/test_message_monitor.py` |
| `test_menu_sim.py` | 채팅 탭 우클릭 메뉴 테스트 | `uv run python scripts/test_menu_sim.py` |
| `test_uia_events.py` | UIA 이벤트 발생 확인 | `uv run python scripts/test_uia_events.py` |

### 테스트 자동화

| 파일 | 용도 | 실행 예시 |
|------|------|----------|
| `run_related_tests.py` | 변경 파일 기반 테스트 실행 | `uv run python scripts/run_related_tests.py --staged` |
| `test_mapping.py` | 소스→테스트 매핑 정의 | (직접 실행 또는 import) |
| `_common.py` | 스크립트 공통 유틸리티 | (import용) |

### 빌드/배포

| 파일 | 용도 | 실행 예시 |
|------|------|----------|
| `build.py` | PyInstaller 빌드 | `uv run python scripts/build.py` |
| `sync_release.py` | release 저장소 동기화 | `uv run python scripts/sync_release.py` |
| `add_license_headers.py` | SPDX 헤더 일괄 추가 | `uv run python scripts/add_license_headers.py` |

## 상세 설명

### dump_uia.py

UIA 트리 덤프 통합 도구. 여러 서브커맨드 지원.

```powershell
# 채팅 목록 덤프 (3초 대기)
uv run python scripts/dump_uia.py chat_list

# 메뉴 덤프 (7초 대기, 메뉴 먼저 열어둘 것)
uv run python scripts/dump_uia.py menu

# 현재 포커스된 요소 덤프
uv run python scripts/dump_uia.py focus

# 현재 트리를 JSON 스냅샷으로 저장
uv run python scripts/dump_uia.py snapshot

# 두 스냅샷 비교
uv run python scripts/dump_uia.py compare snapshot1.json snapshot2.json
```

### debug_tools.py

여러 디버그 모드 통합.

```powershell
# 포커스 추적
uv run python scripts/debug_tools.py --mode focus

# 네비게이션 디버그
uv run python scripts/debug_tools.py --mode nav

# 키보드 네비게이션 디버그
uv run python scripts/debug_tools.py --mode keyboard
```

### analyze_profile.py

프로파일러 로그 분석.

```powershell
# 전체 분석
uv run python scripts/analyze_profile.py

# 특정 작업 필터
uv run python scripts/analyze_profile.py --filter context_menu

# 시간대 필터
uv run python scripts/analyze_profile.py --time 10:00-10:30
```

## 시나리오별 권장 스크립트

| 상황 | 스크립트 |
|------|----------|
| 업데이트 대화상자 테스트 | `test_update_dialogs.py` |
| 트레이 메뉴 테스트 | `test_tray_menu.py` |
| 변경 코드 관련 테스트 | `run_related_tests.py --staged` |
| UI 구조 파악 | `dump_uia.py chat_list` 또는 `dump_uia.py focus` |
| 메뉴 구조 분석 | `dump_menu.py` (메뉴 열어둔 상태에서) |
| 포커스 이동 추적 | `focus_monitor.py` 또는 `debug_tools.py --mode focus` |
| 메시지 탐색 검증 | `test_chat_navigate.py` |
| 새 메시지 감지 테스트 | `test_message_monitor.py` |
| UIA 이벤트 확인 | `test_uia_events.py` |
| 성능 분석 | `analyze_profile.py` |
| 배포 준비 | `build.py` -> `sync_release.py --release` |

## 주의사항

- 대부분의 스크립트는 카카오톡 실행 상태 필요
- `Ctrl+C`로 종료
- 덤프/로그 파일은 현재 디렉토리 또는 `logs/`에 저장
