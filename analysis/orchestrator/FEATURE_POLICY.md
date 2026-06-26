# 피처 및 임계값 정책

이 문서는 현재 분류기 후보 점수와 총괄 오케스트레이터 판단 레이어에서 사용하는
피처와 임계값을 정리한 문서입니다.

중요한 전제:

- 아래 수치들은 **최종 검증된 값이 아니라 초기 baseline 가설값**입니다.
- 모든 수치는 향후 실시간 모니터링에서도 재사용할 수 있도록 되도록 **1분봉 기준**으로 정의했습니다.
- 논문은 주로 피처의 방향성과 개념을 뒷받침합니다. `0.85`, `30분`, `1.5pp` 같은 세부 cut-off는 실제 데이터로 검증해야 합니다.

## 1. 현재 아키텍처에서의 역할

```text
손실 거래
  -> 분류기 후보 점수 산출
       entry_error_score
       stop_loss_failure_score
  -> 총괄 오케스트레이터 판단
       primary_agent
       secondary_factors
       route_type
  -> primary 도메인 에이전트 하나만 실행
  -> 주 원인 + 보조 원인을 프로파일 DB에 저장
```

분류기는 더 이상 에이전트를 직접 선택하지 않습니다.

분류기는 `진입오류 점수`와 `손절실패 점수`를 만들고, 총괄 오케스트레이터가 두 점수와 근거를 비교해 주 원인을 선택합니다.

복합 요인은 별도 에이전트를 새로 만들지 않고, 아래처럼 표현합니다.

```text
primary_agent = stop_loss_failure
secondary_factors = [entry_error]
route_type = single_primary_with_secondary
```

즉, 복합 요인은 **새 에이전트가 아니라 총괄 판단 결과의 속성**입니다.

## 2. 진입오류 피처

진입오류 피처는 모두 진입 시점 이전 또는 진입 시점의 1분봉 데이터만 사용합니다.

진입 이후 데이터는 진입 시점 판단에 사용하면 안 됩니다.

| 피처 | 의미 | 현재 baseline |
|---|---|---:|
| `ret_1m` | 진입 직전 1분 수익률 | 피처만 사용 |
| `ret_3m` | 진입 직전 3분 수익률 | 피처만 사용 |
| `ret_5m` | 진입 직전 5분 수익률 | `<= -0.004` |
| `ret_20m` | 진입 직전 20분 수익률 | `>= 0.012` |
| `ma_20_slope` | 최근 20분 이동평균과 이전 20분 이동평균 비교 | `<= -0.002` |
| `range_position_20m` | 최근 20분 고가-저가 범위 안에서 진입 위치 | `>= 0.85`, `>= 0.75` |
| `entry_vs_high20_ratio` | 진입가 / 최근 20분 고가 | `>= 0.992` |
| `entry_vs_ma20_pct` | 진입가와 20분 이동평균의 차이 | `< 0` |
| `rsi_14` | 1분봉 14개 기준 RSI | `>= 68` |
| `volume_ratio_20m` | 진입봉 거래량 / 최근 20분 평균 거래량 | `< 0.80`, `< 0.75` |
| `entry_position_in_bar` | 진입봉 안에서 진입가 위치 | 피처만 사용 |
| `loss_early_ratio` | 보유 초반 20% 구간 손실 / 최종 손실 | `>= 0.70` |

주의:

`loss_early_ratio`는 거래가 끝난 뒤 계산되는 사후 피처입니다.
복기 루프에서는 사용할 수 있지만, 실시간 진입 전 예측에는 사용하면 안 됩니다.

## 3. 손절실패 피처

손절실패 피처는 실시간 모니터링에서도 그대로 쓸 수 있도록 1분봉 기준으로 정의합니다.

현재 과거 복기용 손절실패 에이전트는 일부 일봉 기준 값을 사용합니다.
그래서 배치 분석에서는 임시로 `1영업일 = 390분`으로 변환합니다.
향후에는 실제 1분봉 기준 `breach_timestamp`를 저장하는 방식으로 바꾸는 것이 좋습니다.

