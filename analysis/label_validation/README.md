# 진입오류 / 손절실패 — 분류기 & 예측기 설계·검증

손실 거래를 **진입오류(entry_error)** / **손절실패(stop_loss_failure)** 로 가르고,
같은 실수를 반복하려 할 때 **실시간 예측·경고**하는 멀티에이전트의 ML 코어.

라벨링·모델식·임계값·자기반복(순환) 네 문제를 실데이터(코스피 1년 1분봉)로 답한 **설계 + 검증 + 결과** 전부를 담는다.

---

## 1. 전체 아키텍처

```
[분석단]  사용자 전체 거래(과거~오늘)
  → loss-screener : 손실 거래만 선별
  → 결과신호/피처 추출
  → 분류기(전체경로 피처) : 손실거래마다 entry_error / stop_loss_failure 라벨 부여   ★teacher
  → 빈도·손실금 집계 → 총괄이 "뭘 먼저 볼까?" 질문 → 도메인 에이전트 분석 → 반복
  → 성향·반복패턴 리포트 저장

[예측단]  오늘 일어나는 이벤트를 현시점 정보만으로 예측 (분류기 라벨이 정답)   ★student
  · 진입오류 예측기 : 오늘 '매수' 순간      → 진입맥락 피처
  · 손절실패 예측기 : 오늘 '보유종목 폭락' 순간 → 현재 포지션 피처
```

**분류기 = 선생(teacher), 예측기 = 제자(student)** 의 label distillation 구조.
분류기는 거래가 끝난 뒤라 **전체경로 정보**를 다 보고 라벨을 만들고,
예측기는 그 라벨을 정답 삼아 **그 순간 알 수 있는 정보만**으로 따라 배운다.

---

## 2. 핵심 설계 원칙

| 원칙 | 내용 |
|---|---|
| **라벨 ↔ 피처 분리** | 라벨 = 결과(사후) 신호 / 피처 = 원인·상태. 같은 신호를 양쪽에 쓰면 자기반복(순환) → 금지 |
| **피처 범위 = 역할** | **분류기 = 전체경로 피처**(사후 포함, 라벨축 제외) / **예측기 = 현시점 피처**(미래 없음, look-ahead 금지) |
| **임계값은 군집이 결정** | 손으로 0.7 안 박음. 단일 고정컷은 §4에서 기각됨 |
| **정답은 군집이 생성** | 실거래엔 라벨이 없음 → 결과신호 군집(K=2)이 라벨 생성기. 지도학습의 타깃 공급 |

라벨 정의축: `loss_early_ratio`(손실이 초반에 몰린 정도), `trough_time_frac`(최저점 시점).
이 두 축은 **라벨을 정의**하므로 **피처에서는 항상 제외**한다(순환 방지).

---

## 3. 분류기 설계 흐름

```
① 랜덤 데이터 + 단일 고정컷(0.7) 검증     → 기각 (경계가 보유기간 따라 미끄러짐)
② 랜덤 데이터 + 2축 군집화               → BIC 2성분 우세·실루엣 0.56 = 구조 실재 (축 정당성)
③ ②의 두 축으로 라벨 생성 → ML 분류기     → 피처를 '전체경로'로 쓰면 성능 확보
   (재합성 검증셋은 파이프라인 작동 입증용 — §6)
```

- **데이터 = 축 정당성**(②) / **이론(design-brief·논문) = 축 의미**(진입오류/손절실패 명명). 둘을 분리.
- 단일 ML 모델로 끝내지 않고 ①②를 거치는 이유 = "왜 이 두 축?"에 데이터 근거를 대기 위함.

---

## 4. ① 단일 고정컷은 부적절 — `step1_threshold_check.py`

보유기간 구간별로 `loss_early_ratio` 분포의 데이터-경계를 GMM+부트스트랩으로 검증:

