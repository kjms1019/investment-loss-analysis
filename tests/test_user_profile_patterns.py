"""반복 실수 패턴 집계(build_patterns) + 저장 테스트."""
from analysis.user_profile import build_patterns, UserProfileStorage


class _R:
    def __init__(self, tid, agent_id, label, score, psych=None):
        self.trade_id = tid
        self.agent_id = agent_id
        self.output_status = "ok"
        self.score = score
        self.result = {"label": label}
        if psych:
            self.result["psych"] = {"detected": True, "pattern": psych}


def _sample():
    return [
        _R("a", "stop_loss_failure", "지연형", 0.8, "disposition"),
        _R("b", "stop_loss_failure", "지연형", 0.7, "disposition"),
        _R("c", "stop_loss_failure", "물타기형", 0.9),
        _R("d", "entry_error", "short_term_overheat", 0.6),
        _R("e", "entry_error", "normal_entry", 0.1),   # 정상 → 집계 제외
    ]


def test_aggregates_by_frequency():
    pats = build_patterns(_sample())
    by_id = {p["pattern_id"]: p for p in pats}
    assert by_id["stop_loss_failure:지연형"]["count"] == 2
    assert by_id["stop_loss_failure:지연형"]["name_ko"] == "손절선 이탈 후 지연 보유"
    # 빈도 내림차순
    assert pats[0]["count"] >= pats[-1]["count"]


def test_skips_normal_and_carries_correction():
    pats = build_patterns(_sample())
    ids = {p["pattern_id"] for p in pats}
    assert "entry_error:normal_entry" not in ids          # 정상 라벨 제외
    overheat = next(p for p in pats if p["pattern_id"] == "entry_error:short_term_overheat")
    assert overheat["correction"]                          # 교정 조언 존재
    assert overheat["representative_trade"] == "d"


def test_psych_pattern_detected():
    pats = build_patterns(_sample(), top_n=10)
    ids = {p["pattern_id"] for p in pats}
    assert "stop_loss_failure:psych_disposition" in ids   # 흡수 심리도 패턴으로


def test_upsert_and_load_roundtrip(tmp_path):
    db = UserProfileStorage(str(tmp_path / "p.sqlite3"))
    pats = build_patterns(_sample())
    db.upsert_patterns("u1", "run1", pats)
    loaded = db.load_patterns("u1")
    db.close()
    assert len(loaded) == len(pats)
    assert loaded[0]["count"] >= loaded[-1]["count"]
    assert isinstance(loaded[0]["trade_ids"], list)
