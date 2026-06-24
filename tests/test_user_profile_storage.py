from tempfile import TemporaryDirectory

from analysis.orchestrator.schema import AgentResult
from analysis.user_profile import UserProfileStorage, build_profile


def test_build_profile_aggregates_agent_results():
    results = [
        AgentResult("run1", "t1", "entry_error", "ok", 0.8, "strong"),
        AgentResult("run1", "t2", "stop_loss_failure", "ok", 0.5, "moderate"),
        AgentResult("run1", "t3", "entry_error", "ok", 0.6, "moderate"),
    ]

    profile = build_profile("u1", results)

    assert profile.total_analyzed_trades == 3
    assert profile.problem_counts == {"entry_error": 2, "stop_loss_failure": 1}
    assert profile.average_scores["entry_error"] == 0.7
    assert profile.dominant_problem_type == "entry_error"


def test_profile_storage_round_trip():
    with TemporaryDirectory() as tmp:
        path = f"{tmp}/user_profiles.sqlite3"
        storage = UserProfileStorage(db_path=path)
        results = [
            AgentResult("run1", "t1", "stop_loss_failure", "ok", 0.9, "strong"),
        ]
        profile = build_profile("u1", results)

        storage.insert_trade_labels("u1", results)
        storage.upsert_profile(profile, latest_run_id="run1")
        loaded = storage.load_profile("u1")
        storage.close()

    assert loaded.user_id == "u1"
    assert loaded.total_analyzed_trades == 1
    assert loaded.dominant_problem_type == "stop_loss_failure"
