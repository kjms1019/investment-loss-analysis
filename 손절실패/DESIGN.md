# 손절실패 에이전트 — 설계 문서

> 원본 명세: [`손절실패_에이전트_구축명세.md`](../손절실패_에이전트_구축명세.md)
> 이 문서는 구현 후 확정된 구조, 점수 산출 근거, 알려진 한계를 정리한다.

---

## 1. 시스템 안에서의 위치

```
끝난 거래
    ├─ 진입 에이전트     → 0~1  ("잘못된 타이밍에 들어갔나")
    ├─ 심리 에이전트     → 0~1  ("반복되는 나쁜 패턴이 있나")
    └─ 손절실패 에이전트  → 0~1  ("버텨서 손실을 키웠나")   ← 이 문서

가장 높은 점수 = 그 거래의 대표 문제로 채택
```

세 에이전트의 점수는 **"이 손실에 이 문제가 기여한 정도"**라는 동일한 의미여야 비교가 성립한다. 이 전제가 아래 3절(수익 거래 처리)의 설계를 결정한다.

---

## 2. 파이프라인

```
거래(Transaction) + 시세(OHLCV/분봉)
        │
        ▼
① build_cycles            거래를 매수→매도 완결 사이클로 묶음 (물타기 판정 포함)
        │
        ▼
② attach_path_features    손절선 결정 + MAE·이탈일 계산 (분봉 있으면 정밀, 없으면 일봉 폴백)
        │
        ▼
③ compute_signals         신호 4개 산출: 확대 / 지연 / 물타기 / 초과손실
        │
        ▼
④ compute_score           신호 4개를 가중합 → 0~1 (수익 거래는 0)
   compute_shadow_score    수익 거래라도 "손실이었다면 몇 점"을 별도 계산
        │
        ▼
⑤ generate_report         판정유형 + 점수 + 신호값 + 서술문 + 추천규칙 + 플래그
```

| 단계 | 파일 |
|---|---|
| ① | [`cycles.py`](cycles.py) |
| ② | [`path_features.py`](path_features.py) |
| ③ | [`rules.py`](rules.py) |
| ④ | [`scoring.py`](scoring.py) |
| ⑤ | [`report.py`](report.py) |
| 진입점 | [`agent.py`](agent.py) — `analyze_all()`(더미), `analyze_real()`(parquet 실데이터) |
| 설정 | [`config.py`](config.py) — 모든 임계값·가중치 |
| 데이터 로더 | [`data_loader.py`](data_loader.py) — parquet → 일봉/분봉 |

---

## 3. 손절선 결정 (우선순위 폴백)

```
사용자 직접 입력 손절률
        │ 없으면
        ▼
ATR(14일) × k(2.0) ÷ 매수평단     ← 변동성 기반 자동 계산
        │ 계산 불가하면 (데이터 부족 등)
        ▼
고정 -5%
```

고정 -5%를 1순위로 안 두는 이유: 하루 변동폭이 ±7%인 종목에 -5% 고정선을 적용하면 정상적인 변동을 손절실패로 오판한다. ATR 기반 동적 손절선이 우선이다.

---

## 4. 신호 4개

보유기간 일봉(또는 분봉)을 스캔해 두 값을 먼저 뽑는다.

- **MAE** — 보유 중 평단 대비 최대 손실 (그날 저가 기준, 분봉 있으면 분 단위)
- **이탈일** — 손절선을 처음 넘은 날

이 두 값으로 신호 4개를 계산한다.

| 신호 | 가중치 | 정의 | 정규화 |
|---|---|---|---|
| **확대** | 0.35 | 최종 실현손실이 손절선을 얼마나 더 넘었나 | 20%p 초과 → 1.0, 또는 손절선의 4배 → 1.0 (max) |
| **지연** | 0.30 | 이탈 후 며칠(영업일) 더 들고 있었나 | 2일 미만 0.1, 2~5일 선형 0.3~0.7, 5일 이상 0.7~1.0 |
| **물타기** | 0.20 | 손실 중 몇 번, 얼마나 더 샀나 | 4회 → 1.0, 또는 추가매수량이 최초매수량의 2배 → 1.0 (max) |
| **초과손실** | 0.15 | MAE가 손절선을 얼마나 더 깊게 뚫었나 | 손절선의 2배 초과 → 1.0 |

