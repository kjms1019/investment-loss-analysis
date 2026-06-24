# Hybrid Agents

기존 3개 에이전트는 수정하지 않고, 심리 에이전트의 기능을 분해해서 새 합성 에이전트 2개로 노출한다.

## 분배 기준

| 심리 기능 | 새 대상 에이전트 | 이유 |
|---|---|---|
| 리벤지 트레이딩 | `entry_error_psych_hybrid` | 손실 직후의 다음 매수 결정 붕괴이므로 진입 오류에 가깝다. |
| 처분효과 | `stop_loss_psych_hybrid` | 손실을 오래 끌고 이익은 빨리 파는 패턴이라 손절 실패에 직접 대응한다. |
| 과매매 | 제외 | 거래 빈도/습관 문제라 두 에이전트 중 하나에 강제로 붙이기에는 원인 해석이 넓다. |

## 사용 예시

```python
from hybrid_agents import EntryErrorPsychHybridAgent, StopLossPsychHybridAgent
from psych_agent.dummy_data import make_demo_trades

trades = make_demo_trades("all")

entry_report = EntryErrorPsychHybridAgent().analyze(trades)
stop_report = StopLossPsychHybridAgent().analyze(trades)

print(entry_report.to_dict())
print(stop_report.to_dict())
```