| 피처 | 의미 | 현재 baseline |
|---|---|---:|
| `stop_breached` | 1분봉 저가 또는 현재가가 손절선을 이탈했는지 | boolean |
| `breach_minutes` | 최초 손절선 이탈 이후 경과 시간 | `>= 30`, `>= 60` |
| `loss_expansion_pct` | 손절선보다 추가로 커진 손실 폭 | `>= 1.5pp`, `>= 3.0pp` |
| `loss_expansion_ratio` | 현재/최종 손실률 ÷ 손절 기준 손실률 | `>= 1.5`, `>= 2.0` |
| `mae_expansion_pct` | 최대 불리 변동폭이 손절선을 얼마나 넘었는지 | 피처만 사용 |
| `avg_down_count_after_loss` | 손실 중 추가매수 횟수 | `>= 1`, `>= 2` |
| `avg_down_qty_ratio` | 추가매수 수량 / 최초 진입 수량 | `>= 1.0` |
| `failed_recovery_minutes` | 손절선 이탈 후 회복하지 못한 시간 | `>= 30` |

## 4. 총괄 오케스트레이터 판단 정책

총괄 오케스트레이터는 분류기의 두 점수를 보고 최종적으로 하나의 primary agent를 고릅니다.

| 정책값 | 현재 baseline | 의미 |
|---|---:|---|
| `min_route_score` | `0.55` | 특정 에이전트로 보내기 위한 최소 점수 |
| `strong_route_score` | `0.70` | 강한 신호로 볼 점수 |
| `min_score_margin` | `0.15` | 1등과 2등 점수 차이가 이 이상이면 단일 주 원인으로 판단 |
| `ambiguous_margin` | `0.10` | 점수 차이가 이하면 애매한 케이스로 판단 |
| `secondary_factor_score` | `0.45` | 보조 요인으로 저장할 최소 점수 |
| `review_min_score` | `0.45` | 중간 신호로, 검토가 필요한 점수 |
| `abstain_threshold` | `0.35` | 이보다 낮으면 전문 에이전트 실행 보류 |
| `profile_update_min_confidence` | `0.60` | 사용자 프로파일 DB에 반영할 최소 신뢰도 |

판단 예시:

```text
entry_error_score = 0.78
stop_loss_failure_score = 0.32
score_margin = 0.46

-> primary_agent = entry_error
-> route_type = single_primary
```

```text
entry_error_score = 0.68
stop_loss_failure_score = 0.82

-> primary_agent = stop_loss_failure
-> secondary_factors = [entry_error]
-> route_type = single_primary_with_secondary
```

```text
entry_error_score = 0.22
stop_loss_failure_score = 0.18

-> route_type = abstain
-> 전문 에이전트 실행하지 않음
```

## 5. 반드시 검증해야 하는 수치

아래 값들은 논문에서 직접 확정된 값이 아닙니다.

실제 거래 데이터, 1분봉 리플레이, 사람 검수 라벨을 이용해 반드시 검증해야 합니다.

### 5.1 진입오류 쪽 검증 필수

| 검증 대상 | 현재 baseline | 왜 검증해야 하는가 |
|---|---:|---|
| `range_position_20m` | `0.75`, `0.85` | 최근 20분 박스 상단 기준이 너무 민감할 수 있음 |
| `entry_vs_high20_ratio` | `0.992` | 20분 고점 근접 기준이 종목별 변동성에 따라 달라질 수 있음 |
| `ret_20m` | `0.012` | 20분 +1.2%가 과열인지 종목/시장 상황별로 다름 |
| `rsi_14` | `68` | RSI 68은 1분봉에서는 과민하게 반응할 수 있음 |
| `volume_ratio_20m` | `0.75`, `0.80` | 장중 시간대별 거래량 패턴 차이를 반영해야 함 |
| `ma_20_slope` | `-0.002` | 20분 이동평균 기울기 기준은 종목 변동성별 보정 필요 |
| `ret_5m` | `-0.004` | 5분 -0.4% 하락이 진입오류 신호인지 검증 필요 |
| `loss_early_ratio` | `0.70` | 손실 초반 집중도를 주 원인 판단에 쓸 수 있는지 검증 필요 |

### 5.2 손절실패 쪽 검증 필수

