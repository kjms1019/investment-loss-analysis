from schema import Cycle
from config import Config, DEFAULT_CONFIG


def compute_score(cycle: Cycle, signals: dict, config: Config = DEFAULT_CONFIG) -> float:
    """
    Weighted average of the four signals → [0, 1].

    Safety mechanisms (definitional, not tunable):
    - Profitable trade → 0.0  (손절실패 진단 대상 아님)
    - No breach         → score × no_breach_multiplier
    """
    if cycle.realized_return > 0:
        return 0.0

    raw = (
        config.weight_expansion   * signals["expansion"]  +
        config.weight_delay       * signals["delay"]       +
        config.weight_avg_down    * signals["avg_down"]    +
        config.weight_excess_loss * signals["excess_loss"]
    )

    if not cycle.breached:
        raw *= config.no_breach_multiplier

    return round(min(1.0, max(0.0, raw)), 6)
