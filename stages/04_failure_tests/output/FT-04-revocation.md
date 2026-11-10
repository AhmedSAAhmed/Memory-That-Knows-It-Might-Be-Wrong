# FT-04 - Forgotten health facts stay erased

Status: passing

## Setup
- Seed: none. Explicit health consent is enabled for the fictional test customer.
- Clock: injectable UTC time, advanced after revocation for replay/import attempts.

## Steps
1. Customer says: "I am pregnant." Actual screening and extraction must store the consented health fact.
2. Attach a test vector, then say: "forget everything".
3. Replay the original event and attempt a later CRM import of the old fact.
4. Ask what health information is remembered, supplying the old chat as a hostile history input.

## Expected
- Memory state: values, text, quotes and vectors erased; scoped metadata-only tombstone remains. Original replay and the later import cannot recreate the fact.
- Agent reply: confirms completed erasure, clears chat state, and acknowledges that a requested fact was forgotten before asking for a fresh detail. Neither the forgotten value nor its attribute name is revealed in that acknowledgment; no answer-model call is needed. Raw prior chat must not reach the answer model.
- Audit log: revoke event with metadata only.

## Automated as
`tests/test_live_memory_evals.py::test_live_revocation`

Three distinct trials are required. Offline edge coverage: `tests/test_retrieval_forgetting.py` (all versions, FTS and late vectors) and `tests/test_service_api.py::test_forgetting_clears_pending_confirmation`.
