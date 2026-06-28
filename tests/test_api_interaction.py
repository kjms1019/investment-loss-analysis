"""API 상호작용 select 의 순수 로직 테스트 (DB 비의존).

_resolve_choice / _next_round 만 검증한다 — 엔드포인트 자체는 리포트 DB 상태에
의존하므로 여기선 결정론적인 순수 함수만 다룬다.
"""
from analysis.api.main import _resolve_choice, _next_round


_INTERACTION = {
    "frequency_winner": "entry",
    "amount_winner": "cut",
    "stats": {"entry": {"count": 5, "amount": 300}, "cut": {"count": 2, "amount": 900}},
}


def test_resolve_choice_direct_domain():
    assert _resolve_choice("entry", _INTERACTION) == "entry"
    assert _resolve_choice("CUT", _INTERACTION) == "cut"


def test_resolve_choice_by_basis():
    assert _resolve_choice("frequency", _INTERACTION) == "entry"
    assert _resolve_choice("amount", _INTERACTION) == "cut"


def test_resolve_choice_unknown_is_none():
    assert _resolve_choice("nonsense", _INTERACTION) is None
    assert _resolve_choice("", _INTERACTION) is None


def test_next_round_offers_remaining_domain():
    nxt = _next_round(_INTERACTION["stats"], completed=["entry"])
    assert nxt is not None
    assert nxt["type"] == "cut"
    assert nxt["count"] == 2 and nxt["amount"] == 900


def test_next_round_none_when_all_done():
    assert _next_round(_INTERACTION["stats"], completed=["entry", "cut"]) is None


def test_next_round_skips_empty_domain():
    stats = {"entry": {"count": 5, "amount": 300}, "cut": {"count": 0, "amount": 0}}
    # cut 은 count 0 이라 남은 라운드 없음
    assert _next_round(stats, completed=["entry"]) is None
