# 분류기 임계값 검증 — 문제 정의 · 접근 · 리서치 결과

> 심리·과매매/손실 분류기(`psych_agent/focus.py`, `orchestrator/router.py`)가 쓰는
> 임계값(매직넘버)을 **"실제로 정당한 숫자인가"** 관점에서 검증하기 위한 작업 기록.
> 작성: 2026-06-25. 관련 코드: `analysis/validation/` (검증 하니스, younghyun 브랜치).

---

## 1. 문제 — 왜 지금의 검증이 "실제수치"가 아닌가

기존 검증 하니스(`cluster_validate.py` + `synth_loss_data.py`)는 합성 데이터로
라우터 정확도·KMeans 군집화를 돌린다. 코드 품질·구현은 정확하지만 **순환성(circularity)**
때문에 "분류기가 작동한다"의 증거가 되지 못한다:

1. **공유 정의(shared definition)** — 합성기가 라벨을 만들 때 쓰는 규칙과
   라우터가 분류에 쓰는 규칙이 *같은 개념*. 라벨러와 채점자가 동일인.
2. **쉬운 케이스만 존재(separable by construction)** — 합성 데이터가 전부 결정경계에서
   먼 "교과서 케이스"라, 어떤 멀쩡한 분류기도 ~99%가 나와 정확도 숫자가
   **분류기 품질에 대한 정보를 주지 못함**.

→ 합성 데이터로 증명 가능한 건 (a) 배관 연결, (b) 검출기가 설계 패턴에 발화함뿐.
**"라우터가 실제 유저에서 잘 분류한다"는 증명 불가.**

추가 문제: 실제 라벨 데이터 확보 불가(손라벨 골드셋 불가) → 외부검증 경로가 막힘.

---

## 2. 접근 — 어떻게 풀기로 했나

여러 대안(하드케이스+베이스라인 주입, 결과기반 보정 등)을 검토한 끝에,
**발상 전환**으로 가장 방어력 강한 경로를 택함:

> **분류기를 "검증"하는 대신, 룰의 임계값을 "정당화/보정"한다.**
> 라벨의 출처를 *우리*가 아니라 *피어리뷰 논문*으로 삼으면 순환성이 끊긴다.

- 룰베이스 분류기의 숫자들(`30분`, `-7%`, `회전율 2.5`, `PGR−PLR 0.05`, `0.7`)은
  논문 상수일 뿐, 코스피·연도마다 달라야 할 수 있다.
- 각 피처마다 **정전(canonical) 논문의 정의·수치를 ground-truth로** 삼아
  "논문 정의 ↔ 우리 1분봉 근사 일치도"를 측정 → 인용 가능한 실측 숫자.
- 논문 정전값이 없는 피처는 정직하게 분리해 **결과앵커(outcome/regret 기반)** 로 보정.

**핵심 함정 주의**: 라벨을 "튜닝하려는 그 규칙"으로 만들면 내 가정을 되찾을 뿐이다.
반드시 라벨을 *독립적인 것*(논문 정의 / 실제 가격 기반 결과)에 앵커링해야 한다.

검증 방법론: 임계값별 ROC-AUC(임계값 무관 피처 판별력) → Youden's J로 운영점,
연도/변동성 레짐별 최적점 이동(코스피·연도 가설의 직접 증거), 베이스라인 대비 보고.

---

## 3. 리서치 결과 — 무엇을 찾았나

딥리서치 2라운드(총 204 에이전트, 40소스, 46 claim 적대검증, 1차출처 우선).

### 3.1 피처별 마스터 매핑표

| 피처 | 우리 코드값 | 최선의 논문 앵커 | 논문 granularity | 판정 |
|---|---|---|---|---|
| **처분효과** | `PGR−PLR > 0.05` | Odean(1998): PGR=0.148, PLR=0.098, **차=0.050** (t>35) | 일 단위 계좌기록 + CRSP 일봉 | ✅ **정확히 일치**. 단 `>`→`>=` |
| **과매매** | 연회전율 `2.5`, 주석 "258%" | **FINRA 18-13: 회전율≥6 + cost/equity≥20%**; Barber-Lee-Liu-Odean: day-trade=당일왕복 | 연간 계좌 / **틱·일중** | ⚠️ 250%/258% 무근거, **FINRA 6배가 진짜 앵커** |
| **리벤지/물타기** | 30분+포지션확대+재손실 | B-D&H(2012) 매도·**매수 V자**(물타기 실재); Coval-Shumway 오후위험 16%↑ | 일봉 / 틱 | ❌ 시간창·배수 **정전값 없음**, 피처 존재는 입증 |
| **손절실패** | `-7%` + 2영업일 | **없음**(% 학술근거 0). Kaminski-Lo 조건부; Richards 승자 160%↑ 매도 | 월간 / 일봉 | ❌ -7% 무근거 |

### 3.2 피처별 상세

