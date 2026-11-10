# Pipeline - from brief to submitted entry

Form: **Pipeline** (ICM) wrapping one product folder, `app/`. Each stage reads the previous stage's `output/` plus the factory in `_shared/`, writes its own `output/`, and stops at its check.

| # | Stage | Reads | Writes | Check |
|---|---|---|---|---|
| 01 | [spec](stages/01_spec/CONTEXT.md) | challenge brief, owner answers | `output/execution-plan.md` | owner approves |
| 02 | [architecture](stages/02_architecture/CONTEXT.md) | 01 output, `_shared/memory-model.md` | `output/architecture.md` | walk test |
| 03 | [build](stages/03_build/CONTEXT.md) | 02 output, `_shared/` | code in `app/`, `tests/` | `uv run pytest` |
| 04 | [failure_tests](stages/04_failure_tests/CONTEXT.md) | `app/`, `_templates/failure-test.md` | `output/report.md` | `_tools/run_evals.py` |
| 05 | [deploy](stages/05_deploy/CONTEXT.md) | `render.yaml`, green 03 + 04 | `output/deploy-log.md` | live `/health` 200 |
| 06 | [submission](stages/06_submission/CONTEXT.md) | everything above | thesis, Loom script, notes | owner approves |

Stages 03 and 04 loop: a failing failure test sends you back to 03.

Status = what exists on disk. A stage is done when its `output/` holds the artifact and, where a script checks it, `check.md` starts with `pass`.
