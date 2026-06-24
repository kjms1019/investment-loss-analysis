"""
더미 데이터 정답지 테스트 — 명세 6번 기대 판정 전부 커버.
pytest 또는 직접 실행 모두 가능: python tests/test_dummy.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.dummy import TRANSACTIONS, OHLCV_DATA
from agent import analyze_all

_results = analyze_all(TRANSACTIONS, OHLCV_DATA)
_by_ticker = {r["ticker"]: r for r in _results}


# ── A: 지연형, 높은 점수 ───────────────────────────────────────────────────────
def test_A_지연형():
    r = _by_ticker["950130"]
    assert r["judgment_type"] == "지연형", r["judgment_type"]
    assert r["score"] > 0.4, f"score={r['score']:.4f} (expected > 0.4)"
    assert r["signals"]["delay_days"] == 6, r["signals"]["delay_days"]
    assert r["signals"]["breached"] is True
    assert r["flags"]["lucky_hold"] is False


# ── B: 물타기형 (핵심 함정: 최종 손실률은 작지만 물타기 행동으로 잡혀야 함) ──────
def test_B_물타기형():
    r = _by_ticker["950220"]
    assert r["judgment_type"] == "물타기형", r["judgment_type"]
    assert r["signals"]["avg_down_count"] == 2, r["signals"]["avg_down_count"]
    assert r["signals"]["avg_down_qty_ratio"] >= 3.0, r["signals"]["avg_down_qty_ratio"]
    # 최종 손실이 손절선(-5%)보다 작아도 avg_down_score가 높아 점수가 나와야 한다
    assert r["score"] > 0.2, f"score={r['score']:.4f} (물타기형이지만 점수 낮음)"
    # 최종 손실이 손절선 안에 있어 expansion은 0이어야 한다
    assert r["signals"]["expansion_score"] == 0.0, r["signals"]["expansion_score"]


# ── C: 정상 손절 — 거의 0점 ───────────────────────────────────────────────────
def test_C_정상손절():
    r = _by_ticker["950310"]
    assert r["score"] < 0.25, f"score={r['score']:.4f} (expected < 0.25)"


# ── D: 수익 거래 — 0점 제외 ───────────────────────────────────────────────────
def test_D_수익():
    r = _by_ticker["950440"]
    assert r["score"] == 0.0, f"score={r['score']}"
    assert r["judgment_type"] == "해당없음"
    assert r["flags"]["lucky_hold"] is False


# ── E: 운 좋은 홀딩 — 0점 + lucky_hold 플래그 ────────────────────────────────
def test_E_lucky_hold():
    r = _by_ticker["950550"]
    assert r["score"] == 0.0, f"score={r['score']}"
    assert r["flags"]["lucky_hold"] is True, "lucky_hold should be True (MAE ≤ -20% + 익절)"
    assert r["signals"]["MAE_pct"] <= -20.0, r["signals"]["MAE_pct"]


# ── 직접 실행 ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    tests = [
        ("A 지연형",     test_A_지연형),
        ("B 물타기형",   test_B_물타기형),
        ("C 정상손절",   test_C_정상손절),
        ("D 수익거래",   test_D_수익),
        ("E lucky_hold", test_E_lucky_hold),
    ]

    print("=" * 60)
    print("  손절실패 에이전트 - 더미 테스트")
    print("=" * 60)

    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  [OK] {name}")
            passed += 1
        except AssertionError as e:
            print(f"  [NG] {name}: {e}")

    print(f"\n  {passed}/{len(tests)} 통과\n")

    print("-" * 60)
    print("  사이클별 상세 결과")
    print("-" * 60)
    for r in _results:
        sig = r["signals"]
        flag = "  [lucky_hold]" if r["flags"]["lucky_hold"] else ""
        print(f"\n  [{r['ticker']}] {r['judgment_type']}  score={r['score']:.4f}{flag}")
        print(f"    서술: {r['narrative']}")
        if r["recommendation"]:
            print(f"    추천: {r['recommendation']}")
        print(
            f"    signals: "
            f"확대={sig['expansion_score']:.3f} "
            f"지연={sig['delay_score']:.3f}({sig['delay_days']}일) "
            f"물타기={sig['avg_down_score']:.3f}({sig['avg_down_count']}회,x{sig['avg_down_qty_ratio']}) "
            f"초과손실={sig['excess_loss_score']:.3f}"
        )
        print(
            f"    MAE={sig['MAE_pct']:.1f}%  실현={sig['realized_return_pct']:.1f}%  "
            f"손절선={sig['stop_pct']:.1f}%({sig['stop_method']})"
        )
