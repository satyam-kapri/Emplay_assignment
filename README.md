# RFP Intelligence Platform

Python application for HTML/PDF bid ingestion, standalone hybrid retrieval and evidence-grounded multi-agent extraction/Q&A. Each bid folder is processed as a unit; production code contains no Bid1/Bid2 answer branches or hard-coded dates/SKUs.

## Validation status

The parser/search stack is exercised on the supplied documents and benchmarked separately from generation. Automated tests use controlled model responses to check orchestration, citation validation and provider failure recovery.

**Live LLM extraction and Q&A are not yet verified:** no endpoint/model/key was configured during implementation. The code fails clearly on missing configuration rather than fabricating output. `scripts/demo.py` generates the two real bid JSON files, at least ten cited Q&A examples and extraction traces once a compatible LLM is configured. Those generated deliverables require manual correctness review before submission.

Bid1 RFP physical pages 54-59 have no extractable text. Readable content remains searchable; warnings and partial status propagate to outputs. OCR and other assignment bonuses are deferred. A demo recording and a genuinely unseen external-bid evaluation have not been produced.

## Setup

Use Python 3.11+ (validated on Python 3.12 on Windows). From this repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
python -m pip install --no-build-isolation --no-deps -e .
Copy-Item .env.example .env
```

The lock records the environment used for verification. It includes Windows `pywin32`; on another operating system use `python -m pip install -e ".[test]"` instead of that Windows lock. Network access is needed initially for package installation and model downloads. Embedding/reranking models are cached under `.data/models`; vectors and manifests under `.data`. These files and `.env` are excluded from Git.

Configure these only for generated extraction/Q&A:

```text
LLM_BASE_URL=<compatible endpoint base, usually ending in /v1>
LLM_MODEL=<model supported by that endpoint>
LLM_API_KEY=<secret, if required>
```

The adapter expects `/chat/completions`, JSON object response mode and text completion content. It validates model JSON with Pydantic and retries malformed responses/timeouts with bounded attempts. Other provider protocols require a new adapter. No credentials are needed for parsing, dense/hybrid search, reranking or retrieval evaluation.

## Commands

After setup, extraction performs indexing automatically:

```powershell
python -m rfp_intelligence.cli extract --bid ./Bid1
python -m rfp_intelligence.cli extract --bid ./Bid2
```

Standalone retrieval:

```powershell
python -m rfp_intelligence.cli index --bid ./Bid1
python -m rfp_intelligence.cli index --bid ./Bid2
python -m rfp_intelligence.cli search --query "submission deadline" --bid-id Bid1
python -m rfp_intelligence.cli search --query "370-BBTL" --bid-id Bid2 --doc-type specs
python -m rfp_intelligence.cli search --query "changes" --bid-id Bid1 --doc-type addendum --addendum-number 2
python -m rfp_intelligence.cli ask --query "Compare the warranty requirements" --bid-id Bid1 --bid-id Bid2
python -m rfp_intelligence.cli serve
```

Search supports `--mode dense|hybrid|rerank` and `--top-k`. The default is hybrid (`RFP_SEARCH_MODE`), chosen from development-set MRR; reranking remains implemented, benchmarked and selectable. An omitted bid filter searches the indexed corpus; generation retrieves each bid separately for cross-bid questions. Documents must be immediate PDF/HTML files inside a folder under `RFP_DATA_ROOT` (default repository root). Folder names supply bid IDs, so use distinct names.

Indexing reports files indexed/skipped/deleted, per-file errors and warnings. Repeating an unchanged folder skips parsing and embedding. Changed/deleted files replace/remove their active generation; adding a new folder does not re-embed other bids. A model/parser/chunker change requires re-indexing. CLI exit code 2 signals setup/validation errors or a partial run, including the expected no-text-page warnings on Bid1; the JSON report explains the reason.

Local REST API (one process, localhost; interactive OpenAPI docs at `/docs`):

| Route | Input | Result |
|---|---|---|
| `POST /index` | `{"folder":"Bid1"}` | Incremental indexing report |
| `GET /search` | `q`, repeated `bid_id`/`doc_type`/`addendum_number`, `top_k`, `mode` | Ranked cited passages |
| `POST /extract` | `{"folder":"Bid1"}` | Complete 20-field schema with validation status |
| `POST /ask` | `{"question":"...","bid_ids":["Bid1"]}` | Answer, citations, warnings and run ID |
| `GET /health` | None | Process health |

This is a local assignment API, without authentication or a distributed job queue. Close the CLI process before starting another process using the same local Qdrant data directory.

## Architecture and reasons

The diagram and phase plan are in [PROJECT_PLAN.md](PROJECT_PLAN.md); implementation choices, tradeoffs and revisit conditions are in [docs/DECISIONS.md](docs/DECISIONS.md). Work purposes are recorded in [docs/WORK_LOG.md](docs/WORK_LOG.md).

- **Parsing:** pdfplumber preserves PDF page and table structure. A coordinate-based fallback recovers borderless SKU-description rows; HTML labels remain attached to values. Raw source text is retained separately. Empty/scanned/unreadable documents are reported rather than silently treated as complete.
- **Chunking:** section-aware, page-local prose chunks target 350 tokenizer tokens with 50-token overlap; table rows remain together and table headers repeat. Extremely large units are split under the tokenizer budget. Sizes are initial hypotheses, not claimed optimal values. A 250-versus-350 size experiment from the plan remains a future tuning step; current evaluation isolates retrieval configurations at fixed size.
- **Embeddings:** initial local `BAAI/bge-small-en-v1.5` balances English semantic retrieval with CPU operation. Cached weights avoid mandatory per-query API usage.
- **Hybrid retrieval:** BM25 preserves full identifiers and their components; Qdrant supplies semantic candidates. Both branches apply the same filters before ranking. Original and conservatively expanded queries remain searchable. Reciprocal Rank Fusion (constant 60) avoids comparing incompatible score scales.
- **Reranking:** `cross-encoder/ms-marco-MiniLM-L6-v2` reranks at most 30 fused candidates before returning five by default. Candidate counts/model names are centralized; environment variables configure model names.
- **Storage:** SQLite manifests activate generations after vector staging; failed file updates preserve previous active data. A local lock protects indexing/search. BM25 is reconstructed over filtered active chunks for simplicity on the small corpus; this is not a large-scale keyword backend.
- **Agents:** asyncio routes deterministic ingestion/retrieval and parallel dates/logistics, commercial/legal, product/identity extraction groups. Reconciliation applies explicit field-specific amendments. A validator checks citations and semantic support, returns failed fields for focused re-retrieval/extraction (default two repair attempts), then report/Q&A synthesizes the final output.
- **Prompts:** treat documents as untrusted evidence, preserve exact source time zones, require quoted citations, distinguish missing from explicit not-required, avoid inferring requirements from blank forms. Raw full-page text is never secretly attached to retrieved chunks in reasoning prompts.
- **Outputs:** Pydantic constrains agent messages; deterministic checks verify quoted text, chunk IDs and source metadata. Semantic support is judged by a separate LLM critic, whose quality still needs live evaluation.

Confidence follows a fixed evidence rubric: 0 for absent/failed values, 0.85 for a validated single-source value, 0.90 for a validated value with multiple source files. It is not a calibrated probability. A missing field uses null, empty sources and an explanatory note. Explicit “not required” needs a source. Date values preserve ambiguous/missing source components; no unstated timezone is invented. HTML citations use `page: null` plus a DOM locator; PDF citations use one-based physical page numbers.

The 20 external field names match assignment section 8 exactly. Product/model/SKU/spec associations are requested as structured values with citations. The external field envelope is stable; detailed product-value shapes currently rely on the generation prompt and critic rather than specialized per-product Pydantic schemas. This is a known area for further contract tightening after a live run.

## Tests and evaluation

```powershell
python -m pytest -q
python -m scripts.audit_corpus
python -m rfp_intelligence.cli evaluate --questions eval/questions.json
python -m scripts.verify_search
```

`verify_search` indexes both supplied folders, saves indexing reports and evaluates dense-only, hybrid and hybrid-plus-reranker against the same corpus. Evaluation does not call an LLM. `eval/questions.json` contains 22 manually specified file/page/quote labels verified against parsed sources: six development and sixteen nominally held-out. `scripts/prepare_eval.py` reconstructs and verifies those labels if needed. Development MRR informed the default retrieval mode. Inspection of a held-out miss exposed an uppercase addendum sentence being split as a heading; the parser was corrected and results regenerated. Therefore the final held-out partition is a regression set, not an untouched external test set. Initial results are retained in `outputs/initial_retrieval_evaluation.json`.

Recall@1/3/5 measures the fraction of expected source passages covered; MRR@5 measures the reciprocal first relevant rank. Matching uses file, page/HTML locator convention and passage substring. Multiple-passage logic is unit-tested, although current question labels are mostly single-passage. No-answer abstention is tested separately, not assigned a misleading retrieval recall score.

Actual per-question results, corpus fingerprint and model names are in [outputs/retrieval_evaluation.json](outputs/retrieval_evaluation.json); the readable table is in [outputs/retrieval_evaluation.md](outputs/retrieval_evaluation.md). Corpus inspection is recorded in [outputs/corpus_audit.json](outputs/corpus_audit.json). This small set does not establish broad generalization or statistical significance.

Final measurements across both bids:

| Mode | Partition | Questions | Recall@5 | MRR@5 |
|---|---|---:|---:|---:|
| Dense | Development | 6 | 1.0000 | 0.5417 |
| Hybrid | Development | 6 | 0.8333 | 0.6389 |
| Hybrid + reranker | Development | 6 | 1.0000 | 0.6389 |
| Dense | Regression (`held_out` label) | 16 | 0.8750 | 0.5781 |
| Hybrid | Regression (`held_out` label) | 16 | 1.0000 | 0.9583 |
| Hybrid + reranker | Regression (`held_out` label) | 16 | 0.8750 | 0.6427 |

These values are passage-retrieval metrics, not extraction accuracy. The initial hybrid advantage on development MRR led to the default choice; after parser corrections, hybrid and reranked development MRR tie. Hybrid avoids the additional reranker inference stage, while users can select reranking where its extra candidate coverage is useful.

Tests cover real addendum parsing and SKU relationships, HTML labels/cleanup, token preservation, table chunk integrity, filtered retrieval, incremental updates/deletions, failed-file preservation, citation rejection, targeted repairs, retry exhaustion, unchanged-field reconciliation, malformed JSON recovery, timeout recovery and local API validation. Controlled LLM fixtures test mechanics and do not count as real extraction accuracy.

Final verification: 23 tests passed; dependency checks reported no broken requirements; editable package installation and CLI startup succeeded. One upstream TestClient deprecation warning remains. The missing-provider CLI error was also verified.

## React workspace

Start the backend from the repository root with `python -m rfp_intelligence.cli serve`. In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. The Vite server proxies `/api` to port 8000. Select a bid to search documents, inspect source passages, ask cited questions, or extract and export the 20-field record. Index a new folder through the sidebar; it must be inside the configured backend data root. Q&A and fresh extraction require the LLM settings described above; search and saved record review do not.

`npm run build` type-checks and creates `frontend/dist`. `npm run preview` serves that build locally with the same API proxy. Production hosting must route `/api/*` to FastAPI with the prefix removed; the static build alone does not include the backend. Run one backend process for the local Qdrant store.

Frontend choices and their reasons are in [docs/FRONTEND_DESIGN.md](docs/FRONTEND_DESIGN.md). Verification: production build passed, 24 backend tests passed, and browser checks covered real search/source inspection, missing-provider errors, folder dialog dismissal, and a 390px mobile viewport without horizontal overflow. Live generated answers and extraction records remain unverified until a provider is configured.

## Generate submission artifacts

After configuring a provider:

```powershell
python -m scripts.demo
```

This makes provider calls. It writes `outputs/Bid1.json`, `outputs/Bid2.json`, `outputs/sample_qa.json` (eleven questions) and JSONL traces under `outputs/traces/`. Each trace records role inputs, search tools, structured output, token usage when provided, latency, retries and final validation. Credentials and raw provider headers are excluded. Check both extraction records and claim-level citations manually; a schema-valid result alone is not proof of correctness.

Follow [docs/DEMO.md](docs/DEMO.md) for a live or recorded demonstration. Submission still needs reviewed real generated artifacts, a full real extraction trace and the five-to-ten-minute demo. These limitations are explicit so mock outputs cannot be mistaken for completed assignment evidence.
