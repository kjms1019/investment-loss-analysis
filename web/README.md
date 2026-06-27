# 왜 잃었지? — 웹 데모 (Next.js + FastAPI)

복기 루프 **6단계**를 실제 백엔드 API로 구동하는 대시보드.
이전 정적 JSON 버전(`src/data/*.json`, `FlowView/PatternCards/Diagnosis`)을 대체해,
이제 화면은 전부 `analysis/api`(FastAPI)에서 실시간으로 데이터를 받아 그린다.

> 분석단·예측단 **모델/파이프라인** 설명은 루트 [../README.md](../README.md) 참고.
> 이 문서는 **UI 레이어와 백엔드 연결**에 집중한다.

---

## 한눈에 — 아키텍처

```
┌────────────────────────────┐        HTTP (JSON)        ┌──────────────────────────────┐
│  브라우저 (Next.js SPA)      │  ───────────────────────▶ │  FastAPI  analysis/api/main.py │
│  src/app/page.tsx          │   GET /api/...            │  (화면별 엔드포인트, 읽기 전용)  │
│  src/components/why/ui.tsx  │ ◀───────────────────────  │                              │
│  src/lib/api.ts (클라이언트) │        DTO                └───────────────┬──────────────┘
└────────────────────────────┘                                          │ 읽기
                                                                         ▼
                  ┌──────────────────────────────────────────────────────────────────┐
                  │  orchestrator.sqlite3      분석 결과(agent_results·normalized_trades) │
                  │  user_profiles.sqlite3     user→run 매핑·패턴·심리 라벨               │
                  │  ui_trade_charts.sqlite3   거래별 미니차트 캐시 (UI 전용)              │
                  │  analysis/data/min1/*.parquet   종목별 1분봉(실거래 차트 소스)         │
                  │  tests/fixtures/...xlsx    데모 사용자(종결거래·현재보유·투자계획)       │
                  └──────────────────────────────────────────────────────────────────┘
```

핵심: **백엔드는 분석/예측 로직을 새로 만들지 않고**, 기존 모듈(`report.builder`,
`orchestrator.demo_alert_runner`, `predictor`)의 출력을 **화면 모양 DTO로 매핑**만 한다.
차트·성향 비교·합성 보유 같은 "화면 구현용" 보조 계산만 API/UI 레이어에 둔다.

---

## 실행

### 1) 백엔드 (FastAPI)

```bash
pip install -r analysis/requirements.txt

# 데모 DB 백필(처음 1회) — 사용자 프로파일·분석결과 적재
python -c "from analysis.orchestrator.demo_alert_runner import backfill_user_profiles; \
backfill_user_profiles('tests/fixtures/demo_users_all_data.final_3sheets.xlsx')"

# 거래별 미니차트 DB 빌드(백필 후 1회 — trade_id 바뀌면 재실행)
python -m analysis.ui.build_trade_charts

uvicorn analysis.api.main:app --port 8000 --reload   # http://127.0.0.1:8000/docs
```

### 2) 프론트엔드 (Next.js)

```bash
cd web
npm install
npm run dev          # http://localhost:3000
```

API 주소는 `NEXT_PUBLIC_API_BASE`(기본 `http://127.0.0.1:8000`)로 바꿀 수 있다.

---

## 화면 흐름 (6단계)

해시 라우팅(`#/dashboard` 등). 로그인→약관을 거쳐야 이후 화면 진입(새로고침·URL 직접입력 포함).

| # | 화면 | 호출 엔드포인트 | 백엔드가 만드는 것 |
|---|---|---|---|
| ① | 업로드 | `GET /api/users`, `POST /api/analyze` | 데모 사용자 목록(백필 결과) |
| ② | 분석 진행 | (②~④ 공통 로드) | 파싱→손실선별→2way 라우팅을 단계 애니메이션으로 |
| ③ | 진단 대시보드 | `GET /api/dashboard/{user}`, `/api/all-trades/{user}` | 도메인 분류 카운트·총손실금, 전체거래 손익차트 |
| ④ | 거래별 설명 | `GET /api/trades/{user}` | 거래별 실거래 미니차트 + 분류 근거(피쳐) + 심리 |
| ⑤ | 내 성향 | `GET /api/disposition/{user}` | 10명 모집단 평균 대비 피쳐 시그니처 + 솔루션 |
| ⑥ | 실시간 알림 | `GET /api/holdings/{user}` | 보유 전체 추적 + 손절선 근접 경고 + 매수 예정 경고 |

