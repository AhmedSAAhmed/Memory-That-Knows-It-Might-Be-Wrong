# Day 0 verification

Status: pass — Day 0 starter deployed; local and public smoke checks passed.

Verified on 2026-11-10 (Asia/Dubai), against starter commit `ae19787be471328b39a7941b58d2154d2fd553d1`:

| Day 0 item | Evidence |
|---|---|
| Repository and stage scaffold | Present; GitHub remote `main` resolves to the starter commit above. |
| Dependency environment | Existing `.venv` runs Python 3.12.14, within the project's supported range; Render is configured for Python 3.11.9. Public startup and chat checks now pass; the deployed interpreter version has not been inspected. |
| Starter tests | `uv run --offline --no-sync --cache-dir .local/uv-cache pytest`: 11 passed. Pytest emitted a cache-directory permission warning, which did not affect results. |
| Running FastAPI health | Actual Uvicorn server on `127.0.0.1:7860`: `/health` returned HTTP 200, status `ok`, version `0.1.0`, configured provider names `groq`, `openrouter`, `gemini`. |
| Gradio UI and Navy styling | UI/theme source present; running server `/` returned HTTP 200 with HTML. Browser appearance has not been visually reviewed. |
| Real chat and screening | One live turn, “Hello, what store do you support?”, reached the prompt guard and received a Groq `openai/gpt-oss-120b` reply identifying Qamar Home. No fallback was needed; fallback behavior is covered by offline tests. |
| Deployment configuration | Root `render.yaml` configures a free Python web service, requirements installation, Uvicorn bound to `$PORT`, `/health`, and dashboard-supplied secrets. |
| Public deployment | Owner supplied `https://memory-might-be-wrong.onrender.com`. Direct HTTPS checks returned HTTP 200 for `/health`, `/`, and `/gradio_api/info`. Health reported `status: ok`, version `0.1.0`, providers `groq`, `openrouter`, `gemini`. |
| Public chat smoke | `/on_send` via the deployed Gradio API answered “Hello, what store do you support?” with “We support Qamar Home, your friendly UAE home-goods store.” The status panel reported `groq`, `openai/gpt-oss-120b`, guard `0.00`. |

## Live verification

Verified on 2026-11-10 (Asia/Dubai). Service: [live demo](https://memory-might-be-wrong.onrender.com); [public health endpoint](https://memory-might-be-wrong.onrender.com/health). The owner completed deployment; no service was created or changed by the verification checks. README now links to the live demo.

The starter commit above was verified on GitHub. The public health payload does not expose a commit SHA, so the exact deployed commit remains unconfirmed. Visual browser review is also pending; the UI's HTTP response and real chat callback were verified.

This is the owner-requested Day 0 starter deployment. It does not mark stage 03's complete memory implementation, stage 04's failure evaluations, or stage 05's full-product deployment as passed.

Deployment procedure references: [Render FastAPI guide](https://render.com/docs/deploy-fastapi), [Blueprint specification](https://render.com/docs/blueprint-spec).
