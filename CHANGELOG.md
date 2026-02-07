# Changelog

모든 주요 변경사항을 기록합니다. [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/) 형식을 따릅니다.

버전 체계는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

## [Unreleased]

## [0.7.0] - 2026-02-07

포커스 모니터링 고도화, 메시지 액션 시스템 추가, 코드 정리 대규모 리팩터링.

### Added
- C키 메시지 복사 기능 (message_actions 패키지)
- ElementSelected 이벤트 리스너로 포커스 추적 강화
- --debug 시 이벤트 모니터 자동 시작
- 커밋 후 릴리즈 체크 자동화 훅

### Improved
- EVA_* 접두사 기반 카카오톡 창 인식 (NVDA isGoodUIAWindow 패턴)
- hwnd 판별 캐시로 이벤트 필터링 최적화
- 컨테이너 포커스 이벤트 필터링 (ListControl, MenuControl)
- 공유 캐시 락 추가 및 스레드 안전성 개선
- 덤프 파일 자동 정리 및 중복 방지
- 메시지 리스트 존재 확인 타임아웃 축소 및 빈 리스트 오탐 수정
- 복사 피드백 메시지 명확화

### Changed
- 포커스 이벤트 디스패치를 테이블 기반으로 전환
- 싱글톤 패턴 통일
- HotkeyPanel 데이터 기반 일반화 (DebugHotkeyPanel 삭제)
- 하드코딩된 상수 config.py로 통합
- 디버그 초기화 로직 debug_setup.py로 분리

### Fixed
- is_focus_in_message_list import 누락
- 메시지 보기 창 첫 열림 시 포커스 이동 안 되던 문제

### Removed
- MSAA fallback (UIA 전용)
- V키 메시지 리뷰 기능
- SpeakCallback 인프라 (speak() 직접 사용)
- 미사용 함수/모듈 정리 (beep.py, uia_reliability.py, uia_workarounds.py 등)

## [0.6.1] - 2026-01-27

이번 버전은 업데이터 안정성을 개선했습니다.

### Fixed
- 트레이 메뉴 "업데이트 확인" 버튼 작동 안 하던 문제
- 자동 업데이트 설치 스크립트 파일 복사 실패 문제

### Improved
- 업데이트 프로세스 전반 로깅 강화 (디버깅 용이)

## [0.6.0] - 2026-01-26

메뉴 탐색 안정성 향상 및 포커스 튀는 문제 완화.

### Changed
- 메뉴 항목 읽기를 NVDA에 위임 (중복 발화 방지)
- 탭(친구/채팅 등) 읽기를 NVDA에 위임
- 메뉴 로직을 menu_handler.py로 통합 (5개 파일에서 1개로)

### Improved
- 광고 웹뷰로 포커스 튀는 문제 완화
- 컨텍스트 메뉴 첫 항목 읽기 안정성 개선
- 방향키 탐색 응답 속도 향상
- hwnd 캐싱으로 포그라운드 폴백 강화
- 메뉴 탐색 안정화 및 시간 기반 지연 제거
- UIA 연결 복구 기능 활성화

### Fixed
- 점자 디스플레이에 내용 표시 안 되던 문제
- 탐색 반복 읽기, 메뉴 첫 항목, 채팅방 진입 무한 루프
- 컨텍스트 메뉴 사용 시 포커스 문제
- 개발 환경에서 업데이트 확인 버튼 작동하지 않던 문제

### Removed
- mouse_hook.py (우클릭 차단 기능 제거)
- 메인 창 전환 시 강제 포커스 이동

## [0.5.1] - 2026-01-16

탐색/읽기 안정성 개선 및 성능 최적화.

### Fixed
- 친구/채팅방/메시지 목록 탐색 시 읽기 실패
- 동일 내용 메시지 연속 시 발화 누락
- 컨텍스트 메뉴 사용 중 새 메시지 누락

### Improved
- FocusChanged 이벤트 핸들러 성능 최적화
- 채팅방 전환 응답 속도 개선
- 스레드 안전성 개선
- 로그 시스템 개선 (로테이션, 타임스탬프)

## [0.5.0] - 2026-01-07

점자 디스플레이 지원 및 디버그 도구 개선.

### Added
- 점자 디스플레이 출력 지원 (accessible_output2 output() 메서드 사용)
- 디버그 단축키 커스터마이징 UI (디버그 모드 설정 창 → "디버그 단축키" 탭)
- 디버그 상태 확인 단축키 (Ctrl+Shift+S)

