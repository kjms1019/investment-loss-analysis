# "왜 잃었지?" — 손실 선별 → 심리 귀속 파이프라인 (준모 담당)

> 이 문서 하나로 전체 흐름·개념·실행법·설계근거를 다 파악할 수 있게 정리했다.
> 코드: `analysis/loss_screener/`, `analysis/psych_agent/`, `analysis/pipeline.py`, `web/`

---

## 0. 한눈 요약

완결된 국내주식 거래내역을 **사후 복기**해, **시장 영향을 제거한 진짜 매매 실패**만 골라
그 원인을 **심리 패턴(리벤지·과매매·처분효과)** 으로 진단한다. (매매 추천 ❌ → 규제 리스크 낮음)

핵심 2단계:

```
① 손실 선별   : 절대손익이 아니라 "시장 빼고 유독 못한 것"(초과수익 α)으로 복기 대상을 고른다
② 심리 귀속   : 고른 손실 거래마다 리벤지/과매매/처분효과 중 무엇이 원인인지 귀속 → 라우팅
```

---

## 1. 전체 시스템 안에서의 위치

전체 멀티에이전트 "왜 잃었지?" 시스템:

```
총괄 오케스트레이터
  │  (음성/조건으로 복기 대상 거래 범위 결정 — 손실액/최근성/거래량)
  │
  ├─ ① 손실 선별기  ◀── analysis/loss_screener  (이 파이프라인 1단계, 공유 상단)
  │      시장 제거 초과수익 α 로 "네 탓 손실"만 추림
  │
  ├─ 다중분류기     ◀── 각 거래를 3문제 중 가장 높은 확률로 분류 (아직 미구현)
  │      입력 피처 = 아래 세 에이전트의 귀속 점수
  │
  ├─ 진입오류 에이전트       (수빈)
  ├─ 손절실패 에이전트       (영현)
  └─ 심리·과매매 에이전트 ◀── analysis/psych_agent  (준모 = 나, 이 파이프라인 2단계)
         리벤지/과매매/처분효과 귀속
  │
  └─ 비슷한 실수 반복 시 알림 (미구현)
```

이 레포(준모 브랜치)에는 **① 손실 선별기 + ③ 심리 에이전트 + 둘을 잇는 pipeline + 웹 데모**가 들어있다.
(① 선별기는 공유 상단 컴포넌트 — 메인 오케스트레이션 편입 여부는 추후 결정.)

---

## 2. 데이터 흐름

```
거래내역(CSV: datetime,code,name,side,qty,price)
        │
        ▼  psych_agent/preprocess.py  (계좌 1회 리플레이, 이동평균법)
   ┌─────────────────────────────────────────────┐
   │ PositionCycle[]  : flat→진입·증감→flat 라운드트립  │
   │ SellEvent[]      : 매도마다 실현부호 + 그 순간 보유 中 다른종목 스냅샷 │
   └─────────────────────────────────────────────┘
        │
        ├─► loss_screener/screener.score_cycles()      ── 1단계 ──
        │     사이클별 α = R_bh − R_mkt 계산 → tier 분류 → 복기대상 선별
        │     (R_mkt = 808종목 동일가중 합성지수, market_index.py)
        │
        └─► psych_agent/focus.attribute_losses()        ── 2단계 ──
              복기대상 각 손실거래에 리벤지/과매매/처분효과 0~3점 귀속
              → dominant 유형 = 라우팅 대상 (없으면 '기타(비심리)')
        │
        ▼  pipeline.py (위 둘을 preprocess 1회 공유로 묶음)
   손실거래별 진단 + 라우팅 집계
        │
        ▼  web_export.py → web/ (Next.js 대시보드)
```

---

## 3. 핵심 개념과 공식

### 3-1. 손실의 정의 = 초과수익 α (시장 제거)

절대손익은 시장 상황에 오염된다. 우리는 "시장 따라 빠진 것"이 아니라
**"남들은 안 잃었는데 너만 유독 못한"** 포지션 실패를 본다. 그래서 한 거래의 수익을 분해:

```
실제 수익률 = 시장 성분(제거)  +  선택 성분 α  +  타이밍 성분
```

| 기호 | 정의 | 의미 |
|------|------|------|
| `R_trade` | 실현 수익률(체결·수수료 반영) | 실제 손익 |
| `R_bh` | 종목 단순보유 수익률 (진입가→청산가) | 종목 자체 성과 |
| `R_mkt` | 합성지수 수익률 (같은 보유구간) | 시장 성분 |
| **`α`** | `R_bh − R_mkt` | **시장 뺀 종목 선택 성과** |
| `timing` | `R_trade − R_bh` | 체결/타이밍 성분 |