**처분효과 (Disposition Effect) — 논문앵커 성립 🏆**
- Odean(1998) *"Are Investors Reluctant to Realize Their Losses?"* (J.Finance):
  `PGR = 실현이익/(실현이익+미실현이익)`, `PLR = 실현손실/(실현손실+미실현손실)`,
  기준점=평균매입가, 매도일에만·2종목 이상 포트에서 계산.
- 보고값: 집계 PGR=0.148, PLR=0.098, **차=0.050** (t>35) / 계좌단위 차=0.21 (PGR 0.57, PLR 0.36).
  → 우리 `0.05`는 **집계값과 정확히 일치**. 단 경계값이 딱 0.05라 `>=` 써야 배제 안 됨.
- 우리 대체측정(보유기간 1.5배↑ + 보유중 익절)은 *보유시간 비대칭*이라 PGR/PLR(*실현율 비대칭*)과
  다른 양. 계좌단위 PGR/PLR 비 0.57/0.36≈1.58이 우연히 "1.5배"와 맞물림.
- Frazzini(2006) capital-gains-overhang은 가격기반 proxy로 또 다른 구성.

**과매매 (Overtrading / Churning) — 하드 넘버 새로 확보 🎯**
- **FINRA Notice 18-13**(규제 정량 기준): 연 **회전율(turnover ratio) ≥ 6** = 과당매매 추정,
  **cost-to-equity ratio ≥ 20%**. 맥락 따라 3~5, 심하면 2.
  → 법적·판례 수치라 우리 "과매매 임계"의 가장 단단한 앵커.
- Barber & Odean(2000): 평균 가구 회전율 **~75%/년**(우리 250%와 안 맞음).
  "258%"는 **어느 논문에도 없는 조작값**(1라운드에서 refuted). (2001) 최고 그룹(독신남)도 ~85%.
- Barber-Lee-Liu-Odean 대만 데이트레이더: day-trade = "**같은 종목 같은 날 매수·매도**",
  **틱 데이터**(1992–2006) → 우리 1분봉이 직접 구현 가능한 정의·해상도.
- 한국: 개인 연 회전율 **~1,600%/년**(Kim&Kim 2022, 2020년) → 미국 20배. US 임계 그대로 쓰면 안 됨.
- 해석 주의(Bonaparte et al 2019): 거래비용 있는 합리적 모델도 고회전+저수익 재현 가능
  → 고회전율은 "행동 플래그"지 비합리성의 증명 아님.

**리벤지/손실추종/물타기 (Revenge / Averaging-down) — 피처는 입증, 수치는 없음**
- Ben-David & Hirshleifer(2012) *"Are Investors Really Reluctant to Realize Their Losses?"*:
  매도확률이 손익에 **V자**. 결정적으로 **손실 종목을 더 사는 것(averaging down)에서도 같은 V자**
  → *물타기·doubling down은 실증된 실제 현상*. 일봉, 2,150만 관측.
- Coval & Shumway(2005): 오전 손실 트레이더가 오후에 평균이상 위험 **16% 더** 감수
  (31.2% vs 27%), CBOT 틱. **방향만**, 30분/배수 아님.
- **Imas(2016) 이론충돌**: 위험추구는 **미실현(paper) 손실** 뒤, **실현(청산) 손실** 뒤엔
  위험**회피**. 우리 검출기는 *청산손실 후 재진입*에 발화 → Imas가 위험회피 예측하는 케이스.
  → "averaging down(손실종목 추가매수, 미실현 상태)"으로 재정의 권장.
- 도박 loss-chasing 문헌: within-session 손실후 베팅확대 정의는 있으나 **합의된 수치 임계 없음**.
- 결론: "**30분**", "**포지션 확대 배수**"는 어느 논문도 구체값을 주지 않음 = 엔지니어링 선택.

**손절실패 / 손실보유 (Failure to cut losses) — % 근거 끝까지 0**
- "-7%/-8%"는 O'Neil CANSLIM 실무 휴리스틱, **학술 검증 0**.
- Kaminski & Lo(2014): 손절 효과는 **수익과정에 조건부** — 랜덤워크 하에선 항상 기대수익 감소,
  모멘텀 하에서만 가치. **보편적 % 임계 없음**. 실증은 **월간** 빈도(단기일수록 효과 最弱).
- Richards et al(2017): 처분효과 Cox 생존분석, 이익 포지션이 손실보다 **160% 더 매도**됨(일봉).
- → 1분봉 -7% 돌파를 "실수"로 라벨링하는 건 이론적 무근거. 다일(multi-day) 구간에서만 평가 타당.

### 3.3 Granularity 분석 (중요한 반전)

모든 처분효과·손절 논문은 **일/월 단위**, 1분봉 intraday 연구는 없음 — 하지만 gap이
"우리가 너무 미세해서 나쁨"으로 균일하지 않다:

