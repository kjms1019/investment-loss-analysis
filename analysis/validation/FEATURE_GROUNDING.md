# 예측기 피처 논문 근거 (Feature Grounding)

> 대상: 예측기(Predictor)의 **진입오류**·**손절실패** 피처 테이블.
> 목적: 각 피처가 "왜 손실/잘못된 진입을 예측하는가"를 **피어리뷰 논문**에 앵커링한다.
> 동반 문서: 분류기(classifier)의 행동편향 임계값 근거는 [THRESHOLD_GROUNDING.md](./THRESHOLD_GROUNDING.md).

## 핵심 요약 (발표용)

- **기술적·모멘텀·앵커링·관심도·변동성 피처군은 Top-3 저널 논문으로 강하게 근거화**된다.
- 다만 두 가지 큰 caveat를 **정직하게** 명시해야 한다:
  1. **빈도 불일치(granularity)** — 모든 논문이 일/월/연 단위인데 우리는 **1분봉**. 논문은 *왜(mechanism)*를 정당화할 뿐, 분 단위 calibration을 보증하지 않는다.
  2. **방향 불일치(direction)** — "고점 근처/거래량 급증"을 다룬 논문(George-Hwang 2004 등)은 사실 **추세 지속(continuation)·프리미엄**을 보고하지, "고점 매수 = 손실"을 입증하지 않는다. 손실 프레이밍은 **단기 반전(Jegadeesh 1990) + 관심도 매수(Barber-Odean 2008)** 에 기댄다.
- **손절실패 피처 3개 중 2개는 논문 근거가 약하거나 없다** — `mae_ratio`(실무 문헌만), `breach_time_frac`(근거 없음). 정직하게 "엔지니어링 휴리스틱"으로 표기.

---

## 진입오류(Entry-Error) 피처