안전장치:
- 손절선 자체를 안 넘었으면(`breached=False`) → 가중합 × 0.3
- 수익 거래 → 0 (5절 참고)

> ⚠️ **가중치 0.35/0.30/0.20/0.15는 검증된 값이 아니라 prior(가설)다.** 6절에서 근거와 한계를 별도로 정리한다.

---

## 5. 수익 거래 처리 — `score` vs `shadow_score`

### 문제

수익 거래는 점수 0이다. 그런데 도중 -20% 넘게 빠졌다가 운이 좋아 회복해서 익절한 경우, **점수만 보면 아무 문제 없는 거래처럼 보인다.** 하지만 행동 자체(손절선을 넘기고도 버틴 것)는 손실로 끝난 거래와 동일하다.

이건 의사결정 이론에서 **"resulting"**이라 부르는 함정과 정반대 방향의 문제다 — *결과가 좋았다고 판단(행동)이 좋았다고 착각하는 오류*. 행동재무학에서는 이를 **"break-even effect / get-evenitis"**로 설명한다: 손실 구간에 들어가면 본전 회복을 위해 더 위험을 추구하게 된다는 이론이다 (Kahneman & Tversky의 Prospect Theory, 손실 영역 risk-seeking 곡선에서 도출).

### 해결: 점수는 정의를 지키고, 행동 평가는 별도 필드로

| 필드 | 의미 | 수익 거래일 때 |
|---|---|---|
| `score` | "이 손실에 이 문제가 기여한 정도" — **cross-agent 비교용**, 손실이 없으면 정의상 0 | `0.0` |
| `shadow_score` | "이 보유 행동이 손실로 끝났다면 몇 점짜리 손절실패였을지" — **코칭 전용**, 비교에는 안 씀 | 실제 값 (breach 없으면 `None`) |
| `flags.lucky_hold` | 수익 거래 + MAE ≤ -20% | `True` |

```
예) 포스코퓨처엠 가상거래

  11-18 당일 고가(216,000) 추격매수
        ↓
  MAE -20.1% (172,500, 분봉 기준) ← 손절선(-11.5%, ATR 기준) 훌쩍 이탈
        ↓
  72거래일 버팀 (아무 조치 없음)
        ↓
  1-22 217,000에 +0.46% 익절

  score        = 0.0     (수익 거래라 정의상 0)
  shadow_score = 0.36    (같은 행동을 손실로 채점하면 0.36점짜리 손절실패)
  lucky_hold   = True
```

`compute_signals`의 지연·물타기·초과손실 신호는 원래부터 수익/손실 여부와 무관하게 MAE·이탈일 기준으로 계산된다(`확대` 신호만 최종 실현손실에 의존해 자연히 0이 됨). 따라서 `shadow_score`는 기존 신호 계산을 그대로 재사용해 가중합만 한 번 더 구하는 것으로 충분하다 — 엔진 구조 변경 없이 추가됨 (`scoring.py`의 `compute_shadow_score`).

---

## 6. 점수 가중치의 학술적 근거와 한계

**"이 네 신호가 중요하다"는 근거는 탄탄하다. "정확히 이 비율"이라는 근거는 어디에도 없다.**

| 신호 | 근거 |
|---|---|
| 지연 | Shefrin & Statman (1985) — "처분 효과(disposition effect)" 원조 논문. 손실은 길게 들고 수익은 빨리 파는 행동을 최초로 실증 |
| 지연 | Odean (1998) — 실거래 계좌 1만 개 분석. 손실 미실현 성향이 세후 수익률을 깎는다는 것을 실증 |
| 지연 (전문가도 동일) | Locke & Mann (2005) — 전문 선물 트레이더도 손실을 더 오래 들고, 이 규율 정도가 향후 성과를 예측한다는 것을 실증 |
| 물타기 (본전 추구) | Break-even effect / get-evenitis — Kahneman & Tversky (1979) Prospect Theory의 손실영역 risk-seeking 곡선에서 도출 |
| 초과손실 (MAE) | John Sweeney, *Maximum Adverse Excursion* (1996) — 트레이딩 실무서 개념. 학술지가 아니라 실무서 |