**선별 우선순위 (tier):**
- **1순위** — 절대손실(`realized_pnl<0`) ∧ `α<0`: 실제로 잃고 + 시장보다도 못함
- **2순위** — `α<0` 이지만 번 거래: 기회손실(시장만큼 못 먹음)
- **제외** — 절대론 손실이나 `α≥0`: 시장 따라 빠진 것 → 네 탓 아님

### 3-2. 벤치마크 = 808종목 동일가중 합성지수

추가 수집 없이 우리 1분봉만으로 만든다. **각 종목 종가를 자기 첫 종가로 정규화 →
공통 분 그리드에 ffill → 횡단면 평균.** (`market_index.py`, 캐시 `data/market_index.parquet`)

### 3-3. 세 가지 심리 유형 (측정법 + 학술 근거)

| 유형 | 측정 축 | 측정법 | 근거 |
|------|---------|--------|------|
| **리벤지** | 결정/시간 | 직전 손절 후 임계시간(30분) 내 재진입 + 포지션 확대 + 재손실 → 1/2/3점 | 행동재무 문헌 |
| **과매매** | 결정/빈도 | 연 회전율 ≥250% / 거래 군집일(개인 일중앙값 대비 배수) | Barber & Odean (2000) |
| **처분효과** | 포지션/보유기간 | PGR vs PLR (실현이익률 vs 실현손실률) + 손실 보유기간 비대칭 | Shefrin & Statman (1985), Odean (1998) |

### 3-4. 손실거래 단위 귀속 (`focus.py`)

**중요 원칙: 손실 거래 = 설명 대상(anchor), 전체 거래 = 패턴 계산 context.**
리벤지(직전 시퀀스)·과매매(빈도)·처분효과(계좌 PGR/보유 비대칭)는 손실 거래 하나만으로
못 재기 때문에, 전체 거래 맥락 위에서 그 손실 거래에 원인을 **귀속**시킨다.

- 리벤지 귀속: 이 손실이 "직전 손절 후 충동 재진입"이었나
- 처분효과 귀속: 이 손실을 평균 수익거래보다 훨씬 오래 들고 있었나 / 그동안 수익은 익절했나
- 과매매 귀속: 이 손실이 그날 거래 폭주 군집 안에서 났나

`dominant` = 점수 최댓값 유형 = 다중분류기가 보낼 곳. 모두 0점이면 `기타(비심리)` →
진입오류/손절실패 에이전트로 갈 케이스.

---

## 4. 파일 맵

### `analysis/loss_screener/` — ① 손실 선별기
| 파일 | 역할 |
|------|------|
| `market_index.py` | 808종목 동일가중 합성지수 빌드·캐시·조회(`MarketIndex`) |
| `screener.py` | 사이클별 α/tier 계산. `score_cycles(pre,…)`(공유) / `screen_trades(…)`(독립) |
| `run.py` | 선별기 단독 데모 CLI |
| `README.md` | 선별기 상세 |

### `analysis/psych_agent/` — ③ 심리 에이전트 (준모)
| 파일 | 역할 |
|------|------|
| `schema.py` | Trade / PositionCycle / SellEvent / Preprocessed / TypeFinding |
| `preprocess.py` | 거래 → 사이클 + 매도이벤트 (계좌 1회 리플레이, 이동평균법) |
| `prices.py` | 1분봉 종가 조회(merge_asof) |
| `detectors/` | revenge / overtrading / disposition (계좌 전체 패턴 검출) |
| `focus.py` | **손실거래별 심리 귀속** `attribute_losses()` — screener 비의존 |
| `diagnose.py` | LLM 문장화(ANTHROPIC_API_KEY) + 템플릿 폴백 + 유형별 교정 |
| `agent.py` | `PsychAgent` (계좌 전체 분석) |
| `dummy_data.py` | 실 min1 가격 기반 더미 거래 생성(시나리오) |
| `run.py` / `export_web.py` | 계좌 전체 분석 CLI / 웹 JSON 익스포트 |
| `README.md` | 에이전트 상세 |

### 통합 / 웹
| 파일 | 역할 |
|------|------|
| `analysis/pipeline.py` | **오케스트레이션 글루**: preprocess 1회 공유 → 선별 → 귀속 → 라우팅 (CLI) |
| `analysis/web_export.py` | pipeline 출력 → `web/src/data/flow_*.json` |
| `web/` | Next.js 대시보드 (Vercel). flow 뷰 + 계좌전체 뷰 토글 |

