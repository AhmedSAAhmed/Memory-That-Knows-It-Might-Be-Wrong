# Stage 05 deployment log

Status: **pass** — verified 2026-11-10 (Asia/Dubai).

- Live demo: [memory-might-be-wrong.onrender.com](https://memory-might-be-wrong.onrender.com).
- Public health: [/health](https://memory-might-be-wrong.onrender.com/health).
- Repository: [AhmedSAAhmed/Memory-That-Knows-It-Might-Be-Wrong](https://github.com/AhmedSAAhmed/Memory-That-Knows-It-Might-Be-Wrong).
- Deployed application commit: [`b6d41357dfcf4e6f534cdb402c5d6bd47962601f`](https://github.com/AhmedSAAhmed/Memory-That-Knows-It-Might-Be-Wrong/commit/b6d41357dfcf4e6f534cdb402c5d6bd47962601f).
- Deployment method: pushed `main`; the existing Render service auto-deployed the repository using its existing provider environment settings.

## Prerequisite gates

[Stage 03](../../03_build/output/check.md) passed startup/health and the corrected offline suite. [Stage 04](../../04_failure_tests/output/report.md) subsequently passed **124 offline tests and all 18 live trials**, three successful runs of each documented failure scenario. Evaluation run: `20261110T114228Z-4fc79cce`.

Source, tests and stage evidence were committed and pushed. Staged-file checks excluded `.env`, local credentials, runtime databases and local-only tooling. The public health payload lists configured Groq, OpenRouter and Gemini providers; the browser scenario actually used Groq for live answers.

## Public verification

The final `curl.exe --fail --silent --show-error --max-time 45 https://memory-might-be-wrong.onrender.com/health` check returned **HTTP 200**:

```json
{"status":"ok","version":"0.1.0","revision":"b6d41357dfcf4e6f534cdb402c5d6bd47962601f","llm_providers":["groq","openrouter","gemini"]}
```

The root UI returned HTTP 200 and loaded in an isolated Chrome browser. The following full scenario passed through the actual public UI and same-session API; browser verification completed at 15:49 Asia/Dubai, with a final health check at 15:52.

| Step | Observed result |
|---|---|
| Reset/start | Fictional visitor received five seed records through its private session API. |
| Ask which delivery city is remembered | Real Groq answer used Dubai and displayed the corresponding evidence ID and source quote. |
| Say “I moved to Abu Dhabi.” | New city became active; the earlier Dubai fact became superseded. |
| Move the Failure Lab clock forward 365 days | City became stale; confidence was 0.45. |
| Ask the city again | Reply said “I might be wrong about this”; evidence showed the aged fact and hedge band. |
| Reply “yes” | Shown facts were reconfirmed; city source became `user_confirmed` and returned to the assert band. |
| Privacy → Forget everything | All retained fact versions became revoked with empty value/text/quote fields; export contained neither Dubai nor Abu Dhabi. |
| Ask the city after erasure | Reply explicitly acknowledged the forgotten information and asked for a fresh detail. Neither city value appeared and no active fact was recreated. |
| Reset demo | Fictional seed records were restored in the test visitor's sandbox. |

This test used only an isolated fictional visitor. Browser cookies, raw provider credentials and test-browser artifacts remain outside Git.

## Correction found during deployment

The initial application commit `9e25f1ef883790e2c80a31e6889c79aa6ffa72be` deployed successfully and erased stored payloads, but a follow-up city question received a generic delivery-coverage answer. Returned to Stage 03, added failing regression tests, and made the post-erasure reply explicitly acknowledge forgetting using metadata-only tombstones. Freshly restated facts and unrelated remaining memories still work. The build and complete Stage 04 evaluation were rerun successfully before deploying the corrected commit above.

## Operating notes and next stage

The service uses the planned disposable SQLite demo storage and per-visitor sandboxes. Optional uptime pings were not configured. Provider fallback and optional-vector fallback remain the application behavior covered by prior tests.

The documentation-only follow-up commit uses `[skip render]` to retain the verified application revision while publishing this record. Stage 05 is complete; Stage 06 submission preparation and owner approval are next.
