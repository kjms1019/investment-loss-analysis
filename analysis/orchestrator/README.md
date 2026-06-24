# Orchestrator Skeleton

This package is the integration layer for the multi-agent review pipeline.

Current scope:

- Parse a user trade CSV into a shared normalized trade schema.
- Persist raw rows before any transformation.
- Persist normalized trades.
- Create an orchestrator run.
- Route trades to placeholder agent adapters.
- Persist placeholder agent results.

Out of scope for this skeleton:

- Broker-specific production parsers.
- Unified feature calculation.
- Real entry-error, stop-loss-failure, and psych agent execution.
- Random Forest prediction.
- Web API integration.

Expected CSV columns for the default parser:

```text
datetime,code,name,side,qty,price
```

Default SQLite path:

```text
analysis/data/orchestrator.sqlite3
```

The `analysis/data/` directory is git-ignored, so generated DB files should not
be committed.

Example:

```python
from analysis.orchestrator import run_orchestrator

result = run_orchestrator("my_trades.csv")
print(result.to_dict())
```
