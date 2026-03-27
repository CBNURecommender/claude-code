# 자동 뉴스 브리핑 시스템 - 요구사항 정의서 (SOP) v2.1

> 문서 버전: v2.1
> 작성일: 2026-03-26
> 목적: Claude Code에서 본 문서를 기반으로 시스템을 구현한다
> 운영 서버: GCP 인스턴스 34.172.56.22

---

## 0. 핵심 요구사항 체크리스트

> 아래 항목은 반드시 충족해야 하는 필수 요구사항이다. 구현 시 하나라도 빠지면 안 된다.

| # | 요구사항 | 상세 |
|---|---------|------|
| R1 | **뉴스 소스 동적 관리** | 텔레그램 봇으로 뉴스 링크를 추가/삭제할 수 있어야 함 |
| R2 | **소스별 필터 키워드** | 각 뉴스 소스마다 별도의 필터 키워드를 설정할 수 있어야 함 |
| R3 | **필터 키워드 동적 관리** | 필터 키워드를 텔레그램 봇으로 추가/삭제할 수 있어야 함 |
| R4 | **지정 링크에서만 파싱** | 사이트 홈페이지가 아닌, 사용자가 등록한 정확한 URL에서만 기사를 파싱해야 함 |
| R5 | **지정 시간 요약 알림** | 사용자가 지정한 시간에 요약 브리핑이 텔레그램으로 전달되어야 함 |
| R6 | **알림 시간 동적 변경** | 요약 시간을 텔레그램 봇으로 언제든 변경할 수 있어야 함 |
| R7 | **요약 이후 기사 제외** | 한번 요약된 기사는 다음 요약에 포함되지 않아야 함 |
| R8 | **한줄 요약 포맷** | 기사당 핵심키워드 + 제목 기반 한줄 요약 형태여야 함 |
| R9 | **MD 파일 저장** | 요약 결과를 지정 폴더에 .md 파일로 저장해야 함 |
| R10 | **텔레그램 봇 제어** | 위 모든 설정을 텔레그램 봇 채팅으로 수행할 수 있어야 함 |
| R11 | **GCP 서버 상시 실행** | GCP 인스턴스(34.172.56.22)에 배포하여 systemd 서비스로 상시 실행. 로컬 개발 → 서버 배포 워크플로우 포함 |

---

## 1. 프로젝트 개요

### 1-1. 목적
IT/반도체/AI 관련 뉴스 소스에서 기사를 자동 수집하고, 소스별 키워드 필터링 후 지정 시간에 한줄 요약 브리핑을 텔레그램으로 전달하는 시스템. 모든 설정은 텔레그램 봇 채팅으로 관리한다.

### 1-2. 기술 스택
- **언어**: Python 3.11+
- **수집**: feedparser, requests, beautifulsoup4, playwright (필요 시)
- **DB**: SQLite
- **스케줄러**: APScheduler
- **요약 AI**: Anthropic Claude API (claude-sonnet-4-20250514)
- **봇/전달**: python-telegram-bot
- **설정 저장**: SQLite (YAML 파일이 아닌 DB로 동적 관리)
- **운영 서버**: GCP 인스턴스 (34.172.56.22), Ubuntu, systemd 서비스
- **배포**: rsync 또는 scp로 로컬 → 서버 전송

---

## 2. 프로젝트 구조

```
news-briefing/
├── src/
│   ├── __init__.py
│   ├── main.py                  # 엔트리포인트: 봇 + 스케줄러 동시 실행
│   ├── bot/
│   │   ├── __init__.py
│   │   └── telegram_bot.py      # 텔레그램 봇 명령어 핸들러
│   ├── collector/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseCollector 추상 클래스
│   │   ├── rss_collector.py     # RSS 피드 수집기
│   │   └── html_collector.py    # HTML 파싱 수집기 (범용)
│   ├── storage/
│   │   ├── __init__.py
│   │   └── database.py          # DB 연결 및 모든 CRUD
│   ├── filter/
│   │   ├── __init__.py
│   │   └── keyword_filter.py    # 소스별 키워드 매칭
│   ├── summarizer/
│   │   ├── __init__.py
│   │   └── briefing.py          # Claude API 한줄 요약 생성
│   ├── delivery/
│   │   ├── __init__.py
│   │   └── telegram_sender.py   # 텔레그램 메시지 전달
│   └── utils/
│       ├── __init__.py
│       └── logger.py
├── data/
│   └── news.db                  # SQLite DB
├── briefings/                   # 요약 결과 .md 파일 저장 폴더
│   └── (자동생성: 2026-03-26_08-00_morning.md 등)
├── deploy/
│   ├── deploy.sh                # 로컬→서버 배포 스크립트
│   └── news-briefing.service    # systemd 서비스 파일
├── logs/
│   └── .gitkeep
├── .env.example                 # 환경변수 템플릿
├── .env                         # 실제 환경변수 (gitignore)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 3. DB 스키마 (모든 설정은 DB에서 관리)

### 3-1. `sources` 테이블 — 뉴스 소스 관리 [R1, R4]

```sql
CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,                    -- 소스 표시명 (사용자 지정)
    url         TEXT UNIQUE NOT NULL,             -- 파싱 대상 정확한 URL
    type        TEXT DEFAULT 'auto',              -- 'rss' | 'html' | 'auto' (자동 감지)
    language    TEXT DEFAULT 'auto',              -- 'ko' | 'en' | 'auto'
    enabled     BOOLEAN DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

