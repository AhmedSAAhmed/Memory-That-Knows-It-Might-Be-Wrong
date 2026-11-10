# FT-02 - Conflicting imports require a question

Status: passing

## Setup
- Seed: fresh inferred Dubai and imported Sharjah facts for the same customer, scope and key.
- Clock: no age offset.

## Steps
1. Persist the two disagreeing non-customer sources.
2. Customer asks: "Which city do you remember for my delivery?"

## Expected
- Memory state: both versions contested.
- Agent reply: asks the customer; neither city value may appear in the reply or evidence. Contested values never reach the answer model. The real screening provider must respond.
- Audit log: written/contested transitions and reads recorded without payload copies.

## Automated as
`tests/test_live_memory_evals.py::test_live_ambiguous_contradiction`

Three distinct trials are required. Offline edge coverage: `tests/test_memory.py::test_explicit_same_value_resolves_contested_group` and `tests/test_retrieval_forgetting.py::test_contested_values_never_enter_evidence`.
