# Memory That Knows It Might Be Wrong

A customer-service memory layer, built for Doo's use case (AI customer service), that knows what it knows, what it doesn't, and when to forget.

- **Live demo:** _coming with Day 0 deploy_
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

Python 3.11 · Gradio 6 on FastAPI · SQLite · Groq (`openai/gpt-oss-120b`, `gpt-oss-20b`, `llama-prompt-guard-2-86m`) with OpenRouter and Gemini fallback · deployed on Render.

## Repo layout

This repo is an [ICM workspace](https://arxiv.org/abs/2603.16021): start at [AGENTS.md](AGENTS.md). `stages/` is the build pipeline with a contract per stage, `_shared/` holds the stable rules and prompts, and `app/` is the product.
