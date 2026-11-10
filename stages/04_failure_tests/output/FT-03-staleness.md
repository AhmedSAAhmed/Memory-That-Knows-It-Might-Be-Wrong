# FT-03 - Old facts lose assertion authority

Status: passing

## Setup
- Seed: a city extracted from "I live in Dubai." by the actual provider.
- Clock: location half-life from `_shared/memory-config.json`, then another half-life.

## Steps
1. Store the fresh customer statement.
2. Jump one location half-life; ask: "Which city do you have for delivery?"
3. Jump another half-life; ask again.

## Expected
- Memory state: stale after the first jump, with decayed confidence.
- Agent reply: first says "I might be wrong" and asks for confirmation; at lower confidence, asks without revealing Dubai. The live guard must respond. Confidence policy must not call an answer model to decide whether to hedge.
- Audit log: one decay transition; repeat sweeps do not duplicate it.

## Automated as
`tests/test_live_memory_evals.py::test_live_staleness`

Three distinct trials are required. Offline edge coverage: `tests/test_memory.py::test_corroboration_also_decays`, `tests/test_answer_behavior.py`, and pending-reconfirmation tests in `tests/test_service_api.py`.
