# 03_build - code the memory layer and UI

One job: make `app/` match the architecture, with tests.

## Inputs
- Working (this run): `../02_architecture/output/architecture.md`
- Reference (every run): `../../_shared/memory-model.md`, `../../_shared/memory-config.json`, `../../_shared/policies.md`, `../../_shared/brand-theme.md`, `../../_shared/prompts/`

Do NOT load: `stages/06_submission/`, `.local/` (reference repos are for the owner, not for code).

## Process
1. Write the test first for any memory behaviour (`tests/`).
2. Implement in `app/memory/` (pure Python, no LLM), then `app/agent/`, then `app/ui/`.
3. Numbers come from `memory-config.json` only; prompts from `_shared/prompts/` only.
4. Run `uv run pytest`.

## Outputs
- code in `app/` and `tests/` (this stage's product lives outside `output/` on purpose: it is the repo's product folder)
- `notes.md` -> `output/` (what changed, what is next)

## Check
`uv run pytest` is green and `uv run uvicorn app.main:app` serves `/health`.
