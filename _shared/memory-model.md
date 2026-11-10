# Memory model - what a memory is and how sure we are

Factory reference. Every number below lives in [memory-config.json](memory-config.json); this file explains them and never repeats them.

## A memory record

| Field | Meaning |
|---|---|
| `customer_id` | whose memory it is (scope root). One demo visitor = one sandbox customer. |
| `scope` | `customer` (about the person), `order:<id>` (one order/ticket), `session` (this chat only, never persisted past it) |
| `category` | one of the categories in the config; sets half-life and sensitivity |
| `key` / `value` | typed fact, e.g. `delivery_city` = `Dubai`. Same `key` + different `value` = a contradiction. |
| `text` | one human sentence, shown in the inspector |
| `source` | `user_stated`, `user_confirmed`, `agent_record`, `crm_import`, `inferred`; plus the message id and exact quote |
| `base_confidence` | from the source type |
| `created_at`, `last_confirmed_at` | freshness is measured from `last_confirmed_at` |
| `status` | `active`, `stale`, `contested`, `superseded`, `revoked` |
| `supersedes` | id of the memory this one replaced; history is kept |

## Effective confidence

```
decay      = 0.5 ** (age_days / half_life_days)
effective  = base_confidence * decay            (+ corroboration, capped)
contested  -> effective - contested_penalty
revoked    -> not retrievable at all
```

## Behaviour bands

| Effective | The agent |
|---|---|
| >= `thresholds.assert` | uses it and cites it |
| between `hedge` and `assert` | says "I might be wrong about this" and asks before acting |
| < `hedge`, or `contested` | does not use it; asks the customer |

## Contradiction rules (in order)

1. A customer's own words beat anything inferred or imported.
2. Between two customer statements, the newer one wins; the older becomes `superseded`.
3. Two inferred or imported facts that disagree: both become `contested`; the agent asks.
4. The loser is never deleted by a contradiction, only superseded, so history explains itself.