- `url`은 사용자가 등록한 정확한 링크. 이 URL에서만 기사를 파싱한다.
- 홈페이지 URL이 아닌 섹션/카테고리 페이지 URL을 그대로 사용.

### 3-2. `source_keywords` 테이블 — 소스별 필터 키워드 [R2, R3]

```sql
CREATE TABLE IF NOT EXISTS source_keywords (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   INTEGER NOT NULL,                 -- sources.id 참조
    keyword     TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
    UNIQUE(source_id, keyword)                    -- 같은 소스에 같은 키워드 중복 방지
);
```

- 소스별로 0~N개의 키워드를 등록할 수 있음
- **키워드가 0개인 소스**: 해당 소스의 모든 기사를 수집 (필터 없이 전체 수집)
- **키워드가 1개 이상인 소스**: 제목에 키워드가 1개 이상 포함된 기사만 수집
- 키워드 매칭: 대소문자 무시, 부분 문자열 매칭

### 3-3. `global_keywords` 테이블 — 전체 소스 공통 필터 키워드 (선택)

```sql
CREATE TABLE IF NOT EXISTS global_keywords (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword     TEXT UNIQUE NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

- 모든 소스에 공통으로 적용되는 키워드 (선택 기능)
- 소스별 키워드와 OR 조건으로 동작

### 3-4. `articles` 테이블 — 수집된 기사 [R7]

```sql
CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    source_id       INTEGER NOT NULL,
    source_name     TEXT NOT NULL,
    summary         TEXT,                              -- 원문 요약 (있으면)
    published_at    DATETIME,
    collected_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    matched_keywords TEXT,                             -- JSON: ["HBM", "삼성전자"]
    -- 브리핑 상태
    is_briefed      BOOLEAN DEFAULT 0,                 -- 한번 요약되면 1, 다시 요약 안 함
    briefing_id     INTEGER,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE INDEX idx_articles_briefed ON articles(is_briefed);
CREATE INDEX idx_articles_source ON articles(source_id);
```

### 3-5. `briefings` 테이블 — 브리핑 히스토리

```sql
CREATE TABLE IF NOT EXISTS briefings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    article_count   INTEGER,
    content_md      TEXT,                              -- 생성된 브리핑 전문 (Markdown)
    file_path       TEXT,                              -- 저장된 .md 파일 경로
    delivered       BOOLEAN DEFAULT 0,
    delivered_at    DATETIME
);
```

### 3-6. `settings` 테이블 — 동적 설정 [R5, R6]

```sql
CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

-- 초기 데이터
INSERT OR IGNORE INTO settings (key, value) VALUES
    ('briefing_times', '["08:00","18:00"]'),           -- JSON 배열, KST
    ('timezone', 'Asia/Seoul'),
    ('briefing_folder', 'briefings'),                  -- .md 파일 저장 폴더
    ('collection_interval_minutes', '30'),             -- 수집 주기
    ('summary_language', 'ko'),
    ('telegram_chat_id', '');                          -- 봇이 자동 설정
```

---

## 4. 텔레그램 봇 명령어 [R10]

### 4-1. 명령어 전체 목록

```
=== 소스 관리 ===
/add_source <이름> <URL>          — 뉴스 소스 추가
/remove_source <이름>             — 뉴스 소스 삭제
/list_sources                     — 등록된 소스 목록 조회
/enable_source <이름>             — 소스 활성화
/disable_source <이름>            — 소스 비활성화

