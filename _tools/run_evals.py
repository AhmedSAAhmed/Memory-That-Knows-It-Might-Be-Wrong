"""Run the failure-test suite and write stages/04_failure_tests/output/check.md.

Run from the repo root: `python _tools/run_evals.py`. LLM-backed scenarios (marked `eval`)
are added on Day 4 and run 3 times each (pass^3); until then this runs the offline suite.
Use `--checkpoint day-1` to record Day 1 verification without passing stage 04.
"""
from __future__ import annotations

import subprocess
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "stages" / "04_failure_tests" / "output" / "check.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", choices=("day-1", "failure-tests"), default="failure-tests")
    args = parser.parse_args()
    check = ROOT / "stages" / "03_build" / "output" / "day-1-check.md" if args.checkpoint == "day-1" else CHECK
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests", "-o", "cache_dir=.local/pytest-cache"], cwd=ROOT,
                          capture_output=True, text=True)
    tail = (proc.stdout or proc.stderr).strip().splitlines()[-1:] or ["no output"]
    verdict = "pass" if proc.returncode == 0 else f"fail: {tail[0]}"
    check.parent.mkdir(parents=True, exist_ok=True)
    check.write_text(f"{verdict}\n\nRun: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
                     f"Checkpoint: {args.checkpoint}\nSummary: {tail[0]}\n"
                     "Scope: offline suite only; this does not certify the full product or live deployment.\n", encoding="utf-8")
    print(verdict)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