| 피처 | 정전(canonical) 논문 | 한 줄 근거 | 판정 |
|---|---|---|---|
| `rsi_14` | **Lo, Mamaysky & Wang (2000)**, "Foundations of Technical Analysis," *J. Finance* 55(4):1705-1765, DOI [10.1111/0022-1082.00265](https://onlinelibrary.wiley.com/doi/abs/10.1111/0022-1082.00265) | 기술적 지표가 무조건부 수익분포 대비 "incremental information"을 갖는다고 실증 → 과열(RSI) 신호의 정보가치 뒷받침 | ⚠️ 간접근거: 논문은 차트 패턴(헤드앤숄더 등)을 검증, **RSI 자체는 메커니즘 외삽**. 일봉 미국주식 |
| `range_position_20/60`, `entry_vs_high20/60` | **George & Hwang (2004)**, "The 52-Week High and Momentum Investing," *J. Finance* 59(5):2145-2176, DOI [10.1111/j.1540-6261.2004.00695.x](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2004.00695.x) · **Della Vedova, Grant & Westerholm (2023)**, *JFQA* 58(7):2852-2889 ([link](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/investor-behavior-at-the-52week-high/5D1C7CA21396521F3B41D91B06A25BE1)) | 고점 근접도가 미래수익 예측력에서 과거수익을 압도하며, 투자자가 고점을 **앵커(기준점)** 로 삼음. Della Vedova: 실제 개인투자자가 52주 고점에서 행동을 급변(앵커링) | ⚠️ **방향 불일치**: George-Hwang은 고점 근처 **지속(continuation)** 을 보고(손실 아님). 52주(연)·일봉 vs 20/60분. 앵커링 *구조*만 근거, 손실 프레이밍은 Barber-Odean과 병행 |
| `ret_5m/20m/60m/120m` | **Jegadeesh (1990)**, "Evidence of Predictable Behavior of Security Returns," *J. Finance* 45(3):881-898, DOI [10.1111/j.1540-6261.1990.tb05110.x](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1990.tb05110.x) · (참고) Jegadeesh & Titman (1993), *J. Finance* 48(1):65-91 | **단기 반전**: 월수익의 1차 자기상관이 유의하게 음(+급등 뒤 반전) → "급등 직후 진입 = 진입오류"의 정직한 근거 | ⚠️ **모멘텀 vs 반전 주의**: J&T(1993) 모멘텀은 **중기(3-12개월) 지속**이라 분 단위 외삽은 과장. 단기엔 **반전(Jegadeesh 1990)** 이 맞는 근거. 월 단위 |
| `accel` | **De Bondt & Thaler (1985)**, *J. Finance* 40(3):793-805, DOI [10.1111/j.1540-6261.1985.tb05004.x](https://doi.org/10.1111/j.1540-6261.1985.tb05004.x) · **Barberis, Shleifer & Vishny (1998)**, *JFE* 49:307-343 ([PDF](https://nicholasbarberis.github.io/bsv_jnl.pdf)) · **Bali, Cakici & Whitelaw (2011)** "Maxing Out," *JFE* 99(2):427-446 ([PDF](https://pages.stern.nyu.edu/~rwhitela/papers/max%20jfe11.pdf)) | 과민반응(overreaction)·representativeness로 급변에 추종. Bali-Cakici-Whitelaw: 최근 **극단적 수익(MAX) 종목이 이후 -1%/월** 저조 → 급등 추종이 부진한 후속수익 예측 | ⚠️ **메커니즘 외삽**: DBT/BSV는 다년·월 단위. MAX는 월 단위 단면, 피처에 직접 들어있진 않음(유추 근거) |
| `entry_vs_ma20`, `ma_20_slope` | **Brock, Lakonishok & LeBaron (1992)**, "Simple Technical Trading Rules...," *J. Finance* 47(5):1731-1764, DOI [10.1111/j.1540-6261.1992.tb04681.x](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1992.tb04681.x) | 이동평균 대비 가격 위치가 수익 예측 정보를 가짐(랜덤워크/GARCH 귀무가설 기각) → `entry_vs_ma20` 근거 | ⚠️ **로버스트성 주의**: Sullivan-Timmermann-White(1999)는 1986년 이후 data-snooping 보정 시 수익성 소멸. `ma_20_slope`는 추세 논리로 **간접근거만**. 일봉 DJIA, pre-cost |
| `vol_20/60` | **Ang, Hodrick, Xing & Zhang (2006)**, "The Cross-Section of Volatility and Expected Returns," *J. Finance* 61(1):259-299, DOI [10.1111/j.1540-6261.2006.00836.x](https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.2006.00836.x) | 고변동성(특이변동성) 종목이 이후 "abysmally low" 수익 → 고변동 국면 진입의 위험성 뒷받침 | ⚠️ **측정·빈도 불일치**: 논문은 월 단위 *특이*변동성(FF3 잔차), 우리는 1분 *총*실현변동성. 동일 *why*, 동일 측정은 아님. 후속연구서 강건성 논쟁(Bali-Cakici 2008 등) |
| `volume_ratio_20` | **Barber & Odean (2008)**, "All That Glitters," *RFS* 21(2):785-818 ([link](https://academic.oup.com/rfs/article-abstract/21/2/785/1607197)) · (메커니즘) Gervais, Kaniel & Mingelgrin (2001), *J. Finance* 56(3):877-919, DOI [10.1111/0022-1082.00349](https://onlinelibrary.wiley.com/doi/abs/10.1111/0022-1082.00349) | 개인투자자는 **관심끄는 종목(비정상 거래량·극단적 1일 수익·뉴스)의 순매수자** — `volume_ratio_20`(비정상 거래량)·`ret_*`(극단수익)에 직접 대응. 개인 특화 최강 근거 | ⚠️ GKM의 "거래량 급증→상승" 주장은 **검증서 기각(0-3)**. GKM은 *가시성(attention) 메커니즘*으로만 인용. 일/주 단위 |

---

## 손절실패(Stop-Loss-Failure) 피처

| 피처 | 근거 | 한 줄 근거 | 판정 |
|---|---|---|---|
| `post_breach_run` | **Odean (1998)**, "Are Investors Reluctant to Realize Their Losses?", *J. Finance* 53(5):1775-1798 · **Shefrin & Statman (1985)**, *J. Finance* 40(3):777-790 · **Kaminski & Lo (2014)**, *J. Financial Markets* 18:234-254 | 처분효과: 투자자가 손실을 실현 못 하고 **손절선을 지나쳐 보유** → 손절 이후 추가 손실 진행을 포착 | ⚠️ 처분효과 자체는 정전(THRESHOLD_GROUNDING의 Odean 1998 앵커와 동일). 단 *이 리서치 라운드에선 미검증* — 본 분류기 근거문서의 Odean 인용 재사용. 일·월 단위 |
| `mae_ratio` (Maximum Adverse Excursion) | **John Sweeney (1996)**, *Maximum Adverse Excursion: Analyzing Price Fluctuations for Trading Management*, Wiley | MAE = 진입 후 최대 불리 움직임. 손실 깊이 관리 개념 | 🚫 **실무 문헌만**, 피어리뷰 논문 아님. "구성개념 출처(Sweeney)"로만 표기하고 학술근거 없음을 명시 |
| `breach_time_frac` | (없음) | 손절선 이탈 시점(보유기간 내 조기/만기) | 🚫 **논문 근거 없음**. 엔지니어링 휴리스틱/탐색적 피처로 정직 표기 |

---

## 검증에서 기각된 주장 (사용 금지)

1. **GKM(2001) "거래량 급증 → 다음 달 상승"** — 3:0 기각. GKM은 *프리미엄*을 보고하지 진입 타이밍 손실 근거가 아님. **가시성 메커니즘으로만** 인용.
2. **Grinblatt & Keloharju (2001) "월 고점/저점이 매매결정에 영향"** — 2:1 기각. 앵커링 1차 앵커로 쓰지 말 것(George-Hwang·Della Vedova로 대체).

## 전체 공통 caveat

1. **빈도 불일치** — 모든 논문 일/월/연 단위, 모델은 1분봉. 논문은 *why*만 정당화.
2. **방향 불일치** — 고점/거래량 논문은 지속·프리미엄을 보고(손실 아님). 손실 프레이밍은 단기반전+관심도매수에 의존.
3. **모멘텀≠반전** — J&T(1993)는 중기 지속. 분 단위 급등엔 단기반전(Jegadeesh 1990)이 정직.
4. **로버스트성** — BLL 기술규칙은 1986년 이후 data-snooping 보정 시 소멸(STW 1999); 특이변동성·MAX 효과는 후기 표본서 약화 논쟁.
5. **손절 피처** — `post_breach_run`은 처분효과로 근거화 가능하나 이번 라운드 미검증(분류기 문서의 Odean 앵커 재사용 필요). `mae_ratio`·`breach_time_frac`은 학술근거 부재.

## 미해결 질문 (후속)

- Odean(1998)/Shefrin-Statman(1985)/Kaminski-Lo(2014)를 working DOI로 독립 재검증해 `post_breach_run` 앵커 확정.
- MAE의 피어리뷰 학술 출처 존재 여부(없으면 Sweeney 실무문헌으로 정직 표기 유지).
- 한국 개인투자자/1분봉 마이크로구조 대상 **고빈도 실증연구**로 빈도 gap 축소 가능성.

---

## 다중공선성 점검 (VIF) — 2개 피처 제거

피처 간 공선성을 VIF로 점검(min1 798종목·손실거래 3,988건 샘플)한 결과, **완전 선형종속 1건과 VIF>10 1건**을 발견해 제거했다.

### 발견
- 🔴 **`accel` = `ret_5m` − `ret_20m`** (정확한 차분, [label_pipeline.py](../label_validation/label_pipeline.py) `entry_features_window`) → `accel`·`ret_5m`·`ret_20m` 모두 **VIF=∞**(완전 공선성). 표준화 후에도 종속 유지.
- 🔴 **`entry_vs_ma20`** ↔ `ret_20m`(r=0.84)·`ret_5m`(r=0.78) → **VIF 10.98** ("이평 위 진입 = 최근 급등 진입"으로 같은 정보).
- 🟡 잔여: `entry_vs_high20/60`(서로 0.72), `vol_20/60`(0.78) → VIF 5~5.5. 20분/60분 윈도우라 시간대 정보가 달라 **유지**.

### 제거 전/후 (분류기 LogReg, 5-fold)

| 단계 | 피처수 | AUC | inf VIF | 최대 VIF | VIF≥10 |
|---|---:|---|---:|---:|---|
| 전체 | 18 | 0.8361 | 3 | 10.98 | accel, ret_5m, ret_20m, entry_vs_ma20 |
| −accel | 17 | 0.8361 | 0 | 10.98 | entry_vs_ma20 |
| **−accel −entry_vs_ma20 (채택)** | **16** | **0.8365** | **0** | **5.46** | **없음** |

### 결론
- **성능 손실 0** (오히려 +0.0004). 핵심 근거피처 계수 **불변**: `mae_ratio`(−7.03)·`post_breach_run`(2.78)·`breach_time_frac`(0.92). → 공선성은 모멘텀 블록에만 있었고 실제 판단 신호는 영향 밖.
- **LogReg 분류기에서 특히 중요**: "계수=근거"가 핵심이므로 완전 공선성은 계수를 임의 분산시켜 해석 신뢰성을 해친다. 제거로 모멘텀 계수가 정상화됨(`ret_5m` 0.076→0.121, 가짜 `accel` 계수 0.064 제거).
- 배포 모델 재학습 완료: 16피처, **5-fold AUC 0.839** ([artifacts/entry_stop_clf.meta.json](../classifier/artifacts/entry_stop_clf.meta.json)).
- `entry_features_window`는 두 값을 계속 계산(에이전트 별칭 `entry_vs_ma20_pct` 호환) — **모델 입력 `FEATURES`에서만 제외**.

---

*생성: deep-research 하니스(소스 21개 페치 → 주장 25개 3표 적대적 검증 → 23 확정/2 기각). 검증 미포함 인용(손절군)은 위 판정란에 명시. 다중공선성 절은 statsmodels VIF + sklearn LogReg 5-fold 실측.*
