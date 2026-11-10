# Stage 03 build

Status: complete locally on 2026-11-10 (Asia/Dubai). [Build check](check.md) passed. [Stage 04 formal evaluation](../../04_failure_tests/output/report.md) subsequently passed; Stage 05 deployment is next. The public site remains the earlier Day 1 milestone.

## Implemented

- Day 1 foundation: typed facts, SQLite/FTS5 storage, deterministic contradiction handling, source-event idempotency, confidence, privacy checks and clocks. Earlier [Day 1 results](day-1.md) and [milestone deployment](day-1-deploy.md) are historical checkpoints.
- Customer/scope-filtered lexical and optional embedding retrieval. Gemini supplies optional vectors; adapter failure leaves lexical search usable. Evidence includes ID, quote, source, age and confidence; contested and below-threshold evidence omits values and quotes.
- Confidence-aware answers: stale facts are hedged and require confirmation; uncertain facts ask without exposing their value. Citation IDs are validated. Unsupported model output falls back to a reply grounded in eligible evidence. Memory content is passed as untrusted user data, never inserted into system instructions. Raw prior chat is excluded so revoked or superseded facts cannot re-enter through conversation history.
- Startup and request decay sweeps; revocation erases payloads across versions, FTS and embeddings while retaining scoped content-free tombstones. Old source events and post-revocation imports/inferences are blocked; a fresh explicit customer statement can restore a fact.
- Signed, expiring server-issued visitor identities shared by API and UI. Customer IDs supplied as query arguments or chat data do not select another visitor's records. Order scope is server-authorized. Session facts live in a separate in-memory database and expire with the service/session state.
- Seeded fictional Qamar Home visitor, per-customer clock, reset, incognito, category blocks and explicit sensitive-category consent. Pending reconfirmations contain IDs only, obey rate limits, and are cleared by correction/revocation/reset. An incognito “yes” cannot refresh memory.
- Complete Gradio tabs: chat/evidence, inspector with confirm/correct/revoke/source history, privacy/export/audit, clock and six isolated offline Failure Lab demonstrations, and the write/retrieve/forget explanation. Revocation refreshes inspector/export and clears chat/evidence/history caches. Desktop evidence sits beside the chat; the layout wraps for narrower screens.
- Identity-bound HTTP list/export/history and confirm/correct/revoke endpoints. Storage opens at startup and closes/reopens safely across app lifespans.

## Verification

- Tests were introduced and observed failing before implementing each new memory behavior. Full suite: **119 passed**, no warnings.
- Coverage includes persistence, customer/order isolation, source precedence, equal-time/out-of-order conflicts, corroboration/decay, replay barriers, malformed extraction, unavailable screening/providers, consent/incognito, secret handling, transaction rollback, concurrent connections, embeddings/fallback, redacted evidence, citation validation, erasure, transient sessions and pending reconfirmation safety.
- Actual local Uvicorn: `/health` HTTP 200 with `status: ok`; UI `/` HTTP 200.
- Actual Gradio/API smoke with configured Groq: cited Dubai, corrected to Abu Dhabi, revoked the city key, and verified both payloads disappeared from the export. A later smoke on the final Python source again verified a real cited reply and revocation/export erasure.
- Headless Chrome: private clock slider at +365 days produced “I might be wrong” with the aged city; Reset demo worked; all six offline Lab checks passed. A desktop screenshot was reviewed and the container width corrected so chat and evidence render side by side.
- Link checker: zero broken links. `git diff --check`: passed.

## Next stage

Stop at the Stage 03 gate. Stage 04 must produce its failure-test scenario documents, report and evaluator pass before Stage 05 deployment. The offline Lab demonstrations and build tests do not replace that formal evaluation.

Operational limits remain those of the planned demo: disposable SQLite hosting, fictional seed data, optional external embeddings, and session identities that rotate on process restart unless `SESSION_SECRET` is configured. Independent browser sessions intentionally receive separate sandboxes.
