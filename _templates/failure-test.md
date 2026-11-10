# FT-{NN} - {failure in five words}

Status: {draft | passing | failing}

## Setup
- Seed: {memories present before the test, with source and age}
- Clock: {offset in days, if any}

## Steps
1. Customer says: "{message}"
2. {next message or action, e.g. revoke memory X, jump clock +200d}

## Expected
- Memory state: {statuses after the steps}
- Agent reply: {what it must and must not say}
- Audit log: {events that must appear}

## Automated as
`tests/{test_file}.py::{test_name}`
