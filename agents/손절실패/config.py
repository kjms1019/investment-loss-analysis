from dataclasses import dataclass


@dataclass
class Config:
    # ATR settings  (A: industry standard)
    atr_period: int = 14
    atr_k: float = 2.0
    fixed_stop_pct: float = -5.0        # fallback stop line

    # Alert thresholds  (B: hypothesis, calibrate with real data)
    delay_warn_days: int = 2
    delay_severe_days: int = 5
    expansion_warn_pct: float = 5.0     # pp beyond stop → warn
    expansion_severe_ratio: float = 2.0 # final_loss >= 2x stop → severe
    avg_down_warn_count: int = 2
    avg_down_severe_ratio: float = 1.0  # add-on qty >= initial qty → severe

    # Score weights  (B: hypothesis — split into config so logistic regression can replace)
    weight_expansion: float = 0.35
    weight_delay: float = 0.30
    weight_avg_down: float = 0.20
    weight_excess_loss: float = 0.15

    # Safety mechanisms  (A: definitional)
    no_breach_multiplier: float = 0.3

    # Lucky hold threshold
    lucky_hold_threshold: float = -20.0  # MAE <= this AND profitable → lucky_hold flag


DEFAULT_CONFIG = Config()
