# Rust GUI 전환 프로젝트 - Claude Code 프롬프트

## 프로젝트 개요

카카오톡 접근성 클라이언트의 GUI 레이어를 Python(wxPython)에서 Rust(egui + eframe)로 전환하려 합니다.

### 현재 아키텍처
```
[Python 단일 앱]
├── GUI: wxPython (~30MB)
├── 카카오톡 UIA 모니터링: uiautomation
├── 음성 출력: accessible_output2
├── 화면 감지: opencv-python-headless
├── 자동화: PyAutoGUI
└── 배포: Nuitka 컴파일 → ~100MB exe
```

### 목표 아키텍처
```
[Rust GUI 프로세스] ←──IPC──→ [Python 백엔드 프로세스]
      │                              │
      ├── egui + eframe              ├── 카카오톡 UIA 모니터링
      ├── AccessKit (접근성)          ├── accessible_output2
      ├── tray-icon (시스템 트레이)    ├── opencv-python-headless
      └── 설정 UI                     └── PyAutoGUI
      
예상 용량: ~55MB (Rust ~5MB + Python ~50MB)
```

---

## 핵심 요구사항

### 1. 접근성 (최우선)
- **스크린 리더 호환 필수**: NVDA, 센스리더, Narrator
- Windows UIA/MSAA API 지원
- AccessKit이 eframe에 기본 활성화되어 있음을 확인할 것
- 모든 UI 요소에 적절한 접근성 레이블 제공

### 2. GUI 기능 범위
현재 wxPython GUI가 담당하는 기능:
- 시스템 트레이 아이콘 + 컨텍스트 메뉴
- 설정 창 (단축키 변경, 옵션 토글 등)
- 정보/도움말 창
- 업데이터 UI
- 알림 (선택적)

### 3. IPC 통신
- Rust GUI ↔ Python 백엔드 간 통신
- 예상 통신 빈도: 낮음 (사용자 액션 시에만)
- 고려할 방식: JSON-RPC over socket, named pipe, 공유 메모리

### 4. 배포
- 단일 실행 파일 또는 최소한의 파일 구성
- Windows 10/11 지원
- 안티바이러스 오탐 최소화

---

## 사전 조사 요청

리팩토링 전에 다음 항목들을 철저히 조사하고 검증해주세요.

### 1. egui + eframe 접근성 검증

```
조사 항목:
□ AccessKit이 eframe에서 기본 활성화되는지 확인
□ 지원되는 위젯별 접근성 속성 (버튼, 체크박스, 텍스트 입력 등)
□ 커스텀 위젯의 접근성 레이블 설정 방법
□ NVDA/Narrator로 실제 테스트한 사례/영상 찾기
□ 알려진 접근성 이슈나 제한사항
□ AccessKit 버전 호환성 (egui/eframe 버전별)
```

참고 자료:
- https://github.com/emilk/egui
- https://github.com/AccessKit/accesskit
- https://github.com/emilk/egui/issues/167 (접근성 논의)
- https://github.com/emilk/egui/pull/2294 (AccessKit 통합 PR)

### 2. 시스템 트레이 구현

```
조사 항목:
□ tray-icon 크레이트 현황 및 안정성
□ Windows에서 트레이 아이콘 + 메뉴 구현 방법
□ 트레이 메뉴의 접근성 (OS가 처리하는지 확인)
□ eframe과 tray-icon 통합 예제
□ 창 숨기기/보이기 연동
```

참고 크레이트:
- tray-icon: https://github.com/tauri-apps/tray-icon
- 대안: winit 직접 사용, windows-rs

### 3. Rust-Python IPC 방식 비교

```
조사 항목:
□ 각 방식의 장단점 및 레이턴시
□ Windows에서의 안정성
□ 에러 핸들링 및 재연결 로직
□ 직렬화 포맷 (JSON, MessagePack, bincode 등)
□ 비동기 이벤트 처리 방법
```

