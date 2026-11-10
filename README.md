# Memory That Knows It Might Be Wrong

A customer-service memory layer, built for Doo's use case (AI customer service), that knows what it knows, what it doesn't, and when to forget.

- **Live demo:** [Open the demo](https://memory-might-be-wrong.onrender.com)
- **Day 0 verification:** [passing local and live checks](stages/03_build/output/day-0.md)
- **Day 1 verification:** [memory write path and test results](stages/03_build/output/day-1.md)
- **90-second walkthrough:** _coming_
- **Architecture:** [stages/02_architecture](stages/02_architecture/CONTEXT.md)
- **Memory model:** [_shared/memory-model.md](_shared/memory-model.md) · **Policies:** [_shared/policies.md](_shared/policies.md)

## What it does

Every memory carries a **source**, a **confidence**, a **freshness** and a **scope**. Confidence decays with age per category, rises when the customer repeats a fact, and drops when facts disagree. The agent's behaviour follows it: it uses sure facts and cites them, says *"I might be wrong about this"* about doubtful ones, and asks instead of guessing. Stale, contradicted and revoked memories each have an explicit path.

## Run locally

```bash
uv sync
cp .env.example .env   # add GROQ_API_KEY (OpenRouter / Gemini keys optional fallbacks)
uv run uvicorn app.main:app --reload --port 7860
```

Open http://localhost:7860. Tests: `uv run pytest`.

## Stack

Python 3.11 · Gradio 6 on FastAPI · SQLite · Groq (`openai/gpt-oss-120b`, `gpt-oss-20b`, `llama-prompt-guard-2-86m`) with OpenRouter and Gemini fallback · configured for Render deployment.

## Repo layout

This repo is an [ICM workspace](https://arxiv.org/abs/2603.16021): start at [AGENTS.md](AGENTS.md). `stages/` is the build pipeline with a contract per stage, `_shared/` holds the stable rules and prompts, and `app/` is the product.
