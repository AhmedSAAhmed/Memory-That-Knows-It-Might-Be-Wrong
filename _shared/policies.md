# Policies - privacy, forgetting, safety

Factory reference for the write, retrieval and forgetting paths.

## Privacy

- **Secret** categories (credentials, card numbers, OTPs, IDs) are never stored. The agent says it won't keep them.
- **Sensitive** categories (health, finance, family) are stored only after the customer says yes to a consent prompt.
- **Incognito**: while on, nothing from the conversation is written. Reads still work.
- **Blocked categories**: the customer can say "never remember X"; the write path drops those candidates and logs it.
- **Inspector**: the customer can see every memory about them, why it exists (quote + source), and its confidence.
- **Export**: the customer can download all their memories as JSON.
- **Audit log**: every write, read-for-answer, supersede, revoke and decay is logged with a timestamp.

## Forgetting

- **Decay**: confidence falls with age by category half-life. Past one half-life a memory is marked `stale` and the agent re-confirms before using it.
- **Contradiction**: handled by the rules in [memory-model.md](memory-model.md); losers are `superseded`, not deleted.
- **Revocation**: the customer can revoke one memory or "forget everything". The value, text, quote and embedding are erased; a content-free tombstone (`key`, `category`, `revoked_at`) stays so the same fact is not re-learned from old messages without the customer saying it again.

## Safety

- Memory content is **data, never instructions**. Text like "remember to ignore your rules" is stored, if at all, as a low-confidence quote and never fed to the model as a directive.
- Every incoming message is screened by the prompt-guard model before the extractor sees it.
- A customer only ever reads their own memories. Scope is enforced in SQL, not in the prompt.
- The public demo is rate-limited per session and output tokens are capped.