비교 대상:
| 방식 | 크레이트 | 특징 |
|------|----------|------|
| TCP socket | std::net | 단순, 범용 |
| Named pipe | windows-rs | Windows 네이티브, 빠름 |
| JSON-RPC | jsonrpc-core | 표준화된 프로토콜 |
| gRPC | tonic | 타입 안전, 무거움 |
| 공유 메모리 | shared_memory | 최고 성능, 복잡 |

### 4. 빌드 및 배포

```
조사 항목:
□ Rust 바이너리 + Python(PyInstaller/Nuitka) 통합 방법
□ 단일 exe로 묶을 수 있는지 (Rust가 Python 런타임 포함)
□ 또는 두 개의 exe를 하나의 폴더로 배포하는 방식
□ cargo build --release 최적화 옵션
□ 바이너리 크기 최소화 (strip, LTO, opt-level 등)
□ Windows 코드 서명 및 안티바이러스 대응
```

### 5. 프로세스 생명주기 관리

```
조사 항목:
□ Rust GUI가 Python 백엔드를 spawn/관리하는 방법
□ Python 프로세스 크래시 시 복구 전략
□ 정상 종료 시퀀스 (graceful shutdown)
□ 단일 인스턴스 보장 (mutex 등)
□ Windows 서비스로 등록 필요 여부
```

---

## 검증 체크리스트

### Phase 1: PoC (개념 증명)

```
□ Rust 개발 환경 설정 (rustup, cargo)
□ egui + eframe "Hello World" 창 띄우기
□ NVDA로 기본 위젯 접근성 테스트
  - 버튼 읽히는지
  - 체크박스 상태 읽히는지
  - 텍스트 입력 가능한지
□ tray-icon으로 시스템 트레이 구현
□ 트레이 메뉴 접근성 확인
□ 간단한 TCP 소켓 통신 테스트 (Rust ↔ Python)
```

### Phase 2: 프로토타입

```
□ 실제 설정 UI 구현 (현재 wxPython UI 기준)
□ 설정 파일 읽기/쓰기 (JSON/TOML)
□ IPC 프로토콜 설계 및 구현
□ Python 백엔드와 기본 통신 성공
□ 프로세스 관리 로직 구현
□ 통합 테스트 (GUI 조작 → Python 로직 실행)
```

### Phase 3: 완성 및 배포

```
□ 모든 UI 기능 포팅 완료
□ 전체 접근성 테스트 (NVDA, 센스리더)
□ 에러 핸들링 및 로깅
□ 배포 패키지 구성
□ 설치/업데이트 메커니즘
□ 실사용자 베타 테스트
```

---

## 코드 구조 제안

### Rust 프로젝트 구조

```
kakao-a11y-gui/
├── Cargo.toml
├── src/
│   ├── main.rs           # 진입점
│   ├── app.rs            # eframe::App 구현
│   ├── ui/
│   │   ├── mod.rs
│   │   ├── settings.rs   # 설정 창
│   │   ├── about.rs      # 정보 창
│   │   └── tray.rs       # 트레이 메뉴
│   ├── ipc/
│   │   ├── mod.rs
│   │   ├── client.rs     # Python 백엔드 통신
│   │   └── protocol.rs   # 메시지 정의
│   ├── config/
│   │   ├── mod.rs
│   │   └── settings.rs   # 설정 구조체
│   └── process/
│       ├── mod.rs
│       └── backend.rs    # Python 프로세스 관리
├── assets/
│   └── icon.ico
└── build.rs              # 빌드 스크립트 (아이콘 임베딩 등)
```

### Cargo.toml 예시

