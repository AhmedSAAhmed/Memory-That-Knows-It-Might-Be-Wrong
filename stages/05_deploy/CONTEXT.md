# 05_deploy - ship to Render free

One job: a live URL anyone can open.

## Inputs
- Working (this run): green `03_build` and `04_failure_tests` checks
- Reference (every run): `../../render.yaml`, `../../.env.example`

Do NOT load: `stages/01_spec/`.

## Process
1. Push `main` to GitHub.
2. Render: New > Blueprint > this repo (reads `render.yaml`). Set `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY` in the dashboard.
3. Wait for the deploy; open `/health`, then the UI; run one demo scenario.
4. Optional: a free uptime ping every 10 minutes during judging so the service does not sleep.

## Outputs
- `deploy-log.md` -> `output/` (URL, commit, date, smoke result)

## Check
`curl https://<service>.onrender.com/health` returns 200 and the demo scenario runs.
