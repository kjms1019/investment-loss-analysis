from schema import Cycle
from config import Config, DEFAULT_CONFIG

_STOP_METHOD_KO = {"user": "사용자 지정", "atr": "변동성 기준", "fixed": "고정 기준"}


def _judgment_type(cycle: Cycle, signals: dict, score: float) -> str:
    if cycle.realized_return > 0 or score < 0.1 or not cycle.breached:
        return "해당없음"
    ranked = max(
        {"avg_down": signals["avg_down"], "delay": signals["delay"], "expansion": signals["expansion"]},
        key=lambda k: {"avg_down": signals["avg_down"], "delay": signals["delay"],
                       "expansion": signals["expansion"]}[k],
    )
    return "물타기형" if ranked == "avg_down" else "지연형"


def _narrative(cycle: Cycle, signals: dict, score: float) -> str:
    if cycle.realized_return > 0:
        return "수익 거래라 손절실패 진단에서 제외됩니다."
    if not cycle.breached:
        method_ko = _STOP_METHOD_KO.get(cycle.stop_method, cycle.stop_method)
        return (
            f"손절선({cycle.stop_pct:.1f}%, {method_ko})을 보유 기간 내내 넘지 않아 "
            "손절실패로 보기 어렵습니다."
        )

    method_ko = _STOP_METHOD_KO.get(cycle.stop_method, cycle.stop_method)
    parts = [
        f"{cycle.breach_date.strftime('%m월 %d일')}에 {cycle.MAE_pct:.1f}%로 "
        f"손절 기준({cycle.stop_pct:.1f}%, {method_ko})을 넘겼지만"
    ]
    if cycle.delay_days > 0:
        parts.append(f"{cycle.delay_days}영업일을 더 들고 있었고,")
    if cycle.avg_down_count > 0:
        parts.append(f"그 사이 {cycle.avg_down_count}번 더 사들이면서")
    parts.append(f"손실이 {cycle.realized_return:.1f}%까지 커졌습니다.")
    return " ".join(parts)


def _recommendation(cycle: Cycle, signals: dict, config: Config) -> str:
    if not cycle.breached:
        return ""
    if signals["avg_down"] > signals["delay"]:
        return "손실 중 추가매수(물타기)는 손실을 키울 수 있으니 진입 전에 '손실 중 추가매수 금지' 규칙을 정해두세요."
    return f"기준선 이탈 후 {config.delay_warn_days}영업일 넘게 보유하면 경고하도록 알림을 설정하세요."


def generate_report(
    cycle: Cycle,
    signals: dict,
    score: float,
    config: Config = DEFAULT_CONFIG,
) -> dict:
    lucky_hold = (cycle.realized_return > 0) and (cycle.MAE_pct <= config.lucky_hold_threshold)
    judgment_type = _judgment_type(cycle, signals, score)

    return {
        "ticker": cycle.ticker,
        "entry_ts": cycle.entry_ts.isoformat(),
        "exit_ts": cycle.exit_ts.isoformat() if cycle.exit_ts else None,
        "judgment_type": judgment_type,
        "score": score,
        # Signal scores + raw diagnostics — always exposed so
        # orchestrator / future logistic regression can consume them directly.
        "signals": {
            "expansion_score": round(signals["expansion"], 4),
            "delay_score":     round(signals["delay"],     4),
            "avg_down_score":  round(signals["avg_down"],  4),
            "excess_loss_score": round(signals["excess_loss"], 4),
            "realized_return_pct": round(cycle.realized_return, 2),
            "MAE_pct":        round(cycle.MAE_pct, 2),
            "stop_pct":       round(cycle.stop_pct, 2),
            "stop_method":    cycle.stop_method,
            "breached":       cycle.breached,
            "breach_date":    cycle.breach_date.isoformat() if cycle.breach_date else None,
            "delay_days":     cycle.delay_days,
            "avg_down_count": cycle.avg_down_count,
            "avg_down_qty_ratio": round(cycle.avg_down_qty, 2),
        },
        "flags": {
            "lucky_hold": lucky_hold,
        },
        "narrative":       _narrative(cycle, signals, score),
        "recommendation":  _recommendation(cycle, signals, config),
    }