| 편향 | 논문 빈도 | 우리(1분봉) 대비 |
|---|---|---|
| 처분효과(Odean) | 일 계좌기록 + 일봉 | 우리가 더 미세 (일단위 집계로 재현 가능) |
| 물타기(B-D&H) | 일봉 | 우리가 더 미세 |
| **데이트레이딩(대만)** | **틱/일중** | ✅ **우리와 일치** |
| 오전→오후 위험(Coval-Shumway) | 틱/일중 | ✅ 가까움 |
| 손절(Kaminski-Lo) | **월간** | 우리가 극단적으로 더 미세 |

→ **일중 피처(과매매·리벤지)는 우리 1분봉이 오히려 올바른 해상도**.
처분효과·손절만 "논문 일/월 vs 우리 분"이라 mismatch. 발표 시 이를 구분.

---

## 4. 검증셋 설계 결론 — 피처마다 ground-truth 출처를 분리

| 피처 | 검증셋 ground-truth 전략 | 성격 |
|---|---|---|
| **처분효과** | 실데이터에서 **진짜 PGR/PLR 계산**(Odean 정의). 1분봉을 일단위 집계해 재현 | 🏆 논문앵커(최강) |
| **과매매** | 회전율·당일왕복 빈도 계산 → **FINRA 6배** 기준 + 코스피 분포 백분위 | 규제앵커 + 데이터보정 |
| **리벤지/물타기** | "손실종목 추가매수"로 재정의 + **결과앵커**(forward-return) | 휴리스틱 + 결과 |
| **손절실패** | **regret 결과앵커**(반사실 손절가 대비). **다일 구간**에서 평가 | 결과앵커 |

산출물은 단일 매직넘버가 아니라 **곡선/표면**(임계값별 AUC·정확도, 레짐별 최적점 이동) +
베이스라인(다수결/랜덤/단일피처/ablated) 대비 격차.

---

## 5. 코드에서 즉시 고칠 것 (`psych_agent/config.py`)

1. `overtrade_annual_turnover` 주석의 **"258%"는 조작값 → 삭제**. Odean 평균은 75%지 250% 아님.
   과매매 근거를 **FINRA 회전율 6배**로 교체.
2. `disposition_min_gap`: `>` → **`>=`** (Odean 정전값이 정확히 0.05라 `>`면 배제됨).
3. 리벤지 검출기에 **Imas/averaging-down 주의 주석** 추가
   (실현손실 후 재진입 가정은 문헌과 충돌; 미실현 물타기로 재정의 검토).

---

## 6. 다음 단계

1. **(빠른 정리)** `config.py` 위 3건 수정.
2. **(본 작업)** 과매매 검증셋 — 1분봉에서 회전율·당일왕복 계산 → FINRA 6배 라벨 + 코스피 백분위.
   granularity 일치라 transfer gap 논쟁 없음 + "한국 1,600% vs FINRA 6 vs 우리 분포" 발표 그림.
3. 처분효과 검증셋 — 일단위 집계해 진짜 PGR/PLR 계산, 우리 근사와의 일치도 측정.
4. 리벤지·손절 — 결과앵커 프로토타입.

---

## 7. 출처 (1차 우선)

- Odean (1998) "Are Investors Reluctant to Realize Their Losses?" — https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/areinvestorsreluctant.pdf
- Barber & Odean (2000) "Trading Is Hazardous to Your Wealth" — https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/individual_investor_performance_final.pdf
- Barber & Odean (2001) "Boys Will Be Boys" — https://faculty.haas.berkeley.edu/odean/papers/gender/boyswillbeboys.pdf
- Barber, Lee, Liu, Odean — Taiwan day traders — https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trading%20and%20Learning%20110217.pdf
- FINRA Regulatory Notice 18-13 (quantitative suitability / churning) — https://www.finra.org/rules-guidance/notices/18-13
- Ben-David & Hirshleifer (2012) — https://sites.uci.edu/dhirshle/files/2012/07/Are-Investors-Really-Reluctant-to-Realize-their-Losses.pdf
- Coval & Shumway (2005) — https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2005.00723.x
- Imas (2016) "The Realization Effect" (AER) — https://www.aeaweb.org/articles?id=10.1257/aer.20140386
- Frazzini (2006) — https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.2006.00896.x
- Kaminski & Lo (2014) "When Do Stop-Loss Rules Stop Losses?" — https://dspace.mit.edu/bitstream/handle/1721.1/114876/Lo_When%20Do%20Stop-Loss.pdf
- Richards et al (2017) disposition survival analysis — https://www.bayes.citystgeorges.ac.uk/__data/assets/pdf_file/0004/79960/Richards.pdf
- Kim & Kim (2022) Korean retail turnover — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4096525
- Bonaparte, Cooper & Sha (2019, NBER w25838) — https://www.nber.org/system/files/working_papers/w25838/revisions/w25838.rev0.pdf

*딥리서치 원본 로그: `tasks/w2i6h2saw.output`(1R), `tasks/wk7j4es6d.output`(2R).*
