# 카카오톡 접근성 클라이언트

## 왜 만들었나
- NVDA 스크린 리더에서는 카카오톡의 실시간 채팅 읽기 기능을 사용할 수 없었어요.
- 카카오톡 PC 버전은 말풍선의 공감 이모지를 클릭할 수 없어 이모지에 공감하려면 모바일 버전을 사용해야 했어요.

### 프로젝트 계기
"채팅방 말풍선의 공감 이모지를 어떻게 클릭할 수 있을까?"라는 물음에서 시작됐어요. AI와 여러 시도 끝에 단서를 찾았고, 프로토타입이 잘 동작했어요.

이렇게 까다로운 작업을 해결할 수 있다면 다른 것도 가능하지 않을까? 그렇게 하나씩 기능을 추가하다 보니 카카오톡 PC 버전을 NVDA 스크린 리더에서 사용할 수 있게 되었어요. 사실 제가 원하는 목표를 이룬 샘이죠.

## 주요 기능
PC 카카오톡을 공식 지원하는 스크린 리더처럼
- 친구 목록, 채팅 목록을 탐색할 수 있어요.
- 친구, 채팅방 항목의 콘텍스트 메뉴를 지원해 친구의 프로필을 확인하고, 채팅방을 고정하거나 해제할 수 있어요.
- 채팅방에서 실시간으로 메시지를 읽고, 답장할 수 있어요.
- 말풍선의 일부 공감 이모지를 클릭할 수 있어요(추후 개선 예정)
- SAPI5 음성이 설치돼 있다면 스크린 리더와 독립적으로 이 모든 기능을 이용할 수 있어요

### 개인정보 보호
- 100% 본인 PC에서 실행되며 외부로 정보를 전송하지 않아요. 공감 이모지는 샘플 데이터를 사용해 처리됩니다.

## 시작하기

1. [릴리즈 페이지](https://github.com/dnz3d4c/kakaotalk-a11y-client/releases)에서 최신 버전 다운로드
2. 압축 풀고 `KakaotalkA11y.exe` 실행

자세한 설치/사용법은 [사용자 가이드](docs/USER_GUIDE.md)를 참조하세요.

## 희망사항
카카오톡 팀에서 접근성을 개선해 주셔서 이 프로젝트가 더이상 사용되지 않길 바라봅니다. 그때까지 스크린 리더 사용자분들이 불편 없이 쓸 수 있도록 계속 개선해 나갈게요. 저에게 이미 이런 프로젝트가 있어요. <https://github.com/dnz3d4c/potplayerNVDAAddon>

## 피드백
버그 리포트나 제안은 [이슈 페이지](https://github.com/dnz3d4c/kakaotalk-a11y-client/issues)에 남겨주세요.

## 문서

| 문서 | 설명 |
|------|------|
| [USER_GUIDE.md](docs/USER_GUIDE.md) | 사용자 가이드 - 설치, 단축키, 기능별 사용법 |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 모듈 구조, 컴포넌트, 데이터 흐름 |
| [KAKAO_UIA_QUIRKS.md](docs/KAKAO_UIA_QUIRKS.md) | 카카오톡 UIA 특이사항 |

### 개발

| 문서 | 설명 |
|------|------|
| [BUILD.md](docs/BUILD.md) | 빌드/실행 방법, 의존성 |
| [TOOLS_GUIDE.md](docs/TOOLS_GUIDE.md) | 디버그 도구, 단축키 |
| [CLAUDE.md](.claude/CLAUDE.md) | 프로젝트에 사용한 Claude Code 작업 지침 |
| [AI_DEVELOPMENT.md](docs/AI_DEVELOPMENT.md) | AI 개발 방식 |

### 참고 문서

| 문서 | 설명 |
|------|------|
| [UIA_GUIDE.md](docs/UIA_GUIDE.md) | Windows UIA 가이드 |
| [NVDA_UIA_PATTERNS.md](docs/NVDA_UIA_PATTERNS.md) | NVDA UIA 패턴 |
| [PROFILER_ANALYSIS.md](docs/PROFILER_ANALYSIS.md) | 프로파일러 측정 결과 |
| [AI 프롬프트 예제](docs/) | 바이브 코딩 프롬프트 원본 (카카오톡_*.md) |

---

## 라이선스

이 프로젝트는 MIT License 하에 배포됩니다. 자유롭게 사용, 수정, 배포할 수 있어요.

## AI 도구 활용

이 프로젝트는 바이브 코딩 방식으로 개발되었습니다. 인간이 문제를 정의하고 기술 방향을 결정하면, AI(Claude Code)가 코드를 작성하고, 인간이 실사용으로 검증했습니다.

상세: [AI 개발 보고서](docs/AI_DEVELOPMENT.md)
