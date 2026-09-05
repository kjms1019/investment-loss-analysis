from schema import Cycle
from config import Config, DEFAULT_CONFIG


def expansion_signal(cycle: Cycle, config: Config = DEFAULT_CONFIG) -> float:
    """
    Signal 1 (weight 0.35): How far beyond the stop did the FINAL realized loss go?
    - expansion_pp > 0 only when final_loss exceeded stop_pct.
    - Normalized: 20 pp beyond → 1.0; 4x stop ratio → 1.0.
    """
    if not cycle.breached:
        return 0.0
    expansion_pp = cycle.stop_pct - cycle.realized_return  # both negative; positive = exceeded
    if expansion_pp <= 0:
        return 0.0
    stop_abs = abs(cycle.stop_pct)
    final_abs = abs(cycle.realized_return)
    ratio = final_abs / stop_abs if stop_abs > 0 else 0.0
    pp_score = min(1.0, expansion_pp / 20.0)
    ratio_score = min(1.0, max(0.0, (ratio - 1.0) / 3.0))
    return max(pp_score, ratio_score)


def delay_signal(cycle: Cycle, config: Config = DEFAULT_CONFIG) -> float:
    """
    Signal 2 (weight 0.30): Business days held after breach.
    - < warn_days  → 0.1 (slight; sold near breach)
    - warn..severe → linear 0.3 → 0.7
    - > severe     → 0.7 → 1.0 (capped)
    """
    if not cycle.breached:
        return 0.0
    days = cycle.delay_days
    if days <= 0:
        return 0.0
    if days < config.delay_warn_days:
        return 0.1
    if days < config.delay_severe_days:
        t = (days - config.delay_warn_days) / (config.delay_severe_days - config.delay_warn_days)
        return 0.3 + t * 0.4
    return min(1.0, 0.7 + (days - config.delay_severe_days) / 10.0 * 0.3)


def avg_down_signal(cycle: Cycle, config: Config = DEFAULT_CONFIG) -> float:
    """
    Signal 3 (weight 0.20): Averaging down while in loss.
    - count score: 2x warn_count → 1.0
    - ratio score: 2x severe_ratio → 1.0
    Takes the max so either dimension alone can max the signal.
    """
    if cycle.avg_down_count == 0:
        return 0.0
    count_score = min(1.0, cycle.avg_down_count / (config.avg_down_warn_count * 2.0))
    ratio_score = min(1.0, cycle.avg_down_qty / (config.avg_down_severe_ratio * 2.0))
    return max(count_score, ratio_score)


def excess_loss_signal(cycle: Cycle, config: Config = DEFAULT_CONFIG) -> float:
    """
    Signal 4 (weight 0.15): How far MAE exceeded the stop line.
    Captures intraday depth even if trader eventually recovered somewhat.
    2x stop excess → 1.0.
    """
    if not cycle.breached:
        return 0.0
    stop_abs = abs(cycle.stop_pct)
    mae_abs = abs(cycle.MAE_pct)
    if mae_abs <= stop_abs or stop_abs == 0:
        return 0.0
    excess = mae_abs - stop_abs
    return min(1.0, excess / (stop_abs * 2.0))


def compute_signals(cycle: Cycle, config: Config = DEFAULT_CONFIG) -> dict:
    """Returns all four raw signal scores (always exposed alongside the final score)."""
    return {
        "expansion": expansion_signal(cycle, config),
        "delay": delay_signal(cycle, config),
        "avg_down": avg_down_signal(cycle, config),
        "excess_loss": excess_loss_signal(cycle, config),
    }
