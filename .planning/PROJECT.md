# News Briefing System (자동 뉴스 브리핑 시스템)

## What This Is

IT/반도체/AI 뉴스 소스에서 기사를 자동 수집하고, 소스별 키워드 필터링 후 지정 시간에 Claude API로 한줄 요약 브리핑을 생성하여 텔레그램으로 전달하는 시스템. 소규모 팀(2-5명)이 공유 설정으로 각자 1:1 텔레그램 봇을 통해 동일한 브리핑을 수신한다. 모든 설정은 텔레그램 봇 채팅으로 관리한다.

## Core Value

뉴스 소스에서 키워드 기반으로 필터링된 기사를 정해진 시간에 한줄 요약으로 받아볼 수 있어야 한다 — 수집부터 요약, 전달까지 완전 자동화.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] R1: 뉴스 소스 동적 관리 — 텔레그램 봇으로 뉴스 링크를 추가/삭제
- [ ] R2: 소스별 필터 키워드 — 각 뉴스 소스마다 별도의 필터 키워드 설정
- [ ] R3: 필터 키워드 동적 관리 — 필터 키워드를 텔레그램 봇으로 추가/삭제
- [ ] R4: 지정 링크에서만 파싱 — 사용자가 등록한 정확한 URL에서만 기사 파싱
- [ ] R5: 지정 시간 요약 알림 — 사용자가 지정한 시간에 요약 브리핑 텔레그램 전달
- [ ] R6: 알림 시간 동적 변경 — 요약 시간을 텔레그램 봇으로 변경
- [ ] R7: 요약 이후 기사 제외 — 한번 요약된 기사는 다음 요약에 미포함
- [ ] R8: 한줄 요약 포맷 — 기사당 [핵심키워드] + 한줄 요약 + 출처
- [ ] R9: MD 파일 저장 — 요약 결과를 briefings/ 폴더에 .md 파일로 저장
- [ ] R10: 텔레그램 봇 제어 — 모든 설정을 텔레그램 봇 채팅으로 수행
- [ ] R11: GCP 서버 상시 실행 — 34.172.56.22에 systemd 서비스로 상시 운영
- [ ] R12: 다중 사용자 전달 — 팀원 각자 1:1 봇으로 동일 브리핑 수신 (공유 설정)

### Out of Scope

- 사용자별 개별 소스/키워드 설정 — 팀 공유 설정으로 충분
- 실시간 채팅/알림 — 정기 브리핑만
- 웹 UI/대시보드 — 텔레그램 봇이 유일한 인터페이스
- 모바일 앱 — 텔레그램으로 대체
- OAuth/소셜 로그인 — 텔레그램 chat_id로 사용자 식별
- n8n 등 외부 자동화 도구 — 순수 Python 구현
- 다국어 요약 — 한국어 요약 기본 (영문 기사도 한국어로 요약)

## Context

- SOP v2.1 문서가 상세한 구현 가이드 역할 (DB 스키마, 봇 명령어, 프로젝트 구조 등 정의)
- IT/반도체/AI 뉴스 도메인 — 전자신문, 디일렉, Tom's Hardware, TrendForce 등이 주요 소스
- RSS 피드 + HTML 파싱 두 가지 수집 방식 (소스 타입 자동 감지)
- 범용 HTML 파서로 시작, 필요시 소스별 커스텀 파서 추가
- 13개 초기 소스가 SOP에 정의되어 있음 (Tier 1: RSS 4개, Tier 2: HTML 9개)
- 한국어/영문 뉴스 혼재 — 요약은 한국어로 통일
- 기존 코드 없음. 처음부터 새로 구현

## Constraints

- **Tech Stack**: Python 3.11+, SQLite, APScheduler, python-telegram-bot, feedparser, BeautifulSoup4, Anthropic Claude API — SOP에서 지정
- **Summarization Model**: claude-sonnet-4-20250514 — Anthropic Claude API
- **Server**: GCP 인스턴스 34.172.56.22, Ubuntu, systemd 서비스
- **Deployment**: rsync 기반 로컬→서버 배포 (deploy.sh)
- **DB**: SQLite 단일 파일 (data/news.db) — 경량 개인/소팀용
- **Interface**: 텔레그램 봇이 유일한 사용자 인터페이스
- **API Keys**: Anthropic API 토큰 보유, Telegram Bot Token은 추후 발급

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SQLite 사용 (PostgreSQL 아닌) | 소규모 팀, 단일 서버, 설치 불필요 | — Pending |
| 범용 HTML 파서 (소스별 전용 파서 아닌) | MVP 빠른 구현, 필요시 커스텀 추가 | — Pending |
| 텔레그램 전용 (Slack/Email 아닌) | 팀 전원 텔레그램 사용, 단일 채널 집중 | — Pending |
| 공유 설정 + 다중 chat_id | 팀원 모두 같은 관심사, 설정 중복 불필요 | — Pending |
| SOP 기반이되 개선 허용 | 핵심 요구사항 준수하되 구현 품질 향상 가능 | — Pending |
| systemd 서비스 운영 | 상시 실행, 자동 재시작, 서버 리부팅 시 자동 시작 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-26 after initialization*
