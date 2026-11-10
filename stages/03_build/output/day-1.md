# Day 1: memory schema, persistence and write path

Status: pass locally and deployed to Render (2026-11-10, Asia/Dubai). [Live verification](day-1-deploy.md) confirms revision `e295a4faa165a2bec737f5d5a7345be6d4b40466` and successful public memory writes.

## Delivered

- Validated immutable candidates and records with customer/scope/key, category, value, source quote, source event, confidence, timestamps, status and supersession lineage.
- SQLite storage with transactional fact/history/event/audit updates, FTS5 indexing, persisted category blocks and consent, parameterized customer/scope filters, and safe concurrent writes. Raw messages are not retained as transcripts.
- System and injectable UTC clocks. Confidence and corroboration decay by configured category half-life; behavior bands require confirmation for stale facts and never use contested or terminal facts as assertions.
- Deterministic privacy gates for secrets, sensitive-data consent, category blocks, incognito, source quotes and authorized order scopes. Session-scoped candidates are rejected from durable storage until transient-session support is built.
- Strict fast-model extraction, with canonical attribute keys and deterministic alias normalization. Models cannot supply customer identity, timestamps, confidence, consent or confirmed-source authority.
- Deterministic contradiction handling: newer customer statements supersede old ones, customer statements outrank imports/inferences, ambiguous conflicts remain contested, equal-time statements do not guess. Same-value corroboration is idempotent per source event; weaker sources cannot refresh a customer's fact.
- Agent integration in the order screen → extract → privacy/resolve/store → answer. Screening outages and invalid scores disable writing; extraction failure still permits an answer. Incognito skips extraction; detected secrets are not forwarded to models. Unsupported forgetting requests cannot receive a fabricated deletion confirmation.
- Storage opens during app startup and closes at shutdown; repeated app lifespans can reopen it. Prompt and numeric changes remain in `_shared/`.

## Verification

Tests were written and observed failing before implementing the corresponding memory/extraction behavior.

| Check | Result |
|---|---|
| Full pytest suite | 92 passed, including the deployed-revision health check, using `uv run --offline --no-sync --cache-dir .local/uv-cache pytest -q -o cache_dir=.local/pytest-cache`. |
| Evaluator checkpoint | `_tools/run_evals.py --checkpoint day-1` writes [day-1-check.md](day-1-check.md); it does not write the stage 04 check. |
| Persistence and isolation | Reopen, source provenance, customer/order separation, content-free audit, canonical keys and FTS index consistency covered. |
| Failure and concurrency | Duplicate/replayed events, concurrent connections, audit-failure rollback including restoration of superseded facts, malformed model output, provider outages, invalid guard scores, privacy bypasses and forged quotes covered. |
| Confidence and history | Half-life bands, decaying corroboration/caps, stale facts, contested/terminal states, future events, out-of-order updates and reconfirmation covered. |
| Real LLM smoke | Two fictional messages (“I live in Dubai.” → “I moved to Abu Dhabi.”), isolated temporary database, actual Groq screening/extraction/answering: one current `delivery_city = Abu Dhabi`, two history versions, other customer sees none. At +365 days, effective confidence was `0.45`, band `hedge`. Temporary database was removed afterwards. |
| Running app | Uvicorn startup succeeded; local `/health` returned HTTP 200 with status `ok`; `/` returned HTTP 200 and HTML. Automated tests also exercise startup/shutdown/restart. |
| Workspace links and patch | Link checker: zero broken links; pending later-stage outputs are expected. `git diff --check` passed. |

The live smoke initially exposed different generated keys (`delivery_city` and `current_city`) for the same attribute. Canonical-key normalization and alias regression tests fixed this before completion.

## Next

Day 2: retrieval and reranking, evidence with validated citations, an answer constrained by confidence bands, staleness sweeps and actual forgetting/revocation with replay-resistant tombstones. The answer currently receives no stored-memory evidence. Inspector/privacy/Failure Lab UI remains later work. This Day 1 checkpoint does not complete stage 03 or any later stage.

Lifecycle integration follows the [official FastAPI lifespan documentation](https://fastapi.tiangolo.com/advanced/events/).