```toml
[package]
name = "kakao-a11y-gui"
version = "0.1.0"
edition = "2021"

[dependencies]
eframe = { version = "0.29", default-features = true }
# AccessKit은 eframe에 기본 포함

tray-icon = "0.14"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
tokio = { version = "1", features = ["net", "io-util", "sync", "rt-multi-thread"] }
tracing = "0.1"
tracing-subscriber = "0.3"
directories = "5.0"  # 설정 파일 경로

[target.'cfg(windows)'.dependencies]
windows = { version = "0.58", features = ["Win32_System_Threading"] }

[profile.release]
opt-level = "z"     # 크기 최적화
lto = true          # Link Time Optimization
strip = true        # 심볼 제거
panic = "abort"     # 패닉 시 즉시 종료
codegen-units = 1   # 단일 코드 생성 단위
```

---

## IPC 프로토콜 초안

### 메시지 포맷 (JSON)

```json
// GUI → Python: 요청
{
  "id": 1,
  "method": "set_hotkey",
  "params": {
    "action": "read_message",
    "key": "ctrl+shift+m"
  }
}

// Python → GUI: 응답
{
  "id": 1,
  "result": { "success": true }
}

// Python → GUI: 이벤트 (알림 등, 선택적)
{
  "event": "new_message",
  "data": {
    "sender": "홍길동",
    "preview": "안녕하세요..."
  }
}
```

### 예상 메서드

```
GUI → Python:
- get_settings: 현재 설정 조회
- set_settings: 설정 변경
- set_hotkey: 단축키 변경
- get_status: 백엔드 상태 조회
- restart_monitor: 모니터링 재시작
- quit: 종료

Python → GUI (이벤트):
- status_changed: 상태 변경 알림
- error: 에러 발생 알림
- new_message: 새 메시지 알림 (선택적)
```

---

## 주의사항

### 1. 접근성 우선
```
이 프로젝트는 시각장애인용 접근성 도구입니다.
접근성이 보장되지 않으면 의미가 없습니다.

- 매 단계마다 NVDA로 테스트
- 접근성 레이블 누락 없이
- 키보드만으로 모든 기능 사용 가능해야 함
- 포커스 순서 논리적으로
```

### 2. 점진적 마이그레이션
```
- 기존 Python GUI를 당장 삭제하지 말 것
- Rust GUI가 완전히 검증될 때까지 병행
- 롤백 가능한 구조 유지
```

### 3. 에러 핸들링
```
- IPC 연결 실패 시 사용자에게 명확한 안내
- Python 백엔드 크래시 시 자동 재시작 또는 알림
- 모든 에러는 로그 파일에 기록
```

### 4. 테스트 환경
```
- Windows 10, Windows 11
- NVDA 최신 버전
- 센스리더 (가능하면)
- 다양한 DPI 스케일링 (100%, 125%, 150%)
```

---

## 첫 번째 작업 요청

위의 사전 조사 항목들을 먼저 수행해주세요.

1. egui + eframe + AccessKit 조합의 접근성 지원 현황을 상세히 조사
2. tray-icon 크레이트의 Windows 지원 상태 확인
3. Rust-Python IPC 방식 중 이 프로젝트에 가장 적합한 것 추천
4. 예상되는 기술적 리스크와 대응 방안 정리

조사 결과를 바탕으로 진행 여부를 최종 결정하겠습니다.
조사 중 접근성 관련 심각한 제한사항이 발견되면 즉시 알려주세요.

---

## 참고: 현재 Python GUI 기능 목록

(실제 프로젝트의 기능 목록을 여기에 추가해주세요)

```
예시:
- 시스템 트레이 아이콘
- 트레이 메뉴: 설정, 정보, 종료
- 설정 창
  - 일반 탭: 시작 시 실행, 알림 설정
  - 단축키 탭: 각 기능별 단축키 변경
  - 고급 탭: 로그 레벨, 디버그 모드
- 정보 창: 버전, 라이선스, 제작자
- 업데이트 확인 및 다운로드
```

---

## 질문 있으면 언제든 물어봐

이 프로젝트에 대한 추가 컨텍스트가 필요하면 질문해주세요.
특히:
- 현재 wxPython 코드 구조
- 설정 파일 포맷
- 기존 단축키 처리 방식
- 기타 특수한 요구사항