**없는 것: 이 네 신호를 0.35/0.30/0.20/0.15로 합성하라는 논문.** 그런 합성 점수 체계는 발표된 적이 없다 — 이건 이 프로젝트 고유의 설계다.

**정당화 가능한 유일한 방법(명세서에 이미 명시):** "명백한 손절실패" 거래를 20개 이상 라벨링 → (확대, 지연, 물타기, 초과손실) 4개를 feature로 로지스틱 회귀 → 계수를 가중치로 교체. 그 전까지는 `config.py`에 분리해둔 가설값으로 운용한다.

### 참고 문헌

- Shefrin, H., & Statman, M. (1985). *The Disposition to Sell Winners Too Early and Ride Losers Too Long: Theory and Evidence.* The Journal of Finance, 40(3), 777-790. [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1985.tb05002.x)
- Odean, T. (1998). *Are Investors Reluctant to Realize Their Losses?* The Journal of Finance, 53(5), 1775-1798. [PDF](https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/areinvestorsreluctant.pdf)
- Locke, P. R., & Mann, S. C. (2005). *Professional Trader Discipline and Trade Disposition.* Journal of Financial Economics, 76(2), 401-444. [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0304405X0400203X)
- Kahneman, D., & Tversky, A. (1979). *Prospect Theory: An Analysis of Decision under Risk.* Econometrica, 47(2), 263-291.
- Break-even effect / get-evenitis 해설: [Larry Swedroe — How Your Brain's "Break-Even" Bias Creates Mispricings](https://larryswedroe.substack.com/p/how-your-brains-break-even-bias-creates)
- Sweeney, J. (1996). *Maximum Adverse Excursion: Analyzing Price Fluctuations for Trading Management.* Wiley. 개념 설명: [Maximum Adverse Excursion — Measure Your Stop Risk](https://journalplus.co/metrics/maximum-adverse-excursion/)

---

## 7. 데이터 / 검증 현황

| 항목 | 상태 | 위치 |
|---|---|---|
| 더미 정답지 5개 (A~E) | 5/5 통과 | [`data/dummy.py`](data/dummy.py), [`tests/test_dummy.py`](tests/test_dummy.py) |
| 가상 거래 20건 (실제 KOSPI 분봉 가격 기반) | 검증 완료 | [`data/virtual_trades.py`](data/virtual_trades.py) |
| 실제 분봉 데이터 (798종목, 245거래일) | `analysis/data/min1/*.parquet` (git 미추적, 로컬 전용) | [`data_loader.py`](data_loader.py) |
| Streamlit 데모 | `streamlit run app_streamlit.py` | [`app_streamlit.py`](app_streamlit.py) |

### 더미 정답지 요약

| 거래 | 판정 | score | 핵심 검증 포인트 |
|---|---|---|---|
| A | 지연형 | 0.532 | 이탈 후 6영업일 버팀 + 손실 확대 |
| B | 물타기형 | 0.469 | **핵심 함정**: 최종 손실(-2.8%)은 손절선보다 작지만 물타기 행동으로 잡힘 (확대=0, 물타기=1.0) |
| C | 정상손절 | 0.107 | 선 닿고 1영업일 만에 끊음 → 거의 0점 |
| D | 수익거래 | 0.000 | 안전장치 |
| E | lucky_hold | 0.000 (+`lucky_hold`) | MAE -20% 갔다 익절 |

---

## 8. 아직 안 된 것 (다음 단계)

| 항목 | 내용 | 블로커 |
|---|---|---|
| 거래내역 파서 | 증권사/키움 CSV → `Transaction` 변환 | CSV 포맷 확정 필요 |
| 가중치 캘리브레이션 | 라벨링된 실거래 → 로지스틱 회귀 → `config.py` 가중치 교체 | 라벨 데이터 20개 이상 필요 |
| 에이전트 오케스트레이터 | 진입/심리 에이전트와 점수 통합, 대표 문제 선정 | 다른 두 에이전트 구현 필요 |
| 수정주가 | 실데이터 연동 시 액면분할·배당락 보정 필수 | 키움 REST 옵션 확인 |
