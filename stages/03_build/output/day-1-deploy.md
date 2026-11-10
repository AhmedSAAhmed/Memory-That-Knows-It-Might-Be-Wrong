# Day 1 deployment verification

pass — verified on 2026-11-10 (Asia/Dubai).

- Service: [live demo](https://memory-might-be-wrong.onrender.com).
- Application commit pushed to GitHub `main`: `e295a4faa165a2bec737f5d5a7345be6d4b40466`.
- [Public health](https://memory-might-be-wrong.onrender.com/health): HTTP 200, `status: ok`, `revision` exactly matching the application commit, configured providers `groq`, `openrouter`, `gemini`.
- Public UI `/`: HTTP 200 and HTML.
- Public Gradio `/on_send`, one isolated client session: “I live in Dubai.” and then “I moved to Abu Dhabi.” both completed successfully. Each status panel reported `memory writes: 1`, `groq`, `openai/gpt-oss-120b`, guard `0.00` (rounded). No unavailable-provider or extraction-error status appeared.
- Pre-deployment offline evaluator: 92 tests passed, including revision reporting. Local live-provider checks also verified supersession/history and half-life decay; the public API does not yet expose the inspector for direct inspection of those records.
- Credentials and runtime databases were excluded from the commit. Existing Render environment settings were used.

This records publication of the Day 1 milestone. Retrieval, evidence-aware answers, forgetting and the full stage 03/04/05 gates remain pending.

The follow-up documentation commit uses Render's [documented skip phrase](https://render.com/docs/deploys#skipping-an-auto-deploy) so the verification record can be published while retaining the verified application revision.
