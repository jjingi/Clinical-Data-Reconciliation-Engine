# Architecture decisions

## Overview

```
browser
  └── React (Vite) on :5173 / Nginx on :80 (Docker)
        └── /api/*  →  proxy  →  FastAPI on :8000
                                    ├── app/main.py    (routes, auth, config)
                                    ├── app/schemas.py (Pydantic models)
                                    └── app/llm.py     (OpenAI + cache)
```

---

## Backend — FastAPI (Python)

**Why FastAPI over Flask or Django:**

- Native `async/await` support allows non-blocking OpenAI API calls. Under Flask or Django (sync), each in-flight LLM request would block a worker thread.
- Pydantic v2 is built in. Request bodies are validated and deserialized automatically; invalid payloads return a 422 with field-level errors before any business logic runs.
- Auto-generated OpenAPI docs at `/docs` make the API immediately explorable without extra tooling.
- Most importantly, I'm most familiar with using FastAPI

**Why a flat structure (3 files instead of a full package layout):**

A `main.py` / `schemas.py` / `llm.py` split is enough for two endpoints. Splitting further into `routers/`, `services/`, `repositories/` adds indirection that hurts readability for a small codebase. Each file has a single clear responsibility.

---

## Frontend — React + Vite + Tailwind CSS

**Why React:**
Component model maps naturally to the two independent panels (Reconciliation, Data Quality), each with their own local form state and result state.

**Why Vite:**
Sub-second hot module replacement during development. The `proxy` config in `vite.config.ts` forwards `/api` requests to the backend, eliminating CORS issues in local development without touching the backend config.

**Why Tailwind CSS:**
Utility-first classes allow rapid UI iteration without writing custom CSS files. Color-coded quality scores (red/yellow/green) are expressed with a few conditional class strings rather than separate stylesheet rules.

---

## LLM integration — OpenAI `gpt-5.3-mini`

### Model choice

The model was selected based on the [MEDIC Benchmark](https://huggingface.co/spaces/m42-health/MEDIC-Benchmark), a leaderboard specifically designed to evaluate LLMs on medical and clinical tasks (clinical reasoning, diagnosis, pharmacology, medical QA). `gpt-4.1-mini` ranks in the **top 3 among all mini-class models** on this benchmark, making it the strongest cost-efficient choice for a healthcare AI application. Therefore, I chose the **`gpt-5.4-mini`** which is newer version of `gpt-4.1-mini`. You can find detailed reason in `README.md`

### Prompt design

**Reconciliation prompt** (`_RECONCILE_SYSTEM` in `llm.py`):
- Establishes the model's role as a clinical pharmacist.
- Specifies a priority ordering: recency > source reliability > clinical plausibility > cross-source consistency.
- Defines the exact JSON schema the model must return, including field names and types.
- Defines when `clinical_safety_check` should be `"FAILED"` (direct patient safety risk only).
- `temperature=0.1` minimises hallucination variance.

**Data quality prompt** (`_DATA_QUALITY_SYSTEM` in `llm.py`):
- Defines four scoring dimensions with clinical rationale.
- Specifies the weighted average formula for `overall_score` explicitly so the model doesn't invent its own weights.
- Provides severity level definitions (`high`/`medium`/`low`) to ensure consistent grading.

### Caching

Every request payload is serialised to a deterministic JSON string (sorted keys), hashed with SHA-256, and used as a dictionary key. Identical requests return the cached result without an API call. This reduces cost and latency for repeated inputs (e.g. same patient loaded multiple times during a session).

### Rate limit handling

`_chat_json` catches `openai.RateLimitError` and retries up to 3 times with exponential backoff (sleep 1s, 2s, 4s). After exhausting retries it raises HTTP 429 to the client. Other `openai.APIError` exceptions are wrapped in HTTP 502.

---

## Authentication

A shared `API_KEY` secret is stored in `backend/.env` and loaded via `pydantic-settings`. Every protected route declares `dependencies=[Depends(verify_api_key)]`. The dependency checks the `X-API-Key` request header and raises HTTP 401 on mismatch.

The frontend reads `VITE_API_KEY` from its environment at build time (Vite replaces `import.meta.env.VITE_API_KEY` in the bundle). In Docker, the key is passed as a build argument from the root `.env` file.

**Trade-off:** A shared secret is simple to implement but does not support per-user identity, token expiry, or revocation. A production system would use OAuth 2.0 with short-lived JWTs.

---

## Docker

```
docker-compose.yml
  ├── backend   python:3.12-slim  →  uvicorn on :8000
  └── frontend  node:20-alpine (build) + nginx:alpine (serve)  →  nginx on :80
```

The frontend uses a multi-stage Docker build:
1. **Builder stage** (`node:20-alpine`) — runs `npm ci` and `vite build`. `VITE_API_KEY` is passed as a build `ARG` and injected into the bundle at this step.
2. **Server stage** (`nginx:alpine`) — copies only the compiled `dist/` folder and a custom `nginx.conf`. The final image contains no Node.js tooling.

Nginx is configured to:
- Serve static files from `/usr/share/nginx/html`.
- Proxy `/api/` and `/health` requests to `http://backend:8000` using Docker's internal DNS.
- Return `index.html` for all unmatched routes (React SPA fallback).

---

## Testing strategy

### Test pyramid

```
test_mimic_integration.py   ← end-to-end (live OpenAI + real MIMIC data)
test_reconcile_route.py     ←
test_validate_route.py      ← HTTP contract tests (mocked LLM)
test_pyhealth_data.py       ← unit tests for data model helpers
test_models.py              ← unit tests for Pydantic schema parsing
```

### Key decisions

**FastAPI `TestClient`:** Runs the ASGI app in-process — no server process needed. Tests execute in the same pytest run as unit tests.

**Mock target is `app.main.*`, not `app.llm.*`:** Because `main.py` imports `reconcile_medication` directly (`from app.llm import reconcile_medication`), the live function reference inside `main` must be patched at `app.main.reconcile_medication`, not at its original module location. Patching the wrong target caused 503 errors in early test runs.

**MIMIC integration tests use real OpenAI:** Rather than asserting on specific text content, tests assert on response *shape and ranges* (e.g. `0.0 <= confidence_score <= 1.0`, `clinical_safety_check in ("PASSED", "FAILED")`). This validates the full integration path without brittle string matching.

