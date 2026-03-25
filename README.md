# Clinical Data Reconciliation Engine

A full-stack AI-assisted application that reconciles conflicting medication records across EHR systems and validates patient data quality using GPT.

---

## How to run locally

### Prerequisites

- Python 3.12
- Node.js 20+
- An OpenAI API key

### 1. Clone and set up environment files

```bash
git clone git@github.com:jjingi/Clinical-Data-Reconciliation-Engine.git
cd Clinical-Data-Reconciliation-Engine
```

Copy and fill in the backend secrets:

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and set:

```
API_KEY=your-chosen-api-key
OPENAI_API_KEY=your-open-api-key
OPENAI_MODEL=gpt-5.4-mini
```

### 2. Run the backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend is now running at `http://localhost:8000`.

### 3. Run the frontend

In a new terminal:

```bash
cd frontend
npm install
```

Create `frontend/.env.local` (copy from `frontend/.env.example`) and set:

```
VITE_API_KEY=your-chosen-api-key   # must match API_KEY in backend/.env
```

```bash
npm run dev
```

Frontend is now running at `http://localhost:5173`.

---

## Run with Docker (recommended)

### Prerequisites

- Docker Desktop

### Setup

1. Fill in `backend/.env` as described above.
2. Create a root-level `.env` (copy from `.env.example`):

```bash
cp .env.example .env
# set VITE_API_KEY=your-chosen-api-key  (must match API_KEY in backend/.env)
```

### Start

```bash
docker compose up --build
```

Open `http://localhost` in your browser.

### Stop

```bash
docker compose down
```

---

## Run tests

```bash
cd backend
source .venv/bin/activate

# All 22 tests (fast unit tests + live OpenAI integration tests)
pytest -v

# Only fast unit tests (no OpenAI calls, runs in ~2 seconds)
pytest -v -k "not reconcile_lisinopril and not reconcile_acetaminophen and not data_quality_mimic"

# Live OpenAI tests with printed responses
pytest tests/test_mimic_integration.py -v -s -k "reconcile_lisinopril or reconcile_acetaminophen or data_quality_mimic"
```

> The MIMIC integration tests download ~5 MB of synthetic patient data on first run and call the real OpenAI API. Make sure `OPENAI_API_KEY` is set in `backend/.env`.

---

## LLM API used

**OpenAI — `gpt-5.4-mini`**

The model was selected based on the [MEDIC Benchmark](https://huggingface.co/spaces/m42-health/MEDIC-Benchmark), a leaderboard specifically designed to evaluate LLMs on medical and clinical tasks (clinical reasoning, diagnosis, pharmacology, medical QA). `gpt-4.1-mini` ranks in the **top 3 among all mini-class models** on this benchmark, making it the strongest cost-efficient choice for a healthcare AI application. Therefore, I chose the **`gpt-5.4-mini`** which is newer version of `gpt-4.1-mini`

Specific reasons:

- **Top medical benchmark performance** — chatGPT's mini model ranked top 3 among mini models on MEDIC, which directly evaluates the kind of clinical reasoning this app requires (medication safety, lab value interpretation, drug-disease interactions).
- **Cost-effective** — significantly cheaper than full `gpt-5.4`, which matters because every form submission triggers a live API call with a detailed clinical prompt.
- **Low latency** — mini models return responses in 2–4 seconds, keeping the UI responsive.
- **JSON mode** — `response_format: {"type": "json_object"}` guarantees structured output that maps directly to Pydantic response schemas, removing any need to parse free-form text.
- **No fine-tuning needed** — despite being a mini model, it demonstrates strong out-of-the-box understanding of pharmacology (dose adjustments for renal function, drug-disease contraindications, source reliability weighting).

---

## Key design decisions and trade-offs

### Flat backend structure

Instead of separating routes, services, models, and config into many files, the backend uses three files: `main.py` (app, auth, routes), `schemas.py` (Pydantic models), and `llm.py` (all LLM logic). This trades some long-term scalability for readability 


### Prompt engineering approach

System prompts specify the exact JSON schema the model must return, include a priority ordering for reconciliation decisions (recency > reliability > plausibility > consistency), and define precise severity levels for data quality issues. Low temperature (0.1) reduces response variance. Full prompts are documented in `docs/ARCHITECTURE.md`.

### Rate limit handling

`llm.py` retries OpenAI `RateLimitError` up to 3 times with exponential backoff (1s, 2s, 4s) before returning a 429 to the client.

### API key authentication

A shared secret (`X-API-Key` header) protects all API routes. This is appropriate for an internal tool but would be replaced with OAuth 2.0 / JWT for a production deployment.

### Docker multi-stage build

The frontend Dockerfile uses a two-stage build: Node builds the React app (baking `VITE_API_KEY` into the bundle at compile time), then Nginx serves the static files and reverse-proxies `/api` requests to the backend container. This keeps the production image small (~25 MB).

### Testing strategy

| Test file | What it covers |
|---|---|
| `test_models.py` | Pydantic schemas parse the exact JSON examples |
| `test_reconcile_route.py` | HTTP contract: auth (401), validation (422), happy path (200) |
| `test_validate_route.py` | Same contract tests for the data quality endpoint |
| `test_pyhealth_data.py` | PyHealth `Patient`/`Event` data model and payload conversion helpers |
| `test_mimic_integration.py` | End-to-end: loads Synthetic MIMIC-III patients, calls live OpenAI, asserts on response shape |

---

## What I'd improve with more time


- **Smarter missing-field scoring in data quality** — currently an empty `allergies` list or missing `vital_signs` automatically lowers the completeness score, but absence is not always a gap. A patient may genuinely have no known allergies, or vital signs may not be relevant for an outpatient record. The improvement would be to distinguish between "field is absent" and "field is confirmed empty" (e.g. `"allergies": []` with a `"no_known_allergies": true` flag), and only penalise the score when the field is truly undocumented rather than intentionally blank.
- **Confidence score calibration** — currently the LLM assigns confidence scores; a more robust approach would combine LLM confidence with deterministic factors (number of agreeing sources, recency delta, source reliability weights) for a calibrated score.
- **Resolve clinical codes to human-readable names** — conditions are currently stored and displayed as raw ICD-9/ICD-10 codes (e.g. `"27802"`, `"25082"`). The improvement would be to map these to their actual diagnosis names (e.g. `"Obesity, unspecified"`, `"Diabetes with renal manifestations"`) using a code lookup table or a terminology API like [NLM's RxNorm/SNOMED service](https://www.nlm.nih.gov/research/umls/index.html). This would make both the UI and the LLM prompt more informative — the model reasons better with `"Type 2 Diabetes with CKD"` than with `"25082"`.
- **Duplicate record detection** — identify medications that are the same drug under different brand/generic names using a drug database (e.g. RxNorm).
- **Audit log** — record every reconciliation decision (input, output, timestamp, user approval/rejection) to a database for clinical traceability.
- **Deployment** — deploy this website 

---

## Estimated time spent

| Area | Time |
|---|---|
| Project setup, folder structure, Docker | ~2 hours |
| Backend API + Pydantic schemas | ~2 hours |
| OpenAI integration, prompt engineering, caching | ~3 hours |
| Frontend dashboard (React + Tailwind) | ~4 hours |
| Tests (unit + MIMIC integration) | ~3 hours |
| Debugging (API key issues, mock paths, Python version) | ~2 hours |
| README + architecture docs | ~1 hour |
| **Total** | **~17 hours** |

---

## Test data

Sample request/response payloads from the assessment PDF are in `test-data/`:

- `test-data/medication-reconcile-example.json`
- `test-data/data-quality-example.json`