=== 소스별 필터 키워드 관리 ===
/add_keyword <소스이름> <키워드>   — 특정 소스에 필터 키워드 추가
/remove_keyword <소스이름> <키워드> — 특정 소스의 필터 키워드 삭제
/list_keywords <소스이름>          — 특정 소스의 키워드 목록 조회
/clear_keywords <소스이름>         — 특정 소스의 모든 키워드 삭제 (전체 수집 모드로 전환)

=== 전체 공통 키워드 관리 ===
/add_global <키워드>              — 전체 공통 키워드 추가
/remove_global <키워드>           — 전체 공통 키워드 삭제
/list_globals                     — 전체 공통 키워드 조회

=== 브리핑 시간 관리 ===
/set_times <HH:MM> [HH:MM] ...   — 브리핑 시간 설정 (여러 개 가능)
/list_times                       — 현재 브리핑 시간 조회

=== 즉시 실행 ===
/collect                          — 지금 즉시 전체 수집 실행
/briefing                         — 지금 즉시 브리핑 생성 및 전달
/status                           — 현재 상태 (소스 수, 미브리핑 기사 수, 다음 브리핑 시간)

=== 도움말 ===
/help                             — 명령어 안내
```

### 4-2. 명령어 상세 동작

#### `/add_source <이름> <URL>`
```
입력: /add_source 전자신문 https://www.etnews.com/news/section.html?id1=06
응답: ✅ 소스 추가 완료
      이름: 전자신문
      URL: https://www.etnews.com/news/section.html?id1=06
      타입: auto (자동감지)
      필터 키워드: 없음 (모든 기사 수집)
      
      💡 필터 키워드를 설정하려면:
      /add_keyword 전자신문 HBM
```

#### `/remove_source <이름>`
```
입력: /remove_source 전자신문
응답: ⚠️ '전자신문' 소스를 삭제하시겠습니까?
      등록된 키워드 3개도 함께 삭제됩니다.
      삭제하려면 /confirm_delete 를 입력하세요.
```
- 삭제 전 확인 단계 필요 (ON DELETE CASCADE로 키워드도 함께 삭제)

#### `/list_sources`
```
응답: 📋 등록된 뉴스 소스 (5개)

      1. ✅ 전자신문
         URL: https://www.etnews.com/news/section.html?id1=06
         키워드: HBM, 삼성전자, TSMC (3개)
         
      2. ✅ Tom's Hardware
         URL: https://www.tomshardware.com/feeds.xml
         키워드: 없음 (전체 수집)
         
      3. ❌ 디일렉 (비활성)
         URL: https://www.thelec.kr/news/articleList.html?...
         키워드: 파운드리, 메모리 (2개)
```

#### `/add_keyword <소스이름> <키워드>`
```
입력: /add_keyword 전자신문 HBM
응답: ✅ '전자신문'에 키워드 추가: HBM
      현재 키워드: HBM, 삼성전자 (2개)
```

#### `/remove_keyword <소스이름> <키워드>`
```
입력: /remove_keyword 전자신문 HBM
응답: ✅ '전자신문'에서 키워드 삭제: HBM
      현재 키워드: 삼성전자 (1개)
```

#### `/set_times <HH:MM> [HH:MM] ...`
```
입력: /set_times 08:00 12:00 18:00
응답: ✅ 브리핑 시간 설정 완료
      - 08:00 KST
      - 12:00 KST
      - 18:00 KST
      
      다음 브리핑: 오늘 12:00
```
- 스케줄러를 즉시 갱신해야 함 (재시작 없이)

#### `/status`
```
응답: 📊 시스템 상태

      소스: 5개 활성 / 2개 비활성
      미브리핑 기사: 23건
      마지막 수집: 10분 전
      마지막 브리핑: 오늘 08:00 (15건 요약)
      다음 브리핑: 오늘 18:00
      
      브리핑 저장 폴더: briefings/
      저장된 브리핑: 47개
```

#### `/briefing` (즉시 실행)
```
응답: 📰 브리핑 생성 중... (미브리핑 기사 23건)

      (AI 요약 후)
      
      📰 뉴스 브리핑 | 2026-03-26 14:35
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      
      [HBM] 삼성전자 HBM4 양산 라인 가동 본격화 — 전자신문
      [TSMC] TSMC 2nm 수율 90% 돌파, 양산 앞당겨 — TrendForce
      [AI서버] 엔비디아 B300 출하량 예상 상회 — Tom's Hardware
      [메모리] SK하이닉스 HBM3E 12단 샘플 출하 — 디일렉
      ...
      
      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      총 23건 | 저장: briefings/2026-03-26_14-35.md
