# 02_architecture - write, retrieve, forget paths

One job: produce the architecture snapshot judges ask for.

## Inputs
- Working (this run): `../01_spec/output/execution-plan.md`
- Reference (every run): `../../_shared/memory-model.md`, `../../_shared/policies.md`

Do NOT load: `tests/`, deploy files.

## Process
1. Draw the three paths (write, retrieval, forgetting) as one Mermaid diagram.
2. Under each path, name the module in `app/memory/` that implements each box.
3. Keep it to one page.

## Outputs
- `architecture.md` -> `output/`

## Check
Walk test: a reader with no context can trace one message from input to stored memory to cited answer to revocation using only this page.
