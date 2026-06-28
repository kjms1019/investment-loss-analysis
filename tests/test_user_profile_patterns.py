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
    # 이름·태그는 공유 taxonomy에서 (심리는 별도 카드 아니라 태그)
    assert by_id["stop_loss_failure:지연형"]["name_ko"] == "손절선 이탈 후 2일 이상 보유"
    assert by_id["stop_loss_failure:지연형"]["tag"] == "처분효과"
    assert pats[0]["count"] >= pats[-1]["count"]


def test_skips_normal_and_carries_correction():
    pats = build_patterns(_sample())
    ids = {p["pattern_id"] for p in pats}
    assert "entry_error:normal_entry" not in ids          # 정상 라벨 제외
    overheat = next(p for p in pats if p["pattern_id"] == "entry_error:short_term_overheat")
    assert overheat["correction"]                          # 교정 조언 존재 (taxonomy)
    assert overheat["pattern_key"] == "entry_error.overheat"
    assert overheat["representative_trade"] == "d"


def test_uses_shared_taxonomy():
    # 패턴 분류체계는 report.tendency_taxonomy 와 동일 소스
    from analysis.report.tendency_taxonomy import lookup_taxonomy
    pats = build_patterns(_sample())
    p = next(x for x in pats if x["pattern_id"] == "stop_loss_failure:물타기형")
    assert p["pattern_key"] == lookup_taxonomy("stop_loss_failure", "물타기형").pattern_key


def test_upsert_and_load_roundtrip(tmp_path):
    db = UserProfileStorage(str(tmp_path / "p.sqlite3"))
    pats = build_patterns(_sample())
    db.upsert_patterns("u1", "run1", pats)
    loaded = db.load_patterns("u1")
    db.close()
    assert len(loaded) == len(pats)
    assert loaded[0]["count"] >= loaded[-1]["count"]
    assert isinstance(loaded[0]["trade_ids"], list)
