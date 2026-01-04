# Changelog

모든 주요 변경사항을 기록합니다. [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/) 형식을 따릅니다.

버전 체계는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

## [Unreleased]

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
