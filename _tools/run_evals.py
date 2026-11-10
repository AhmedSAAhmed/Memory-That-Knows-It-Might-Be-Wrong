"""Formal gate: offline regression suite plus three real runs of six failures.

Run: uv run python _tools/run_evals.py
The historical --checkpoint day-1 option runs offline and cannot pass stage 04.
No missing, failed, duplicate or skipped live trial counts as a passing run.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "stages" / "04_failure_tests" / "output"
CHECK = OUTPUT / "check.md"
SCENARIOS = {
    "FT-01-clear-contradiction.md": "test_live_clear_contradiction",
    "FT-02-ambiguous-contradiction.md": "test_live_ambiguous_contradiction",
    "FT-03-staleness.md": "test_live_staleness",
    "FT-04-revocation.md": "test_live_revocation",
    "FT-05-memory-injection.md": "test_live_memory_injection",
    "FT-06-scope-isolation.md": "test_live_scope_isolation",
}


def score_scenarios(records: list[dict], repetitions: int) -> list[dict]:
    scores = []
    for filename, test in SCENARIOS.items():
        runs = [row for row in records if row["test"] == test]
        expected = set(range(1, repetitions + 1))
        distinct = {row["trial"] for row in runs}
        successes = sum(row["status"] == "passed" for row in runs)
        passed = len(runs) == repetitions and distinct == expected and successes == repetitions
        scores.append({"scenario": Path(filename).stem, "file": filename, "test": test,
                       "passes": successes, "runs": len(runs), "required": repetitions, "passed": passed})
    return scores


def run_phase(label: str, arguments: list[str], xml_path: Path) -> dict:
    command = [sys.executable, "-m", "pytest", *arguments, "-p", "no:cacheprovider",
               f"--basetemp={xml_path.parent / (xml_path.stem + '-tmp')}",
               "-o", "junit_family=xunit1", f"--junitxml={xml_path}"]
    print(f"Running {label}...", flush=True)
    lines = []
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", env=env)
    for line in proc.stdout:
        lines.append(line.rstrip())
        print(line, end="", flush=True)
    code = proc.wait()
    cases = []
    if xml_path.exists():
        for case in ET.parse(xml_path).getroot().iter("testcase"):
            name = case.get("name", "")
            match = re.fullmatch(r"(.+)\[run-(\d+)\]", name)
            status = "failed" if case.find("failure") is not None or case.find("error") is not None else "skipped" if case.find("skipped") is not None else "passed"
            properties = {item.get("name"): item.get("value") for item in case.findall("./properties/property")}
            cases.append({"test": match[1] if match else name, "trial": int(match[2]) if match else None,
                          "status": status, "seconds": float(case.get("time", "0")), "observations": properties})
    summary = next((line.strip("= ") for line in reversed(lines) if re.search(r"\d+ (?:passed|failed|skipped|error)", line)), "No test summary produced")
    return {"exit_code": code, "summary": summary, "cases": cases}


def write_result(run: dict) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "eval-results.json"
    previous = json.loads(result_path.read_text(encoding="utf-8"))["runs"] if result_path.exists() else []
    result_path.write_text(json.dumps({"runs": [*previous, run]}, indent=2) + "\n", encoding="utf-8")
    verdict = "pass" if run["passed"] else "fail: " + "; ".join(run["issues"])
    CHECK.write_text(f"{verdict}\n\nRun: {run['id']}\nUTC: {run['at']}\n"
                     f"Offline: {run['offline']['summary']}\nLive: {run['live_summary']}\n"
                     "Evidence: report.md and eval-results.json. No skipped live trials count as passes.\n", encoding="utf-8")
    table = ["| Scenario | Successful runs | Gate |", "|---|---|---|"]
    for row in run["scores"]:
        table.append(f"| [{row['scenario']}]({row['file']}) | {row['passes']}/{row['required']} | {'pass' if row['passed'] else 'fail'} |")
        path = OUTPUT / row["file"]
        if path.exists():
            text = path.read_text(encoding="utf-8")
            text = re.sub(r"(?m)^Status: .*", "Status: " + ("passing" if row["passed"] else "failing"), text)
            path.write_text(text, encoding="utf-8")
    report = ["# Stage 04 failure evaluation", "", f"Status: **{'pass' if run['passed'] else 'fail'}**", "",
              f"Run: `{run['id']}` · UTC: {run['at']}", "",
              f"Offline regressions: **{run['offline']['summary']}**.", f"Live evaluations: **{run['live_summary']}**.", "",
              *table, "", "## Method", "",
              "Each live case runs against a fresh temporary SQLite database with an injectable UTC clock. "
              "Configured providers perform real screening, extraction and assert-band answers. Ask/hedge enforcement is deterministic by design; those cases still require a real guard response. "
              "The live cases use FTS-only retrieval; vector scoring, vector failure fallback and late-vector erasure are tested offline.", "",
              "Three distinct successful trials are required per scenario. Missing/skipped trials, duplicate trial IDs, failed assertions, unavailable required providers, missing scenario documents or a failed build gate fail the evaluation. "
              "Production provider fallback and SDK transport retries remain enabled; no scenario-level retry is hidden inside a trial.", "",
              "## Evidence and limits", "",
              "[eval-results.json](eval-results.json) retains every evaluator attempt, trial status, duration, observed providers and live guard-call counts. "
              "All customer facts, attacks and peer canaries are fictional. Credentials and raw provider request/response bodies are excluded from the report.", "",
              "This is observed pass^3 behavior for the documented cases, not an exhaustive security proof or a statistical production-reliability estimate. "
              "Scope, privacy, rollback, malformed output, unavailable providers, incognito and replay edge cases are additionally covered by the offline suite.", "",
              "## Next", "", "Stage 05 deployment may proceed only after this gate passes." if run["passed"] else "Return to Stage 03 for product fixes; rerun the offline suite and this complete evaluation after corrections."]
    if run["issues"]:
        report.extend(["", "Issues: " + "; ".join(run["issues"])])
    (OUTPUT / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", choices=("day-1", "failure-tests"), default="failure-tests")
    args = parser.parse_args()
    config = json.loads((ROOT / "_shared" / "memory-config.json").read_text(encoding="utf-8"))["evaluation"]
    repetitions = config["repetitions"]
    if args.checkpoint == "failure-tests":
        OUTPUT.mkdir(parents=True, exist_ok=True)
        CHECK.write_text("fail: evaluation has not completed\n", encoding="utf-8")
    issues = []
    build_check = ROOT / "stages" / "03_build" / "output" / "check.md"
    if args.checkpoint == "failure-tests":
        if not build_check.exists() or not build_check.read_text(encoding="utf-8").startswith("pass\n"):
            issues.append("Stage 03 build gate is not passing")
        if len(SCENARIOS) != config["live_scenarios"] or any(not (OUTPUT / name).exists() for name in SCENARIOS):
            issues.append("Required failure scenario documents are missing")
    offline = {"exit_code": 1, "summary": "Not run: precondition failed", "cases": []}
    live = {"exit_code": 1, "summary": "Not run", "cases": []}
    with TemporaryDirectory(prefix="memory-evaluation-") as directory:
        temporary = Path(directory)
        if not issues:
            offline = run_phase("offline regressions", ["-q", "tests", "-m", "not eval", "--tb=short"], temporary / "offline.xml")
            if offline["exit_code"]:
                issues.append("Offline regression suite failed")
        if args.checkpoint == "day-1":
            path = ROOT / "stages" / "03_build" / "output" / "day-1-check.md"
            path.write_text(("pass" if not issues else "fail") + f"\n\nOffline only: {offline['summary']}\nStage 04 is unchanged.\n", encoding="utf-8")
            return int(bool(issues))
        if not issues:
            live = run_phase("live pass^3 scenarios", ["-v", "tests/test_live_memory_evals.py", "--live-evals", "--tb=short"], temporary / "live.xml")
    scores = score_scenarios(live["cases"], repetitions)
    if live["exit_code"] or len(live["cases"]) != len(SCENARIOS) * repetitions or not all(row["passed"] for row in scores):
        issues.append("Live pass^3 gate is incomplete or failing")
    run = {"id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8],
           "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "passed": not issues,
           "issues": issues, "offline": {"summary": offline["summary"], "exit_code": offline["exit_code"]},
           "live_summary": live["summary"], "trials": live["cases"], "scores": scores}
    write_result(run)
    print("pass" if run["passed"] else "fail: " + "; ".join(issues), flush=True)
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
