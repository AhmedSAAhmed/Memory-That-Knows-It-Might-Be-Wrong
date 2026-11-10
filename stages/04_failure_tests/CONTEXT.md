# 04_failure_tests - prove the wrong/forget mechanics

One job: show contradiction, staleness, revocation, injection and scope leaks are handled explicitly.

## Inputs
- Working (this run): `../../app/`, `../../tests/`
- Reference (every run): `../../_templates/failure-test.md`, `../../_shared/policies.md`

Do NOT load: UI styling files.

## Process
1. One copy of the template per failure into `output/FT-NN-*.md`.
2. Each one names its automated test.
3. Run `uv run python _tools/run_evals.py` (runs the LLM-backed scenarios 3 times each: pass^3).

## Outputs
- `FT-*.md` and `report.md` -> `output/`

## Check
`_tools/run_evals.py` writes `output/check.md`; first line `pass` or `fail: <why>`.