| 구간(보유분) | BC | 데이터 경계 | 95% CI | 0.7? |
|---|---|---|---|---|
| scalp(10~60) | 0.80 | 0.001 | [0.001,0.001] | OUT |
| intraday(60~380) | 0.58 | 0.001 | [0.001,0.001] | OUT |
| short_swing(380~1900) | 0.36 | 0.213 | [0.026,0.293] | OUT |
| long_swing(1900~7600) | 0.21 | 0.444 | [0.387,0.499] | OUT |

→ **경계가 0.001→0.44로 미끄러지고, 0.7은 모든 구간에서 CI 밖.** 단일 고정컷 불가 확정.

---

## 5. ② 2축 군집 = 축 선택 근거 — `step2_cluster_axes.py`

실 손실거래를 두 축(`loss_early_ratio`, `trough_time_frac`)으로 군집(GMM K=2):

- 실루엣 **0.56** (이봉 기준선 0.555 상회), BIC **1성분 31745 → 2성분 26981** (2성분 명백 우세)
- → 두 축에 2-그룹 구조가 **실재**. 이게 §6 설계합성을 이 축으로 하는 정당성.
- (`post_breach_run`은 `loss_early_ratio`와 중복이라 제외 시 실루엣 0.46→0.56 — 정당한 피처선택)

---

## 6. ③ 분류기 성능 — 피처 범위가 핵심

### `step3_classifier_real.py` (실/랜덤, 진입피처) + `step3b_classifier_designed.py` (설계셋)

데이터(랜덤 vs 설계재합성) × 피처(진입 vs 전체) 비교 (5-fold AUC, 6000표본):

| 데이터 | 피처 | logreg | rf |
|---|---|---|---|
| 랜덤 (재합성 없음) | 진입피처 | 0.510 | 0.505 |
| 랜덤 (재합성 없음) | **전체피처** | **0.836** | **0.863** |
| 설계 재합성 | 진입피처 | 0.967 | 0.963 |

**핵심 발견 3가지:**
1. **0.5의 원인은 "랜덤"이 아니라 "진입피처"였다** — 데이터 그대로 두고 피처만 전체로 바꾸니 0.51→0.84. **재합성 없이도** 극복.
2. **0.97(설계셋)은 피처가 아니라 "구조 주입" 덕** — 진입피처로도 0.97 나옴(주입 효과).
3. → **분류기 = 전체경로 피처 + 군집라벨.** 재합성은 분류기엔 선택사항(검증·예시용).

### 설계 검증셋(`step3b`) — 파이프라인 작동 입증

설계셋(정답 구조 주입)에서: 군집↔주입유형 정확도 **0.979**(ARI 0.916), 분류기 AUC **0.967**(logreg)/0.963(rf).
→ 같은 코드, 데이터만 구조 있게 바꾸니 0.51→0.97. **"막힌 건 데이터지 파이프라인 아님".**

> ⚠️ 설계셋은 **랜덤 아닌 '설계된 검증셋'**. 파이프라인 작동 검증까지만 — 임계값·실제 시장구조 증명엔 불가(순환).

### 전체피처에 약간의 거품
전체피처(mae_ratio·breach_time·post_run)도 라벨축도 같은 가격경로에서 나와 일부 상관 존재.
진짜 **행동피처**(물타기 avg_down, 손절선 뚫고 버팀)는 실거래 로그에만 → 실거래 들어오면 더 의미있게 상승할 자리.

---

## 7. 예측단 — 두 예측기 (분류기 라벨이 정답)

### ④ 진입오류 예측기 — `step4_predictor.py` (매수 이벤트, 진입맥락 피처)
### ⑤ 손절실패 예측기 — `step5_stop_predictor_live.py` (보유 폭락 이벤트, 현재 포지션 피처)

손절실패 예측은 보유 중 손절선(-3%) **첫 돌파 순간의 포지션 스냅샷**(미실현손실·보유시간·최근낙폭·고점대비·진입후상승)을 쓴다. 전부 그 순간까지만 — look-ahead 없음.

