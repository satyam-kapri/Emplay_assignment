[Watch the project demo on Loom](https://www.loom.com/share/8fd38be3c6a048c78857034902d85a27)
LIVE DEPLOYED PROJECT LINK: http://15.206.205.43:8080/

# RFP Intelligence Platform

Search PDF/HTML bids, ask cited questions, and extract 20-field records through a React workspace or CLI.

## Setup

Use Python 3.12 and Node.js. Run from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
python -m pip install --no-build-isolation --no-deps -e .
Copy-Item .env.example .env
```

Keep an existing `.env`. On Linux/macOS, install with `python -m pip install -e ".[test]"` instead of the Windows lock. Do not mix Python versions in one virtual environment.

Set Gemini credentials in `.env`:

```dotenv
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=<your available Gemini model>
LLM_API_KEY=<your key>
LLM_TIMEOUT=120
```

Search works without LLM credentials. Keys stay in the ignored backend `.env`.

## Run the app

Terminal 1:

```powershell
cd C:\Users\Admin\Emplay_assignment
.\.venv\Scripts\python.exe -m rfp_intelligence.cli serve
```

Terminal 2:

```powershell
cd C:\Users\Admin\Emplay_assignment\frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Select a bid, update its index, then search, ask questions, or extract/export JSON. Skip `npm ci` on later starts. Restart the backend after changing `.env`.

API health: http://127.0.0.1:8000/health · API docs: http://127.0.0.1:8000/docs. Stop servers with Ctrl+C. Run only one process against the local Qdrant store.

## Docker

Start Docker Engine, then run from the repository root:

```powershell
docker compose up -d --build
docker compose ps
docker compose logs -f backend
docker compose down
```

Open http://127.0.0.1:8080 and index both bids. In Docker, folder paths are `/bids/Bid1` and `/bids/Bid2`. Named volumes retain indexes, models and outputs; `down -v` deletes them.

For hosting, configure `RFP_BIND_ADDRESS` and `RFP_HTTP_PORT` in `.env`. Add HTTPS and access control before public exposure; the app has no login. Keep one backend replica. Compose validation passes; image builds and AWS deployment remain unverified.

## CLI commands

Activate `.venv` first. Stop the API before running CLI operations.

```powershell
python -m rfp_intelligence.cli index --bid ./Bid1
python -m rfp_intelligence.cli index --bid ./Bid2
python -m rfp_intelligence.cli extract --bid ./Bid1
python -m rfp_intelligence.cli extract --bid ./Bid2
python -m rfp_intelligence.cli search --query "submission deadline" --bid-id Bid1
python -m rfp_intelligence.cli search --query "370-BBTL" --bid-id Bid2 --doc-type specs
python -m rfp_intelligence.cli search --query "changes" --bid-id Bid1 --doc-type addendum --addendum-number 2
python -m rfp_intelligence.cli ask --query "Compare the warranty requirements" --bid-id Bid1 --bid-id Bid2
python -m rfp_intelligence.cli serve
```

Search supports `--mode dense|hybrid|rerank` and `--top-k`; hybrid is the default. Bid folders contain immediate PDF/HTML files under `RFP_DATA_ROOT`. Extraction indexes automatically. Unchanged files are skipped; exit code 2 indicates errors or partial results.

## API

| Route | Input | Result |
|---|---|---|
| `POST /index` | `{"folder":"Bid1"}` | Incremental indexing report |
| `GET /search` | `q`, repeated `bid_id`/`doc_type`/`addendum_number`, `top_k`, `mode` | Ranked cited passages |
| `POST /extract` | `{"folder":"Bid1"}` | Complete 20-field schema with validation status |
| `POST /ask` | `{"question":"...","bid_ids":["Bid1"]}` | Answer, citations, warnings and run ID |
| `GET /health` | None | Process health |

## Tests and evaluation

```powershell
python -m pytest -q
python -m scripts.audit_corpus
python -m rfp_intelligence.cli evaluate --questions eval/questions.json
python -m scripts.verify_search
cd frontend
npm run build
```

24 tests and the frontend build pass. Retrieval evaluation uses 22 source-labeled questions. The 16-question regression set was inspected during a parser fix, so it is not an untouched holdout.

| Mode | Partition | Questions | Recall@5 | MRR@5 |
|---|---|---:|---:|---:|
| Dense | Development | 6 | 1.0000 | 0.5417 |
| Hybrid | Development | 6 | 0.8333 | 0.6389 |
| Hybrid + reranker | Development | 6 | 1.0000 | 0.6389 |
| Dense | Regression (`held_out` label) | 16 | 0.8750 | 0.5781 |
| Hybrid | Regression (`held_out` label) | 16 | 1.0000 | 0.9583 |
| Hybrid + reranker | Regression (`held_out` label) | 16 | 0.8750 | 0.6427 |

These measure passage retrieval, not extraction accuracy. See [evaluation results](outputs/retrieval_evaluation.md) and [corpus audit](outputs/corpus_audit.json).

## Generate demo outputs

With a configured LLM, stop the API and run:

```powershell
python -m scripts.demo
```

Creates bid JSON records, eleven Q&A examples and traces under `outputs/`. Review generated facts and citations. Live extraction accuracy has not been independently verified. Bid1 pages 54–59 lack extractable text; OCR is deferred.

## Design notes

[Project plan](PROJECT_PLAN.md) · [Technical decisions](docs/DECISIONS.md) · [Frontend choices](docs/FRONTEND_DESIGN.md) · [Work log](docs/WORK_LOG.md) · [Demo guide](docs/DEMO.md)
