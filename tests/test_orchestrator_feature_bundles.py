import csv
import json
import sqlite3

from analysis.label_validation.label_pipeline import CLASSIFIER_FEATURES
from analysis.orchestrator.pipeline import run_pipeline


def test_run_pipeline_stores_initial_feature_bundles_and_reuses_them(tmp_path):
    trade_csv = tmp_path / "trades.csv"
    with trade_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["datetime", "code", "name", "side", "qty", "price", "fee"])
        writer.writerow(["2026-01-02 09:00:00", "005930", "삼성전자", "BUY", 10, 10000, 0])
        writer.writerow(["2026-01-02 10:00:00", "005930", "삼성전자", "SELL", 10, 9000, 0])

    features = {name: 0.1 for name in CLASSIFIER_FEATURES}
    result = run_pipeline(
        str(trade_csv),
        db_path=str(tmp_path / "orchestrator.sqlite3"),
        profile_db_path=str(tmp_path / "profiles.sqlite3"),
        classifier_features_by_trade_id={"005930@2026-01-02T09:00:00": features},
    )

    # 초기 분석 파이프라인은 피처 번들 계산/저장까지만 검증한다.
    # 사용자 선택/focus(사후)는 test_orchestrator_interaction.py 가 담당.
    assert result.normalized_count == 1
    assert result.agent_results
    learned = result.agent_results[0].result["learned_classifier"]
    assert learned["calculation_stage"] == "initial_user_upload"
    assert learned["feature_scope"] == "historical_classifier_only"
    assert learned["feature_source"] == "provided_by_trade_id"

    conn = sqlite3.connect(tmp_path / "orchestrator.sqlite3")
    conn.row_factory = sqlite3.Row
    try:
        bundle = conn.execute("SELECT * FROM feature_bundles").fetchone()
        normalized = conn.execute("SELECT * FROM normalized_trades").fetchone()
    finally:
        conn.close()

    assert bundle is not None
    assert bundle["feature_status"] == "ok"
    assert json.loads(bundle["data_quality_json"])["calculation_stage"] == "initial_user_upload"
    assert normalized is not None
    assert normalized["trade_id"] == result.agent_results[0].trade_id
    assert normalized["code"] == "005930"
    assert normalized["name"] == "삼성전자"
