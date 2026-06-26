# Runtime Predictor

The predictor is the alert brain after the orchestrator has accumulated closed
trade analysis in SQLite.

It has one public component, `TradeRiskPredictor`, with two modes:

- `predict_entry_risk`: checks a new or just-opened trade using only pre-entry
  context.
- `monitor_live_position`: checks one currently open position from a live
  stream.

The component does not own broker streaming. A broker adapter should feed
`PositionSnapshot` objects for each open position, and the predictor returns a
`RiskSignal` per trade.

When labeled examples are available, `fit()` trains a Random Forest classifier.
When data is scarce or scikit-learn is unavailable, rule scoring is used so the
user flow still works.

```python
from analysis.predictor import EntryContext, PositionSnapshot, TradeRiskPredictor

predictor = TradeRiskPredictor.from_sqlite("analysis/data/orchestrator.sqlite3")
signal = predictor.monitor_live_position(snapshot)

if signal.should_alert:
    notify(signal)
```