```

---

## 5. 수집 프로세스 [R4]

### 5-1. 수집 흐름

```
1. DB에서 enabled=1인 소스 전체 조회
2. 각 소스에 대해:
   a. source.url을 fetch (RSS이면 feedparser, HTML이면 requests+BS4)
   b. 기사 목록 파싱 (title, url, published_at)
   c. 해당 소스의 source_keywords 조회
   d. 키워드 필터링:
      - 키워드 0개 → 모든 기사 통과
      - 키워드 1개+ → 제목에 키워드 1개 이상 포함된 기사만 통과
      - global_keywords도 OR 조건으로 함께 매칭
   e. 통과한 기사에 대해:
      - URL로 중복 체크
      - 신규이면 articles 테이블에 INSERT
3. 수집 결과 로그 출력
```

### 5-2. 소스 타입 자동 감지 (`type: auto`)

소스 추가 시 URL을 분석하여 자동으로 타입을 결정한다:

```python
def detect_source_type(url: str) -> str:
    """
    1. URL에 /feed, /rss, .xml, /atom이 포함되어 있으면 → 'rss'
    2. URL을 fetch하여 Content-Type이 application/rss+xml 또는 
       application/atom+xml이면 → 'rss'
    3. 그 외 → 'html'
    """
```

### 5-3. HTML 파싱 (범용)

소스별 전용 파서를 만드는 대신, **범용 HTML 파서**를 사용한다:

```python
def parse_html_articles(html: str, base_url: str) -> list[Article]:
    """
    범용 파싱 전략:
    1. <a> 태그 중 기사 링크로 보이는 것을 추출
       - href에 /news/, /article/, /story/ 등 기사 패턴 포함
       - 또는 날짜 패턴 포함 (/2026/, /20260326/ 등)
    2. 각 <a>의 텍스트를 title로 사용
    3. 상대경로는 base_url 기준으로 절대경로 변환
    4. 중복 URL 제거
    5. 네비게이션/푸터 링크 필터링 (짧은 텍스트, 반복 패턴 등)
    """
```

- 범용 파서로 커버 안 되는 소스가 있으면, 해당 소스를 위한 커스텀 파서를 추후 추가
- 최초 MVP에서는 범용 파서 하나로 시작

### 5-4. 키워드 매칭 상세 [R2]

```python
def matches_keywords(title: str, keywords: list[str]) -> tuple[bool, list[str]]:
    """
    Args:
        title: 기사 제목
        keywords: 해당 소스의 필터 키워드 목록
    Returns:
        (매칭 여부, 매칭된 키워드 리스트)
    
    규칙:
    - keywords가 빈 리스트 → (True, []) 무조건 통과
    - 대소문자 무시
    - 부분 문자열 매칭 (title.lower()에 keyword.lower()가 포함되면 매칭)
    - 1개 이상 매칭되면 True
    """
```

---

## 6. 요약 브리핑 생성 [R7, R8, R9]

### 6-1. 브리핑 생성 프로세스

```
1. DB에서 is_briefed=0인 기사 전체 조회 (수집 시각 순 정렬)
2. 기사가 0건이면 "새로운 기사가 없습니다" 메시지만 전달
3. 기사가 1건 이상이면:
   a. Claude API 호출하여 한줄 요약 생성
   b. 요약 결과를 Markdown 포맷으로 구성
   c. briefings/ 폴더에 .md 파일 저장 [R9]
   d. 텔레그램으로 전달
   e. 해당 기사들의 is_briefed=1 업데이트 [R7]
   f. briefings 테이블에 기록
```

### 6-2. Claude API 요약 프롬프트

```
시스템 프롬프트:
당신은 IT/반도체 뉴스 요약 전문가입니다.
각 기사를 아래 형식으로 한줄 요약하세요:
[핵심키워드] 한줄 요약 — 출처
핵심키워드는 기사의 가장 중요한 주제어 1~2개를 대괄호 안에 넣습니다.
한줄 요약은 20~40자 이내로 핵심만 담습니다.
출처는 뉴스 소스 이름입니다.

유저 프롬프트:
아래 기사들을 각각 한줄 요약해주세요.

1. [전자신문] 삼성전자, HBM4 양산 본격화...4분기 매출 반영
   URL: https://...
