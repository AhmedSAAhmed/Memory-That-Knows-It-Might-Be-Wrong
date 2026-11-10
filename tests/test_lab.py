from app.lab import run_lab


def test_failure_lab_runs_isolated_offline_scenarios():
    results = run_lab()
    assert len(results) == 6
    assert all(row["passed"] for row in results), results
    assert {row["scenario"] for row in results} >= {"Revocation", "Scope isolation", "Staleness"}
