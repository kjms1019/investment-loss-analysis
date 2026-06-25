# Feature And Threshold Policy

This document lists the current baseline features and thresholds used by the
classifier-score and orchestrator-decision layer. Values are intentionally
minute-oriented so the batch review loop and live monitor can share the same
language.

These thresholds are not final research results. They are baseline hypotheses
that must be calibrated with labeled trades and 1-minute OHLCV replay.

## Architecture

```text
TradeCycle
  -> classifier candidate scores
       entry_error_score
       stop_loss_failure_score
  -> orchestrator decision layer
       primary_agent
       secondary_factors
       route_type
  -> run primary hybrid agent only
  -> save profile with primary + secondary evidence
```

The classifier produces candidate scores. The orchestrator chooses the primary
agent and records secondary factors. Complex factors are represented as
`single_primary_with_secondary`; a third compound agent is not used.

## Entry-Error Features

All entry-error features are defined on 1-minute OHLCV before or at entry time.
Post-entry rows must not be used for entry-time prediction.

| Feature | Meaning | Current Baseline |
|---|---|---:|
| `ret_1m` | 1-minute return before entry | feature only |
| `ret_3m` | 3-minute return before entry | feature only |
| `ret_5m` | 5-minute return before entry | `<= -0.004` pullback weakness |
| `ret_20m` | 20-minute return before entry | `>= 0.012` overheat |
| `ma_20_slope` | recent 20m MA vs previous 20m MA | `<= -0.002` downtrend |
| `range_position_20m` | entry position in recent 20m high-low range | `>= 0.85` upper entry, `>= 0.75` weak-flow upper area |
| `entry_vs_high20_ratio` | entry price / recent 20m high | `>= 0.992` near high |
| `entry_vs_ma20_pct` | entry price vs 20m MA | `< 0` below MA |
| `rsi_14` | 14-bar RSI on 1-minute closes | `>= 68` overheat |
| `volume_ratio_20m` | entry volume / recent 20m average volume | `< 0.80` weak, `< 0.75` dry |
| `entry_position_in_bar` | entry location inside entry minute candle | feature only |
| `loss_early_ratio` | early loss / final loss during first 20% of holding | `>= 0.70` entry-error review signal |

## Stop-Loss-Failure Features

Stop-loss features are defined for minute-level live monitoring. Batch day-level
reports are adapted to minutes with `390` trading minutes per day until a true
minute breach timestamp is available.

| Feature | Meaning | Current Baseline |
|---|---|---:|
| `stop_breached` | 1-minute low/current price breached stop line | boolean |
| `breach_minutes` | minutes after first stop breach | `>= 30` warning, `>= 60` severe |
| `loss_expansion_pct` | loss beyond stop line in percentage points | `>= 1.5pp` warning, `>= 3.0pp` severe |
| `loss_expansion_ratio` | absolute current/final loss divided by stop width | `>= 1.5` warning, `>= 2.0` severe |
| `mae_expansion_pct` | MAE beyond stop line | feature only |
| `avg_down_count_after_loss` | add-on buys after position is in loss | `>= 1` warning, `>= 2` severe |
| `avg_down_qty_ratio` | add-on quantity / first entry quantity | `>= 1.0` severe |
| `failed_recovery_minutes` | minutes without recovery above stop line | `>= 30` warning |

## Orchestrator Decision Policy

| Policy Value | Current Baseline | Purpose |
|---|---:|---|
| `min_route_score` | `0.55` | minimum score for primary routing |
| `strong_route_score` | `0.70` | strong signal marker |
| `min_score_margin` | `0.15` | margin for clean single-primary route |
| `ambiguous_margin` | `0.10` | close scores become ambiguous/review if not both routeable |
| `secondary_factor_score` | `0.45` | score high enough to save as secondary factor |
| `review_min_score` | `0.45` | medium signal that needs review |
| `abstain_threshold` | `0.35` | below this, skip specialized agent |
| `profile_update_min_confidence` | `0.60` | minimum confidence for profile updates |

## Values That Need Real Validation

The following are not paper-proven constants. They need threshold sweep,
human-reviewed labels, and replay on 1-minute OHLCV:

- `range_position_20m`: `0.75`, `0.85`
- `entry_vs_high20_ratio`: `0.992`
- `ret_20m`: `0.012`
- `rsi_14`: `68`
- `volume_ratio_20m`: `0.75`, `0.80`
- `ma_20_slope`: `-0.002`
- `ret_5m`: `-0.004`
- `loss_early_ratio`: `0.70`
- `breach_minutes`: `30`, `60`
- `loss_expansion_pct`: `1.5pp`, `3.0pp`
- `loss_expansion_ratio`: `1.5`, `2.0`
- `avg_down_count_after_loss`: `1`, `2`
- `avg_down_qty_ratio`: `1.0`
- `failed_recovery_minutes`: `30`
- all orchestrator policy scores and margins

## Literature To Support Feature Choice

Search and cite these areas. Most papers support feature concepts rather than
our exact minute-level cutoffs.

- Disposition effect / realization behavior:
  - Odean (1998), "Are Investors Reluctant to Realize Their Losses?"
  - Barber, Lee, Liu, Odean (2007), "Is the Aggregate Investor Reluctant to Realise Losses?"
  - Ben-David & Hirshleifer (2012), "Are Investors Really Reluctant to Realize their Losses?"
- Overtrading / post-loss risk taking:
  - Barber & Odean (2000), "Trading Is Hazardous to Your Wealth"
  - Odean (1999), "Do Investors Trade Too Much?"
  - Coval & Shumway (2005), "Do Behavioral Biases Affect Prices?"
- Technical features:
  - Brock, Lakonishok & LeBaron (1992), "Simple Technical Trading Rules and the Stochastic Properties of Stock Returns"
  - Lo, Mamaysky & Wang (2000), "Foundations of Technical Analysis"
  - Osler (2000), "Support for Resistance"
- RSI / ATR / volatility stops:
  - Wilder (1978), "New Concepts in Technical Trading Systems"
  - volatility stop and ATR stop-loss empirical literature
