"""Run the failure-test suite and write stages/04_failure_tests/output/check.md.

Run from the repo root: `python _tools/run_evals.py`. LLM-backed scenarios (marked `eval`)
are added on Day 4 and run 3 times each (pass^3); until then this runs the offline suite.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "stages" / "04_failure_tests" / "output" / "check.md"


def main() -> int:
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=ROOT,
                          capture_output=True, text=True)
    tail = (proc.stdout or proc.stderr).strip().splitlines()[-1:] or ["no output"]
    verdict = "pass" if proc.returncode == 0 else f"fail: {tail[0]}"
    CHECK.parent.mkdir(parents=True, exist_ok=True)
    CHECK.write_text(f"{verdict}\n\nRun: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
                     f"Summary: {tail[0]}\n", encoding="utf-8")
    print(verdict)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
