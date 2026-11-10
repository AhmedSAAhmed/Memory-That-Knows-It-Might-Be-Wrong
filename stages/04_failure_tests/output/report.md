# Stage 04 failure evaluation

Status: **pass**

Run: `20261110T114228Z-4fc79cce` · UTC: 2026-11-10T11:42:28+00:00

Offline regressions: **124 passed, 18 deselected in 4.73s**.
Live evaluations: **18 passed in 35.78s**.

| Scenario | Successful runs | Gate |
|---|---|---|
| [FT-01-clear-contradiction](FT-01-clear-contradiction.md) | 3/3 | pass |
| [FT-02-ambiguous-contradiction](FT-02-ambiguous-contradiction.md) | 3/3 | pass |
| [FT-03-staleness](FT-03-staleness.md) | 3/3 | pass |
| [FT-04-revocation](FT-04-revocation.md) | 3/3 | pass |
| [FT-05-memory-injection](FT-05-memory-injection.md) | 3/3 | pass |
| [FT-06-scope-isolation](FT-06-scope-isolation.md) | 3/3 | pass |

## Method

Each live case runs against a fresh temporary SQLite database with an injectable UTC clock. Configured providers perform real screening, extraction and assert-band answers. Ask/hedge enforcement is deterministic by design; those cases still require a real guard response. The live cases use FTS-only retrieval; vector scoring, vector failure fallback and late-vector erasure are tested offline.

Three distinct successful trials are required per scenario. Missing/skipped trials, duplicate trial IDs, failed assertions, unavailable required providers, missing scenario documents or a failed build gate fail the evaluation. Production provider fallback and SDK transport retries remain enabled; no scenario-level retry is hidden inside a trial.

## Evidence and limits

[eval-results.json](eval-results.json) retains every evaluator attempt, trial status, duration, observed providers and live guard-call counts. All customer facts, attacks and peer canaries are fictional. Credentials and raw provider request/response bodies are excluded from the report.

This is observed pass^3 behavior for the documented cases, not an exhaustive security proof or a statistical production-reliability estimate. Scope, privacy, rollback, malformed output, unavailable providers, incognito and replay edge cases are additionally covered by the offline suite.

## Next

Stage 05 deployment may proceed only after this gate passes.