2. [TrendForce] TSMC Reports 2nm Yield Breakthrough
   URL: https://...
3. ...

응답 예시:
[HBM] 삼성전자 HBM4 양산 라인 본격 가동, 4분기부터 매출 기여 — 전자신문
[파운드리] TSMC 2nm 수율 90% 돌파하며 양산 일정 앞당겨 — TrendForce
```

### 6-3. 요약 결과 포맷 (Markdown) [R8, R9]

```markdown
# 뉴스 브리핑 | 2026-03-26 18:00

> 이전 브리핑: 2026-03-26 08:00 | 대상 기사: 23건

---

[HBM] 삼성전자 HBM4 양산 라인 본격 가동, 4분기 매출 기여 — 전자신문
[파운드리] TSMC 2nm 수율 90% 돌파하며 양산 일정 앞당겨 — TrendForce
[AI서버] 엔비디아 B300 출하량 당초 예상 20% 상회 — Tom's Hardware
[메모리] SK하이닉스 HBM3E 12단 적층 샘플 주요 고객사 출하 — 디일렉
[데이터센터] AWS 오하이오 신규 데이터센터 10조원 투자 발표 — CNBC
[OLED] LG디스플레이 차량용 OLED 수주 잇따라 확보 — 한국경제

---

총 23건 | 생성: 2026-03-26 18:00 KST
```

### 6-4. MD 파일 저장 [R9]

```python
# 파일명 규칙: YYYY-MM-DD_HH-MM.md
# 저장 경로: {briefing_folder}/2026-03-26_18-00.md

import os
from datetime import datetime

