from schema import Cycle
from config import Config, DEFAULT_CONFIG


def _weighted_raw(cycle: Cycle, signals: dict, config: Config) -> float:
    """Weighted sum of the four signals, before the profit safety check."""
    raw = (
        config.weight_expansion   * signals["expansion"]  +
        config.weight_delay       * signals["delay"]       +
        config.weight_avg_down    * signals["avg_down"]    +
        config.weight_excess_loss * signals["excess_loss"]
    )
    if not cycle.breached:
        raw *= config.no_breach_multiplier
    return round(min(1.0, max(0.0, raw)), 6)


def compute_score(cycle: Cycle, signals: dict, config: Config = DEFAULT_CONFIG) -> float:
    """
    Weighted average of the four signals → [0, 1].

    Safety mechanisms (definitional, not tunable):
    - Profitable trade → 0.0  (점수는 "이 손실에 이 문제가 기여한 정도"라는 정의상,
      손실이 없으면 0이어야 cross-agent 비교가 성립한다. resulting bias로 행동 자체를
      면죄부 주는 게 아니라, lucky_hold 케이스는 compute_shadow_score로 별도 노출한다.)
    - No breach         → score × no_breach_multiplier
    """
    if cycle.realized_return > 0:
        return 0.0
    return _weighted_raw(cycle, signals, config)


def compute_shadow_score(cycle: Cycle, signals: dict, config: Config = DEFAULT_CONFIG) -> float:
    """
    수익 거래라도 "이 보유 행동이 손실로 끝났다면 몇 점짜리 손절실패였을지" 보여주는 참고 점수.
    실제 score(cross-agent 비교용, 정의상 0)와는 별개이며, lucky_hold 코칭 메시지에만 쓴다.
    """
    return _weighted_raw(cycle, signals, config)
