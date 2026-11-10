"""The formal gate must not pass missing, skipped or duplicate live runs."""
from _tools.run_evals import SCENARIOS, score_scenarios


def records():
    return [{"test": test, "trial": trial, "status": "passed"} for test in SCENARIOS.values() for trial in (1,2,3)]


def test_all_three_distinct_runs_required():
    assert all(row["passed"] for row in score_scenarios(records(), 3))
    missing = records()[1:]
    assert not all(row["passed"] for row in score_scenarios(missing, 3))


def test_skipped_failed_and_duplicate_runs_cannot_pass():
    for status in ("skipped", "failed"):
        rows = records()
        rows[0]["status"] = status
        assert not all(row["passed"] for row in score_scenarios(rows, 3))
    duplicated = records()
    duplicated[0]["trial"] = 2
    assert not all(row["passed"] for row in score_scenarios(duplicated, 3))