### Improved
- 디버그 도구 음성 피드백 개선: 덤프/프로파일 완료 시 파일명 발화
- 릴리즈 시 client 저장소에도 태그 자동 생성

## [0.4.0] - 2026-01-05

포커스 모니터링 방식 전면 개편 (폴링 → 이벤트).

### Changed
- 포커스 변경 감지를 폴링에서 FocusChanged 이벤트로 전환
- HybridFocusMonitor → FocusMonitor 클래스 단순화
- 폴링 폴백 코드 제거 (이벤트 전용)

### Added
- 채팅방 진입 시 현재 포커스 메시지 자동 읽기
- NVDA 이벤트 핸들링 패턴 문서 (docs/NVDA_EVENT_PATTERNS.md)
- 테스트용 비프음 유틸리티 (utils/beep.py)

### Fixed
- 비카카오톡 창 (작업표시줄 등) 읽히던 문제

## [0.3.4.1] - 2026-01-05

### Fixed
- dist 빌드 시 화면읽기/UIAutomation 오류 (email 모듈 누락, accessible_output2 hiddenimports 추가)

## [0.3.4] - 2026-01-05

메시지 읽기 안정성 개선 및 디버그 도구 추가.

### Added
- 디버그 모드 테스트 단축키 (Ctrl+Shift+1: 탐색, Ctrl+Shift+2: 메시지)
- IUIAutomation6 CoalesceEvents 지원 (Windows 10 1809+)
- README에 감사의 말 섹션 추가

### Changed
- 새 메시지 발화 끊김 방지 (이벤트 디바운싱 + interrupt=False)
- 포커스 모니터 TRACE 로그 중복 제거

## [0.3.1] - 2026-01-04

### Changed
- 포커스 모니터 COM 호출 60-65% 감소 (CacheRequest 도입)
- 포커스 중복 감지 정확도 개선 (CompareElements API)
- 메뉴 읽기 코드 단순화

## [0.3.0] - 2026-01-04

### Added
- 탭 메뉴 읽기 기능

### Changed
- main.py 책임 분리 (ModeManager, FocusMonitorService)
- 메뉴 모드 CPU 스파이크 완화
- 스마트 캐시 및 메뉴 감지 안정화

### Fixed
- 음성 발화 끊김 문제

## [0.2.3] - 2026-01-03

### Changed
- 업데이트 체크 간격 제한 (4시간 이내 재시작 시 API 호출 스킵)

## [0.2.2] - 2026-01-02

### Added
- 자동 업데이터 (GitHub 릴리스 기반)
- 비메시지 항목 우클릭 차단

### Changed
- TTS 엔진 변경 (pyttsx3 → accessible_output2)

### Fixed
- 팝업메뉴 CPU 스파이크
- 탐색 시 음성 끊김

## [0.2.1] - 2026-01-02

### Added
- wxPython 기반 GUI 및 시스템 트레이 아이콘
- 설정 다이얼로그 (핫키 커스터마이징, 상태 표시, 정보 탭)
- 설정 저장/로드 (`~/.kakaotalk_a11y/settings.json`)
- 메시지 자동 읽기 (UIA StructureChanged 이벤트 기반)
- 단축키 변경 시 음성 안내
- 시작 시 UIA 사용 가능 여부 체크
- 이모지 이미지 패키지 포함
- PyInstaller 빌드 지원
- 디버그 도구 (프로파일러, 이벤트 모니터, UIA 트리 덤프)
- NVDA UIA 패턴 적용 (chat_room, context_menu)

### Changed
- 백그라운드 실행 (콘솔 창 제거)
- 콘솔 모드는 디버그 모드에서만 사용
- 핫키 패널 스크린 리더 친화적 UI로 개선
- 프로덕션 준비 - 코드 정리 및 의존성 최적화
- 미사용 코드 1,100줄 삭제

### Fixed
- 종료 시 음성 피드백이 들리지 않던 문제
- 포커스 모니터 COM 해제 및 핫키 오류 처리
- --debug CLI 옵션 사용 시 로그 파일 생성 안 되는 버그
- 키보드 입력 지연 및 탭 모드 안정성
- 컨텍스트 메뉴 버그

## [0.1.0] - 초기 버전

### Added
- 이모지 스캔 및 클릭 (OpenCV 템플릿 매칭)
- 키보드 단축키 (Ctrl+Shift+E 등)
- 스크린 리더 음성 출력 (NVDA 호환)
