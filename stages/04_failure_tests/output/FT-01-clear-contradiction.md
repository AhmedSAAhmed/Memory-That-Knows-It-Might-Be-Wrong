# FT-01 - New city replaces old city

Status: passing

## Setup
- Seed: none; a fresh temporary SQLite database per trial.
- Clock: injectable UTC clock, advanced between customer statements.

## Steps
1. Customer says: "I live in Dubai."
2. Advance time; customer says: "I moved to Abu Dhabi."
3. Ask: "Which city do you remember for my delivery?"

## Expected
- Memory state: one current canonical `delivery_city`, Abu Dhabi; Dubai is superseded and retains source history.
- Agent reply: uses and cites the new memory ID; must not reuse Dubai. Actual screening, extraction and answer providers must succeed.
- Audit log: writes, supersession and read-for-answer events.

## Automated as
`tests/test_live_memory_evals.py::test_live_clear_contradiction`

Three distinct trials are required. Offline edge coverage: `tests/test_memory.py` (aliases, source precedence, equal-time/out-of-order statements, rollback and concurrency).
