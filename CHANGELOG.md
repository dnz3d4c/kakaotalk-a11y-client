# Changelog

모든 주요 변경사항을 기록합니다. [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/) 형식을 따릅니다.

버전 체계는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

## [0.2.0-beta] - 2026-01-01

### Added
- wxPython 기반 GUI 및 시스템 트레이 아이콘
- 핫키 커스터마이징 UI (설정 다이얼로그)
- 메시지 자동 읽기 (UIA 이벤트 기반)
- 설정 저장/로드 (`~/.kakaotalk_a11y/settings.json`)
- PyInstaller 빌드 지원
- 디버그 도구 (프로파일러, 이벤트 모니터, UIA 트리 덤프)

### Changed
- 백그라운드 실행 (콘솔 창 제거)
- 콘솔 모드는 디버그 모드에서만 사용 가능
- 단축키 변경 시 음성 안내 추가

## [0.1.0] - 초기 버전

### Added
- 이모지 스캔 및 클릭 (OpenCV 템플릿 매칭)
- 키보드 단축키 (Ctrl+Shift+E 등)
- 스크린 리더 음성 출력 (NVDA 호환)