def save_briefing_md(content: str, folder: str) -> str:
    os.makedirs(folder, exist_ok=True)
    now = datetime.now()
    filename = now.strftime("%Y-%m-%d_%H-%M") + ".md"
    filepath = os.path.join(folder, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath
```

---

## 7. 텔레그램 전달 포맷

### 7-1. 정기 브리핑 메시지

```
📰 뉴스 브리핑 | 2026-03-26 18:00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[HBM] 삼성전자 HBM4 양산 라인 본격 가동, 4분기 매출 기여 — 전자신문
[파운드리] TSMC 2nm 수율 90% 돌파하며 양산 일정 앞당겨 — TrendForce
[AI서버] 엔비디아 B300 출하량 당초 예상 20% 상회 — Tom's Hardware
...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
총 23건 | 저장: 2026-03-26_18-00.md
```

- 4096자 초과 시 여러 메시지로 분할 전송
- 기사가 0건이면: `📭 새로운 기사가 없습니다. (마지막 수집: 10분 전)`

### 7-2. 새로운 기사 없을 때

브리핑 시간이 되었지만 미브리핑 기사가 0건이면:
- 텔레그램: 간단한 알림만 전달 (`📭 새로운 기사가 없습니다`)
- .md 파일: 생성하지 않음
- briefings 테이블: 기록하지 않음

---

## 8. 스케줄러 [R5, R6]

### 8-1. 실행 구조

```python
# main.py
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

async def main():
    # 1. DB 초기화
    db.init()
    
    # 2. 스케줄러 생성
    scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
    
    # 3. 수집 작업 등록 (고정 간격)
    interval = int(db.get_setting('collection_interval_minutes'))
    scheduler.add_job(job_collect, 'interval', minutes=interval, id='collector')
    
    # 4. 브리핑 작업 등록 (DB에서 시간 로드)
    update_briefing_schedule(scheduler)
    
    # 5. 텔레그램 봇 시작
    app = Application.builder().token(BOT_TOKEN).build()
    register_handlers(app)  # 모든 명령어 핸들러 등록
    
    # 6. 스케줄러에 대한 참조를 봇에 전달 (시간 변경 시 스케줄 갱신용)
    app.bot_data['scheduler'] = scheduler
    
    scheduler.start()
    await app.run_polling()
```

### 8-2. 브리핑 시간 동적 변경 [R6]

```python
def update_briefing_schedule(scheduler):
    """
    DB의 settings에서 briefing_times를 읽어 스케줄러의 브리핑 작업을 갱신한다.
    /set_times 명령어 처리 후에도 이 함수를 호출해야 한다.
    """
    # 기존 브리핑 작업 모두 제거
    for job in scheduler.get_jobs():
        if job.id.startswith('briefing_'):
            job.remove()
    
    # DB에서 시간 로드
    times = json.loads(db.get_setting('briefing_times'))  # ["08:00", "18:00"]
    
    # 새 작업 등록
    for t in times:
        hour, minute = map(int, t.split(':'))
        scheduler.add_job(
            job_briefing,
            'cron',
            hour=hour,
            minute=minute,
            id=f'briefing_{t}',
            replace_existing=True
        )
```

---

## 9. 데이터 흐름 전체도

```
[텔레그램 봇] ←→ [DB: sources, source_keywords, settings]
      │
      │  /add_source, /add_keyword, /set_times 등
      │
      ▼
[스케줄러]
      │
      ├── 매 N분 ──→ [Collector]
      │                  │
      │                  ├── 소스별 URL fetch
      │                  ├── 기사 파싱
      │                  ├── 소스별 키워드 필터링
      │                  └── 신규 기사 DB 저장 (is_briefed=0)
      │
      └── 지정 시간 ──→ [Summarizer]
                           │
                           ├── is_briefed=0 기사 조회
                           ├── Claude API 한줄 요약
                           ├── .md 파일 저장 (briefings/ 폴더)
                           ├── 텔레그램 전달
                           └── is_briefed=1 업데이트
```

---

## 10. 구현 순서

### Phase 1: 기반 (먼저)
1. 프로젝트 구조 생성
2. requirements.txt 작성 및 의존성 설치
3. .env 파일 생성
4. DB 초기화 (모든 테이블 생성)
5. database.py CRUD 함수 구현

### Phase 2: 수집기
6. BaseCollector 구현
7. RSSCollector 구현 (feedparser)
8. HTMLCollector 범용 파서 구현 (requests + BS4)
9. 소스 타입 자동 감지 함수
10. 키워드 필터 구현

### Phase 3: 요약 & 저장
11. Claude API 연동 briefing.py
12. .md 파일 저장 로직
13. 텔레그램 메시지 전달

### Phase 4: 텔레그램 봇
14. 봇 기본 구조 (Application, handlers)
15. 소스 관리 명령어 (/add_source, /remove_source, /list_sources 등)
16. 키워드 관리 명령어 (/add_keyword, /remove_keyword 등)
17. 시간 관리 명령어 (/set_times, /list_times)
18. 즉시 실행 명령어 (/collect, /briefing, /status)
19. /help 명령어

### Phase 5: 통합 & 스케줄러
20. main.py에서 봇 + 스케줄러 통합 실행
21. 브리핑 시간 동적 갱신
22. 에러 핸들링 및 로깅

### Phase 6: 배포 [R11]
23. deploy/news-briefing.service 생성
24. deploy/deploy.sh 배포 스크립트 생성
25. .gitignore 생성
26. 로컬 테스트 완료 후 GCP 서버(34.172.56.22)로 배포
27. systemd 서비스 등록 및 상시 실행 확인

---

## 11. 에러 핸들링

- 개별 소스 수집 실패: 해당 소스만 SKIP, 로그 남기고 다음 소스 진행
- Claude API 실패: 3회 재시도 (30초 간격), 실패 시 원본 기사 제목 목록만 전달
- 텔레그램 전달 실패: 3회 재시도, 실패 시 .md 파일은 저장 (delivered=0)
- DB 오류: 로그 기록, 해당 작업 SKIP
- HTML 파싱 실패 (구조 변경 등): 로그 남기고 해당 소스 SKIP

---

## 12. 배포 및 운영 [R11]

### 12-1. 운영 환경

| 항목 | 값 |
|------|-----|
| 서버 | GCP 인스턴스 |
| IP | 34.172.56.22 |
| OS | Ubuntu (GCP 기본) |
| Python | 3.11+ |
| 서비스 관리 | systemd |
| 배포 경로 | `/home/jihoon/news-briefing/` |
| DB 경로 | `/home/jihoon/news-briefing/data/news.db` |
| 브리핑 저장 | `/home/jihoon/news-briefing/briefings/` |
| 로그 경로 | `/home/jihoon/news-briefing/logs/` |

### 12-2. systemd 서비스 파일

`deploy/news-briefing.service`:

```ini
[Unit]
Description=News Briefing Bot
After=network.target

[Service]
Type=simple
User=jihoon
WorkingDirectory=/home/jihoon/news-briefing
ExecStart=/home/jihoon/news-briefing/venv/bin/python -m src.main --daemon
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/home/jihoon/news-briefing/.env

# 로그
StandardOutput=append:/home/jihoon/news-briefing/logs/service.log
StandardError=append:/home/jihoon/news-briefing/logs/service-error.log

[Install]
WantedBy=multi-user.target
```

- `Restart=always`: 프로세스 비정상 종료 시 10초 후 자동 재시작
- `EnvironmentFile`: .env 파일에서 API 키 등 환경변수 로드
- 서버 재부팅 시에도 자동 시작 (`WantedBy=multi-user.target`)

### 12-3. 배포 스크립트

`deploy/deploy.sh`:

```bash
#!/bin/bash
set -e

# === 설정 ===
SERVER="jihoon@34.172.56.22"
REMOTE_DIR="/home/jihoon/news-briefing"
SERVICE_NAME="news-briefing"

echo "🚀 뉴스 브리핑 시스템 배포 시작"

# === 1. 파일 전송 (rsync) ===
echo "📦 파일 전송 중..."
rsync -avz --delete \
    --exclude '.env' \
    --exclude 'data/' \
    --exclude 'briefings/' \
    --exclude 'logs/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude 'venv/' \
    --exclude '.git/' \
    ./ ${SERVER}:${REMOTE_DIR}/

# === 2. 서버에서 설정 ===
echo "⚙️ 서버 설정 중..."
ssh ${SERVER} << 'EOF'
    cd /home/jihoon/news-briefing

    # 폴더 생성
    mkdir -p data briefings logs

    # 가상환경 생성 (없으면)
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        echo "✅ 가상환경 생성 완료"
    fi

    # 의존성 설치
    venv/bin/pip install -r requirements.txt --quiet
    echo "✅ 의존성 설치 완료"

    # .env 파일 확인
    if [ ! -f ".env" ]; then
        cp .env.example .env
        echo "⚠️  .env 파일이 없어 .env.example을 복사했습니다."
        echo "    서버에서 .env를 편집해주세요: nano /home/jihoon/news-briefing/.env"
    fi

    # systemd 서비스 등록
    sudo cp deploy/news-briefing.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable ${SERVICE_NAME}
    
    # 서비스 재시작
    sudo systemctl restart ${SERVICE_NAME}
    echo "✅ 서비스 재시작 완료"

    # 상태 확인
    sleep 2
    sudo systemctl status ${SERVICE_NAME} --no-pager -l
EOF

echo ""
echo "✅ 배포 완료!"
echo "📊 서비스 상태: ssh ${SERVER} 'sudo systemctl status ${SERVICE_NAME}'"
echo "📋 로그 확인: ssh ${SERVER} 'tail -f ${REMOTE_DIR}/logs/service.log'"
```

### 12-4. 서버 관리 명령어

```bash
# === 로컬에서 실행 ===

# 배포
cd news-briefing
bash deploy/deploy.sh

# === 서버에서 실행 (ssh 접속 후) ===

# 서비스 상태 확인
sudo systemctl status news-briefing

# 서비스 중지
sudo systemctl stop news-briefing

# 서비스 시작
sudo systemctl start news-briefing

# 서비스 재시작
sudo systemctl restart news-briefing

# 실시간 로그 확인
tail -f /home/jihoon/news-briefing/logs/service.log

# 에러 로그 확인
tail -f /home/jihoon/news-briefing/logs/service-error.log

# journalctl 로그
sudo journalctl -u news-briefing -f

# .env 편집
nano /home/jihoon/news-briefing/.env
```

### 12-5. 로컬 개발 → 배포 워크플로우

```
[로컬 개발]
    │
    ├── 1. 코드 작성/수정
    ├── 2. 로컬 테스트: python -m src.main --daemon
    ├── 3. 정상 동작 확인
    │
    ▼
[배포]
    │
    ├── 4. bash deploy/deploy.sh 실행
    │      → rsync로 파일 전송 (data/, briefings/, .env 제외)
    │      → pip install
    │      → systemctl restart
    │
    ▼
[운영]
    │
    ├── 서버에서 상시 실행 (systemd)
    ├── 비정상 종료 시 자동 재시작 (Restart=always)
    ├── 서버 재부팅 시 자동 시작 (enable)
    └── 텔레그램 봇으로 모든 설정 변경
```

### 12-6. 주의사항

- `.env` 파일은 rsync에서 제외. 서버에서 최초 1회만 직접 편집
- `data/news.db`도 rsync에서 제외. 배포 시 기존 DB를 덮어쓰지 않음
- `briefings/` 폴더도 제외. 서버에 축적된 브리핑 파일 보존
- 서버에 SSH 키가 등록되어 있어야 함 (`ssh-copy-id jihoon@34.172.56.22`)
- 서버에 Python 3.11+ 설치 필요 (없으면 `sudo apt install python3.11 python3.11-venv`)

### 12-7. .gitignore

```
# Python
__pycache__/
*.pyc
venv/

# 환경변수
.env

# 데이터 (서버에서 생성)
data/
briefings/
logs/
```

---

## 13. .env 파일

```env
# Anthropic API
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Telegram Bot
TELEGRAM_BOT_TOKEN=123456:ABC-xxxxx

# 최초 실행 시 봇에게 아무 메시지나 보내면 chat_id가 자동 저장됨

# GCP 서버 (deploy.sh에서 참조, 런타임에는 불필요)
# DEPLOY_SERVER=jihoon@34.172.56.22
```

---

## 14. requirements.txt

```
python-telegram-bot>=21.0
feedparser>=6.0
requests>=2.31
beautifulsoup4>=4.12
anthropic>=0.40
apscheduler>=3.10
python-dotenv>=1.0
```

---

## 15. 초기 소스 등록 데이터

시스템 최초 실행 시 아래 소스들을 자동 등록한다 (텔레그램 봇으로 이후 추가/삭제 가능):

```python
INITIAL_SOURCES = [
    # Tier 1: RSS
    ("Tom's Hardware", "https://www.tomshardware.com/feeds.xml"),
    ("MacRumors", "https://feeds.macrumors.com/MacRumors-All"),
    ("CNBC Technology", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910"),
    ("WCCFTech", "https://wccftech.com/feed/"),
    # Tier 2: HTML
    ("전자신문", "https://www.etnews.com/news/section.html?id1=06"),
    ("디일렉", "https://www.thelec.kr/news/articleList.html?sc_section_code=S1N2&view_type=sm"),
    ("ZDNet Korea", "https://zdnet.co.kr/news/?lstcode=0050&page=1"),
    ("한국경제", "https://www.hankyung.com/industry/semicon-electronics"),
    ("TrendForce", "https://www.trendforce.com/news/"),
    ("DIGITIMES", "https://www.digitimes.com/tech/"),
    ("Omdia", "https://omdia.tech.informa.com/pr"),
    ("Counterpoint", "https://counterpointresearch.com/en/insights"),
    ("SemiAnalysis", "https://semianalysis.com/"),
]
```

---

## 부록: 요구사항 대비 변경점

### v1.0 → v2.0

| 항목 | v1.0 | v2.0 |
|------|------|------|
| 설정 관리 | YAML 파일 (정적) | DB + 텔레그램 봇 (동적) |
| 키워드 필터 | 전역 키워드 그룹 (7개 카테고리) | **소스별 개별 키워드** + 전역 키워드 |
| 키워드 수정 | 파일 편집 후 재시작 | **텔레그램 봇으로 실시간 추가/삭제** |
| 소스 관리 | YAML에 고정 | **텔레그램 봇으로 추가/삭제** |
| 파싱 대상 | 소스 홈페이지 | **등록된 정확한 URL에서만 파싱** |
| 요약 포맷 | 카테고리별 분류 + 상세 요약 | **기사당 한줄 요약 (키워드+제목)** |
| 브리핑 시간 | settings.yaml에 고정 | **텔레그램 봇으로 동적 변경** |
| 전달 채널 | Slack/Telegram/Email 선택 | **텔레그램 전용** |
| 요약 저장 | DB에만 저장 | **briefings/ 폴더에 .md 파일 저장** |
| 소스별 파서 | 소스마다 전용 파서 모듈 | **범용 HTML 파서 (RSS 자동 감지)** |
| 제어 인터페이스 | CLI | **텔레그램 봇** |

### v2.0 → v2.1

| 항목 | v2.0 | v2.1 |
|------|------|------|
| 운영 환경 | 미정 | **GCP 인스턴스 34.172.56.22** |
| 프로세스 관리 | 미정 | **systemd 서비스 (상시 실행, 자동 재시작)** |
| 배포 방식 | 미정 | **rsync 기반 deploy.sh 스크립트** |
| 워크플로우 | 미정 | **로컬 개발 → deploy.sh → 서버 자동 반영** |
| 프로젝트 구조 | deploy/ 없음 | **deploy/ 폴더 (서비스 파일 + 배포 스크립트)** |
| 구현 순서 | Phase 5까지 | **Phase 6: 배포 단계 추가** |
| n8n | 언급 없음 | **사용하지 않음 (순수 Python)** |