| 모델 | 이벤트 | 피처 | 랜덤 AUC | 설계 AUC |
|---|---|---|---|---|
| 분류기 | 거래 종료 후 | 전체경로 | 0.85 | 0.97 |
| 진입오류 예측기 | 오늘 매수 순간 | 진입맥락 | 0.51 | 0.97 |
| 손절실패 예측기 | 오늘 보유폭락 순간 | 현재 포지션 | **0.68** | 0.98 (rf) |

**해석:** 이벤트 시점의 정보량이 성능을 가른다.
- 진입오류 예측(매수) = 미래 전혀 모름 → 랜덤 0.51(동전던지기)
- 손절실패 예측(폭락) = 이미 손실 진행 중, 손절선을 **언제·어떻게** 뚫었나가 보임 → 랜덤 0.68
- 셋 다 설계셋(구조 주입)에선 0.97~0.98로 **구조 작동 입증**. **진짜 성능은 실거래에서 판가름.**

---

## 8. 정직성 경계 (발표 시 필수)

- 설계셋은 **'설계된 검증셋'이라 명시.** 랜덤 아님. **파이프라인 작동 검증까지만.**
- 설계셋으로 **임계값·실제 시장구조는 증명 불가**(순환). 축 정당성은 ②(실데이터)가 제공.
- **데이터 = 축 정당성 / 이론(design-brief·논문) = 축 의미.**
- 모든 합성 결과는 **실거래 매매내역 확보 시 재검증** 대상.

---

## 9. 구조

```
label_pipeline.py              공유 코어 — 결과신호·진입맥락 피처·실 min1 샘플러·군집·설계합성
step1_threshold_check.py       ① 단일 고정컷(0.7) 검증 + 보유기간 sweep(--sweep)
step2_cluster_axes.py          ② 실데이터 2축 군집 (축 선택 근거)
step3_classifier_real.py       ③ 실/랜덤 분류기 (진입피처 → 데이터 한계)
step3b_classifier_designed.py  ③' 설계 검증셋 (파이프라인 작동)
step4_predictor.py             ④ 진입오류 예측기 (매수 이벤트, 진입맥락 피처)
step5_stop_predictor_live.py   ⑤ 손절실패 예측기 (보유폭락 이벤트, 현재 포지션 피처)
```

런타임 모듈: [`analysis/classifier`](../classifier/) — 학습된 분류기를 서비스가 import해 호출.
예측기 스키마: [`analysis/predictor`](../predictor/) — `EntryContext`(매수)/`PositionSnapshot`(보유) 두 모드.

핵심 빌딩블록(`label_pipeline.py`):
- `outcome_signals()` — loss_early_ratio, trough_time_frac, post_breach_run (라벨용)
- `entry_features()` — rsi/range_position/momentum/vol/volume 등 15개 (예측·진입피처)
- `sample_signals_only()` / `sample_with_features()` — 실 min1 손실거래 샘플러
- `cluster_labels()` — 다중신호 GMM(K=2) → entry_error/stop_loss_failure + 품질지표
- `generate_designed()` / `_designed_path()` — 정답 구조 주입 합성 생성기

---

## 10. 데이터 준비 (다른 브랜치/PC)

분봉 데이터(~1GB)는 git에 안 올라간다(`.gitignore: /analysis/data/`). 배포처 = GitHub Release.

- **A. Release zip** — `kospi_min1_1y_*.zip` 다운로드 → `analysis/data/`에 압축 해제 → `analysis/data/min1/{code}.parquet` 798개.
  ```bash
  unzip kospi_min1_1y_20260623.zip -d analysis/data/
  ```
- **B. 재수집** — `python analysis/collector/collect_min1.py` (키움 API, `.env` 키 필요).

## 11. 실행

```bash
python analysis/label_validation/step1_threshold_check.py --sweep
python analysis/label_validation/step2_cluster_axes.py
python analysis/label_validation/step3_classifier_real.py
python analysis/label_validation/step3b_classifier_designed.py
python analysis/label_validation/step4_predictor.py
python analysis/label_validation/step5_stop_predictor_live.py
```

산출물(JSON)은 `analysis/data/_label_validation/` (gitignored).
의존성: numpy, pandas, scikit-learn, scipy (`analysis/requirements.txt`).
```