상태/네비게이션은 전부 `src/app/page.tsx`의 `Home` 컴포넌트가 관리한다.

---

## 화면별 상세 (UI ↔ 백엔드)

### ② 분석 진행 — 단계별 색인 차트
- 4단계(파싱→손실선별→2way 라우팅→거래별 설명)를 타이머로 진행.
- 전체거래 차트가 단계마다 **점진적으로 색인**: 파싱 전엔 막대 없이 축선만(레이아웃 고정) →
  파싱 후 전체 회색 → 손실 선별 시 손실만 → 라우팅 시 진입오류(주황)·손절실패(남색).

### ③ 진단 대시보드
- 도메인 2분류(손절실패·진입오류) 빈도·총손실금 카드.
- **분석탭과 동일한 손익 차트**(이익 위·손실 아래)에서 **분석 중 도메인만 색인**, 나머지 회색.
- 3카드 ‖ 차트 평행 배치(스크롤 최소화).
- 상호작용: 빈도·금액 winner가 다르면 선택지 제공(`/api/interaction/{user}/select`).

### ④ 거래별 설명 — 미니탭
- **탭 1개 = 거래 1건**(스크롤 대신 탭 전환). 필터: 유형·심각도(3단계로 정규화).
- 카드 왼쪽: **그 거래의 실제 보유구간 가격 차트**(`TradeMiniChart`) — 진입·청산·손절선·돌파·최대낙폭 마커.
- 카드 오른쪽: **분류 근거**(분류기가 걸러낸 피쳐를 문장으로) + **심리 심화**(처분효과/리벤지 evidence).
  - 손절선 미접촉(`breached=False`) 거래는 "손절실패 강도 약함"으로 정직 표기.

### ⑤ 내 성향 — 모집단 대비 + 솔루션
- 헤드라인: "OOO님은 손실 N건 중 X가 가장 잦고, 그중 '피쳐'를 남보다 1.9배 자주 합니다".
- **피쳐 시그니처**: 본인 발생률 vs 10명 평균(│ 마커) 비교 막대. 표본 가중(1건짜리 고배율은 보류).
- 심리 신호(처분효과·리벤지) 본인 vs 평균.
- **최종 솔루션**: 성향에 맞춘 교정안(흰 카드 안에 남색 카드 3개).

### ⑥ 실시간 알림 — 미래에셋 앱 시뮬레이션
- **현재=6/23 컷오프, 6/24~26을 미래로 추적**한다는 가정.
- 미래에셋 앱 목업(`PhoneApp`): 세로 폰 프레임·다이나믹아일랜드·검색바·탭·하단 네비, 우상단 **종**.
- 두 시나리오(상단 토글):
  - **손절실패**(남색 종): 앱이 **보유 종목 리스트** 표시. 보유 전체(이익+손실)를 추적하다
    **손절선에 막 닿으며 내려가는** 종목에 경고.
  - **진입오류**(주황 종): 앱이 **매수 주문 화면** 표시. 사려는 종목이 고점 추격 등이면 경고.
- **종 클릭 → 앱이 왼쪽으로 슬라이드 + 오른쪽에 예측 알림 카드 슬라이드인**.
  알림 카드엔 주식창 차트(`AlertMiniChart`)로 매수→하락→손절선 터치를 그린다.

### 거래별 → 내 성향 되묻기 플로우
- 거래별 탭 맨 아래 "내 성향 보러 가기" 버튼.
- 한 도메인만 본 사용자면 **"안 본 다른 도메인도 볼까요?"** 되묻고, 네 → 진단으로 복귀(다른 도메인) →
  거래별 → 둘 다 봤으면 내 성향으로. (`seenDomains` 상태로 추적)

---

## 차트 시스템

