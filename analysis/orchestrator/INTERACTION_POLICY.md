# 총괄 에이전트 사용자 상호작용 설계

이 문서는 분류기 결과를 받은 뒤, 총괄 에이전트가 웹에서 사용자에게 어떤 분석 관점을 물어보고
어떤 에이전트를 실행할지 정하는 상호작용 정책을 정의한다.

## 1. 전제

- 총괄의 사용자 상호작용은 거래별 분류가 끝난 뒤 실행한다.
- 사용자에게 노출되는 선택지는 에이전트 이름이 아니라 문제 관점이다.
- 현재 실제 오케스트레이터는 `common.parser.filter_loss_cycles()`를 통해 완결된 절대손실 거래만 다룬다.
- `analysis/loss_screener`의 `selected`는 1순위 절대손실 거래와 2순위 기회손실 거래를 모두 포함할 수 있다.
  따라서 손실 거래만 대상으로 삼으려면 `tier == 1` 또는 `realized_pnl < 0` 조건을 유지해야 한다.
- 손실 총액 비교는 손실 거래의 `abs(realized_pnl)` 합계로 계산한다. 손실 거래는 음수 손익을 가지므로
  금액 크기를 비교하기 위해 절댓값을 사용한다.

## 2. 집계 구조

분류기 또는 라우터는 거래별로 대표 도메인을 하나 산출한다.

```text
trade_id
primary_agent: entry_error | stop_loss_failure | unclassified
realized_pnl
classifier_scores
route_reason
```

총괄은 `primary_agent` 기준으로 아래 값을 집계한다.

```text
category_stats = {
  entry_error: {
    count,
    loss_amount_sum,
    trade_ids
  },
  stop_loss_failure: {
    count,
    loss_amount_sum,
    trade_ids
  }
}
```

- `count`: 해당 문제로 분류된 손실 거래 수
- `loss_amount_sum`: `sum(abs(realized_pnl))`
- `trade_ids`: 이후 선택된 에이전트 리포트에 포함할 거래 목록

`unclassified` 또는 `abstain` 결과는 사용자 선택 후보에서 제외한다. 단, 화면 하단 요약에는
"분류 보류 N건"처럼 보조 정보로만 노출할 수 있다.

## 3. 사용자 질문 조건

### 빈도 1위와 손실금액 1위가 같은 경우

사용자에게 선택 질문을 하지 않고 해당 문제를 중심으로 분석한다.

```text
사용자의 과거 손실 거래 통계를 보면,
가장 자주 반복되고 손실 금액도 가장 컸던 문제는 '진입오류'로 파악되었습니다.
```

### 빈도 1위와 손실금액 1위가 다른 경우

웹에 아래 문구와 선택지를 띄운다.

```text
사용자의 과거 손실 거래 통계를 보면,
가장 자주 반복된 문제는 '진입오류'이고,
손실 금액이 가장 컸던 문제는 '손절실패'로 파악되었습니다.

어떤 문제를 중심으로 분석해볼까요?
[자주 반복된 문제] [손실 금액이 컸던 문제]
```

선택지 내부 매핑:

```text
자주 반복된 문제 -> frequency_winner
손실 금액이 컸던 문제 -> amount_winner
```

사용자는 에이전트가 아니라 분석 관점을 고른다. 총괄은 선택된 관점에 해당하는 에이전트만 실행한다.

## 4. 에이전트 선택

현재 사용자 선택 후보는 두 도메인으로 제한한다.

| 문제 도메인 | 실행 에이전트 |
|---|---|
| `entry_error` | 진입오류 에이전트 |
| `stop_loss_failure` | 손절실패 에이전트 |

세부 카테고리는 도메인 에이전트에 매핑된다.

```text
박스권 상단 추격 진입 -> entry_error
단기 과열 추격 진입 -> entry_error
손절 지연 -> stop_loss_failure
손실 중 추가매수 -> stop_loss_failure
```

## 5. 루프 정책

사용자 상호작용 루프는 최대 2회까지만 허용한다.

1. 첫 번째 선택에 해당하는 에이전트를 실행한다.
2. 해당 카테고리의 분석 리포트를 제공한다.
3. 선택하지 않은 다른 카테고리가 있으면 사용자에게 추가 질문을 띄운다.

```text
진입오류 분석이 완료되었습니다.
손실 금액이 컸던 '손절실패' 문제도 이어서 확인해볼까요?
[예] [아니오]
```

4. 사용자가 `예`를 선택하면 남은 에이전트를 한 번 더 실행한다.
5. 사용자가 `아니오`를 선택하거나 두 도메인을 모두 분석했으면 종료한다.

루프 상태는 아래처럼 관리한다.

```text
max_rounds = 2
completed_agents = []
remaining_agents = [entry_error, stop_loss_failure] - completed_agents
selected_agent = user_choice_mapped_agent
```

## 6. 리포트 제공 범위

상세 분석 리포트는 사용자가 선택한 카테고리에 대해서만 제공한다.

첫 화면의 통계 요약은 두 기준을 모두 보여줄 수 있지만, 실제 상세 리포트에는 선택된 도메인의
거래와 분석 결과만 포함한다.

```text
통계 요약:
- 빈도 1위: 진입오류
- 손실금액 1위: 손절실패

사용자 선택:
- 손실 금액이 컸던 문제

제공 리포트:
- 손절실패 분석 리포트만 제공
```

## 7. 저장할 상태값

웹과 총괄이 같은 흐름을 재현할 수 있도록 아래 상태값을 남긴다.

```text
frequency_winner
amount_winner
frequency_count
amount_loss_sum
user_selected_basis: frequency | amount | auto_same_winner | followup
selected_agent_id
completed_agent_ids
remaining_agent_ids
round_index
max_rounds
```

이 상태는 추후 DB에 저장하거나 웹 JSON export에 포함할 수 있다.