---

## 5. 실행법

```bash
cd analysis
source venv/bin/activate          # pandas / numpy / pyarrow (LLM은 선택: anthropic)

# (최초 1회) 합성 시장지수 빌드·캐시 — 약 2분
python -m loss_screener.market_index

# 손실 선별만 보기
python -m loss_screener.run --demo

# 심리 에이전트 단독(계좌 전체 패턴)
python -m psych_agent.run --demo [--scenario all|revenge|overtrading|disposition]

# ★ 전체 파이프라인: 손실선별 → 심리 귀속 라우팅
python -m pipeline --demo [--scenario ...]

# 실제 거래내역으로
python -m pipeline --trades my_trades.csv
```

### 웹 데모

```bash
cd analysis && python -m web_export ../web/src/data   # 데이터 갱신
cd ../web && npm install && npm run dev               # http://localhost:3000
# 시나리오 딥링크: /#all /#revenge /#overtrading /#disposition
```

Vercel 배포: Root Directory = `web` (정적 SSG, 백엔드 불필요). 자세히는 `web/README.md`.

### 입력 거래내역 스키마

| 컬럼 | 설명 |
|------|------|
| `datetime` | 체결 시각 |
| `code` | 종목코드 6자리 |
| `name` | 종목명 |
| `side` | `BUY` / `SELL` |
| `qty` | 체결 수량 |
| `price` | 체결 단가 |

---

## 6. 설계 결정 (왜 이렇게 했나)

1. **절대손익 ❌ → 초과수익 α**: 시장 상황을 제거해야 "이 사람의 매매 실패"만 남는다.
2. **벤치마크 = 자체 808종목 동일가중 합성지수**: 추가 수집 0, 자급자족.
3. **손실=anchor / 전체=context**: 심리 패턴은 시퀀스·빈도·계좌비율이라 손실 하나로 못 잼.
4. **psych_agent 가 screener 에 비의존**: focus 입력은 사이클 키 목록뿐 → 메인 오케스트레이션
   편입 여부와 무관하게 심리 에이전트는 독립적으로 동작/테스트 가능.
5. **룰+LLM 하이브리드**: 룰/통계가 팩트(수치)를 계산, LLM은 문장만. 키 없으면 템플릿 폴백.
6. **웹은 정적(SSG)**: 에이전트 실제 출력 JSON을 빌드에 포함 → Vercel에 그대로 배포, 가장 안정적.

---

## 7. 빌드 중 잡은 함정 (합성지수)

1. **분 수익률 누적복리 → +215% 상방편향**(호가 bounce·볼록성) → **정규화 레벨 평균**으로 교체.
2. **분마다 구성 종목 수 1~789 변동 → 지수 점프**(가짜 +700% 분봉 7,233개) →
   **공통 그리드 ffill**로 778~798 상시 고정 → 점프 17개로 소멸. (최종 1년 +27.7%, 정상)

---

## 8. 알려진 한계 / 다음 단계

- **타이밍 축**: 현재 `R_trade − R_bh` 라 단일 매수/매도에선 수수료(−0.2%)로 거의 상수.
  분할매매가 있어야 의미. → **VWAP 실행 갭**(평단가 vs 구간 VWAP)으로 고도화 예정.
- **α**: β=1 단순 차감. → **마켓모델 β-조정**(일봉 6~12개월 회귀)로 업그레이드 가능.
- **다중분류기**: 미구현. focus의 R/O/D 점수 + 진입/손절 에이전트 신호를 합쳐 확률 라우팅.
- **미청산 포지션**: 현재 청산 사이클만 선별(진입 타이밍만 평가 가능).
- **임계값 튜닝**: 더미는 시장 노이즈성 소액 손실이 많아 '기타' 비중이 큼 → 실데이터로 조정 필요.
- **음성 트리거 / 반복 실수 알림**: 총괄 오케스트레이터 영역, 미구현.

---

## 9. 환경

- Python 3.13 venv (`analysis/venv`), 의존: pandas / numpy / pyarrow (LLM은 `anthropic` 선택).
- 데이터: `analysis/data/min1/{code}.parquet` (코스피 1분봉 1년, 808종목, gitignore).
- 합성지수 캐시: `analysis/data/market_index.parquet` (gitignore).
- 키움 키는 루트 `.env`. 데이터 수집은 별도(PR #1 feat/kospi-min1-collector).
```
