# AI 도구 활용 및 저작권 조사 보고서

## 개요

이 문서는 kakaotalk-a11y-client 프로젝트의 AI 도구 활용 방식과 관련 저작권/라이선스 조사 결과를 기록합니다.

---

## 1. 개발 방식

### AI Assisted 개발

이 프로젝트는 **AI Assisted** 방식으로 개발되었다:

| 역할 | 담당 | 비고 |
|------|------|------|
| 문제 정의 | 인간 | 시각장애인 접근성 요구사항 |
| 아키텍처 설계 | 인간 | 기술 방향 결정 |
| **코드 작성** | **AI** | **전체 구현 (Claude Code)** |
| 코드 검토 | 인간 | 품질 확인 |
| 테스트 | 인간 | NVDA 스크린 리더 실사용 환경 |
| 문서 작성 | 협업 | 인간 + AI |

### 사용 도구

- **Claude Code** (Anthropic): 코드 생성, 리팩토링, 디버깅 지원
- 커밋 메시지에 AI 기여 표기: `Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>`

---

## 2. 저작권 분석

### 2.1 법적 배경

#### 미국 (USCO 2025년 보고서)

미국 저작권청은 2025년 1월 "Copyright and Artificial Intelligence, Part 2" 보고서에서:

- AI 단독 생성물은 저작권 보호 대상 아님
- 인간이 "충분한 표현적 요소"를 결정한 경우 저작권 인정 가능
- 단순 프롬프트 입력만으로는 저작권 주장 불가

#### 한국 저작권법

- 저작권법 제2조: 저작물은 "인간의 사상 또는 감정을 표현한 창작물"
- AI 자체는 저작자 지위 불인정
- 인간의 창작적 기여가 있는 경우 해당 부분 보호 가능

#### 주요 판례: Thaler v. Perlmutter (2025)

- AI를 유일한 저작자로 저작권 등록 시도 → 거부
- D.C. 순회항소법원 만장일치: "저작자는 인간이어야 함"
- 단, AI가 "보조적 역할"을 한 저작물의 저작권 가능성은 열어둠

### 2.2 이 프로젝트의 법적 지위

이 프로젝트는 저작권 주장이 가능하다고 판단합니다.

근거:
1. 인간(기획자)의 창작적 기여가 명확히 존재
   - 접근성 문제 정의
   - 기술적 접근 방식 결정 (이미지 인식 vs UIA)
   - 도메인 지식 (스크린 리더 사용자 관점)
2. AI는 도구로 활용됨 (AI Assisted)
3. 모든 코드는 인간의 검토와 수정을 거침

---

## 3. AI 회사 정책

### Anthropic (Claude)

Anthropic Terms of Service:

> "You own all Output. Anthropic does not claim any ownership rights in your Output."

- 생성물 소유권: 사용자
- 상업적 사용: 허용
- 오픈소스 배포: 허용

### OpenAI (참고)

> "OpenAI hereby assigns to you all its right, title and interest in and to Output."

동일하게 사용자에게 권리 양도.

---

## 4. 오픈소스 라이선스 분석

### GitHub Copilot 소송 (2022~)

- 2022년 11월 집단소송 제기
- 22개 청구 중 대부분 기각, 2개만 진행 중
- DMCA 청구 기각: AI 생성 코드가 원본과 "동일"하지 않으면 위반 아님
- 2024년 10월 제9순회항소법원 항소 진행 중

### 라이선스별 위험도

| 라이선스 | AI 코드 적용 위험 | 이유 |
|----------|-------------------|------|
| MIT | 낮음 | 귀속 표시만 요구 |
| Apache 2.0 | 낮음 | 특허 보호 포함 |
| GPL | 높음 | 학습 데이터 문제 시 Copyleft 적용 가능성 |

### 이 프로젝트의 라이선스 선택: MIT

**선택 이유:**
1. 간결하고 이해하기 쉬움
2. 최대 확산 가능 (제약 최소)
3. 접근성 도구 표준
4. 기업(카카오 등) 참여 허용

---

## 5. 투명성 공개

### 공개 이유

1. **윤리적 의무**: 접근성 프로젝트의 사회적 책임
2. **재현 가능성**: 다른 개발자가 유사 프로젝트 시작 시 참고
3. **신뢰 구축**: AI 활용 방식을 숨기면 나중에 문제될 소지
4. **법적 안전**: 추후 분쟁 시 방어 논거

### 공개 방식

- 커밋 메시지: `Co-Authored-By` 트레일러 사용
- README.md: AI 활용 안내 섹션
- 이 문서: 상세 조사 보고서

---

## 6. 정리

이 프로젝트는 접근성 개선이라는 사회적 가치를 위해 인간과 AI가 협업하여 개발되었습니다. 인간이 기획과 설계, 검토를 담당하고, AI가 코드 작성을 보조하는 방식으로 각자의 강점을 발휘했습니다.

---

## 참고 자료

### 법률
- U.S. Copyright Office, "Copyright and Artificial Intelligence, Part 2" (2025.01)
- Thaler v. Perlmutter, D.C. Circuit (2025.03)
- 한국 저작권법 제2조

### 오픈소스
- OSI Open Source AI Definition (OSAID) 1.0 (2024.10)
- GitHub Copilot Litigation (2022~)
- https://githubcopilotlitigation.com/

### AI 정책
- Anthropic Terms of Service
- OpenAI Terms of Use

---

*이 문서는 법적 조언이 아닙니다. 법적 문제는 전문 변호사 상담을 권장합니다.*

*최종 업데이트: 2025년 1월*