| 검증 대상 | 현재 baseline | 왜 검증해야 하는가 |
|---|---:|---|
| `breach_minutes` | `30`, `60` | 손절선 이탈 후 몇 분을 지연으로 볼지 실제 사용자 행동 기준 필요 |
| `loss_expansion_pct` | `1.5pp`, `3.0pp` | 손절선 대비 추가 손실 폭 기준 검증 필요 |
| `loss_expansion_ratio` | `1.5`, `2.0` | 손실이 손절폭의 몇 배일 때 심각한지 검증 필요 |
| `avg_down_count_after_loss` | `1`, `2` | 손실 중 추가매수 횟수 기준 검증 필요 |
| `avg_down_qty_ratio` | `1.0` | 추가매수 수량이 최초 수량 이상이면 심각하다는 기준 검증 필요 |
| `failed_recovery_minutes` | `30` | 손절선 위로 회복하지 못한 시간을 어떻게 볼지 검증 필요 |

### 5.3 총괄 오케스트레이터 정책값 검증 필수

| 검증 대상 | 현재 baseline | 왜 검증해야 하는가 |
|---|---:|---|
| `min_route_score` | `0.55` | 이 점수 이상이면 에이전트 실행할 만한지 검증 필요 |
| `strong_route_score` | `0.70` | 강한 신호 기준 검증 필요 |
| `min_score_margin` | `0.15` | 주 원인과 보조 원인을 나누는 점수 차이 검증 필요 |
| `ambiguous_margin` | `0.10` | 애매한 케이스 판단 기준 검증 필요 |
| `secondary_factor_score` | `0.45` | 보조 요인으로 저장할 최소 점수 검증 필요 |
| `review_min_score` | `0.45` | 사람 검수 또는 보류 대상 기준 검증 필요 |
| `abstain_threshold` | `0.35` | 너무 약한 신호를 걸러내는 기준 검증 필요 |
| `profile_update_min_confidence` | `0.60` | 사용자 프로파일에 반영할 신뢰도 기준 검증 필요 |

## 6. 논문으로 찾아야 할 근거

논문은 세부 수치를 그대로 가져오기보다, 피처와 판단 방향의 근거를 찾는 용도입니다.

### 6.1 처분효과 / 손절실패

찾을 키워드:

```text
disposition effect
realization behavior
PGR PLR
loss realization
retail investor stop loss
```

대표 논문:

- Odean (1998), "Are Investors Reluctant to Realize Their Losses?"
- Barber, Lee, Liu, Odean (2007), "Is the Aggregate Investor Reluctant to Realise Losses?"
- Ben-David & Hirshleifer (2012), "Are Investors Really Reluctant to Realize their Losses?"

### 6.2 과매매 / 손실 후 위험추구

찾을 키워드:

```text
overtrading individual investors
revenge trading
post-loss risk taking
retail investor overconfidence
trading frequency performance
```

대표 논문:

- Barber & Odean (2000), "Trading Is Hazardous to Your Wealth"
- Odean (1999), "Do Investors Trade Too Much?"
- Coval & Shumway (2005), "Do Behavioral Biases Affect Prices?"

### 6.3 기술적 분석 피처

찾을 키워드:

```text
technical trading rules
moving average
momentum
volume breakout
support resistance
intraday technical analysis
```

대표 논문:

- Brock, Lakonishok & LeBaron (1992), "Simple Technical Trading Rules and the Stochastic Properties of Stock Returns"
- Lo, Mamaysky & Wang (2000), "Foundations of Technical Analysis"
- Osler (2000), "Support for Resistance"

### 6.4 RSI / ATR / 변동성 손절

찾을 키워드:

```text
RSI technical indicator
average true range
ATR stop loss
volatility stop
intraday volatility stop
```

대표 근거:

- Wilder (1978), "New Concepts in Technical Trading Systems"
- ATR stop-loss / volatility stop 관련 실증 연구

## 7. 현재 문서의 해석

이 문서에 있는 수치들은 이렇게 봐야 합니다.

```text
논문으로 개념 근거가 있는 피처:
이동평균, 모멘텀, RSI, ATR, 거래량, 지지/저항, 처분효과, 과매매

우리 데이터에 맞게 임시로 둔 값:
0.85, 0.992, 0.012, 30분, 60분, 1.5pp, 0.55 등
```

따라서 현재 단계에서 할 수 있는 주장은 다음 정도입니다.

```text
문헌 기반 개념을 1분봉 데이터 구조에 맞게 feature화했고,
초기 baseline 임계값을 설정했다.
세부 임계값은 실제 데이터 검증으로 보정할 예정이다.
```