| 컴포넌트 | 위치 | 용도 |
|---|---|---|
| `TradeMiniChart` | `components/why/ui.tsx` | ④ 거래별 — 보유구간 + 진입/청산/손절선/돌파/최대낙폭 |
| `AlertMiniChart` | `components/why/ui.tsx` | ⑥ 알림 — 매수/현재/손절선/돌파 (주식창) |
| `LossBars` | `components/why/ui.tsx` | ②③ 막대 차트(손익·도메인 색인) |

- 모두 의존성 없는 **순수 SVG**. `viewBox` 좌표계에 가격→y 매핑, 라벨은 흰 외곽선(halo)으로 선 위에서도 가독.
- ④ 거래별 차트 데이터는 **UI 전용 DB** `analysis/data/ui_trade_charts.sqlite3`에 캐시
  (`analysis/ui/build_trade_charts.py`가 orchestrator DB + min1 parquet로 생성).
- ⑥ 알림 차트는 API가 min1에서 즉석 생성(`_alert_chart`).

---

## 백엔드 연결 상세 (`analysis/api/main.py`)

읽기 전용 매퍼. 각 엔드포인트가 기존 모듈 출력을 DTO로 변환한다.

| 엔드포인트 | 소스 | 비고 |
|---|---|---|
| `/api/users` | user_profiles | 데모 사용자 |
| `/api/dashboard/{u}` | `report.build_user_summary` | 도메인 카운트·총손실금·상호작용 |
| `/api/trades/{u}` | report items + `ui_trade_charts` | `chart`·`why`(피쳐 근거)·`psych` 첨부 |
| `/api/all-trades/{u}` | 데모 fixture | 이익 포함 전체거래(차트용) |
| `/api/disposition/{u}` | `_population()` 집계 | 10명 모집단 대비 피쳐 시그니처 |
| `/api/alerts/{u}` | `demo_alert_runner` B·C 루프 | 손절(보유)·진입(예정) 예측 알림 + 차트 |
| `/api/holdings/{u}` | `_all_holdings()` | 보유 전체 추적 + 손절선 근접 경고 + 매수 예정 |
| `/api/interaction/{u}/select` | `orchestrator.interaction` 재현 | 도메인 선택 → 다음 라운드 |

### 데모용 보조 계산 (아키텍처엔 불필요, 화면 구현용)
- **합성 보유**(`_synthetic_holdings`): fixture 보유가 사람당 1~5종목뿐이라, 우량주를 실거래 주가로
  더해 7종목 포트폴리오로 채움 — **차트·등락률은 실제 min1**, 보유 사실만 데모용.
- **손절선 근접 경고**(`_danger_holding`): 이미 −70%인 종목이 아니라 **고점에서 하락하며 손절선에
  막 닿는** 종목을 실거래에서 골라 라이브 경고 주체로. "닿을락말락" 순간에 알림.

---

## 디렉터리

```
web/src/
├── app/page.tsx           전체 화면·라우팅·상태 (메인)
├── app/globals.css        애니메이션 키프레임(wlbell·wlcardin 등)
├── components/why/ui.tsx  DOMAIN 상수·아이콘·차트 컴포넌트(현재 사용)
└── lib/api.ts             API 클라이언트 + DTO 타입
```

> `components/{Diagnosis,FlowView,PatternCards,ui}.tsx`, `lib/{data,flow,types}.ts`, `data/*.json`
> 은 **구버전(정적 JSON)** 잔재로, 현재 `page.tsx`는 사용하지 않는다.

---

## 데이터·운영 주의

- 데모 DB **백필을 다시 돌리면 trade_id가 바뀌므로** `build_trade_charts`도 재실행해야 ④ 차트가 매칭된다.
- API는 분봉 전수 평가가 느려 `_all_alerts`·`_all_holdings`·`_trade_charts`를 **프로세스 캐시**(lru_cache)한다.
  데이터 갱신 후엔 API 재시작 필요.
- min1 parquet(2025-06-23~, 801종목)는 GitHub Release로 배포. 로컬 `analysis/data/min1/`에 있어야 차트가 그려진다.
